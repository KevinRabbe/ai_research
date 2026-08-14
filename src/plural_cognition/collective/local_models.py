"""Frozen local inference runtime and capable-model source identities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Any
from urllib.parse import quote

from .content_store import validate_sha256

LOCAL_MODEL_SOURCE_FREEZE_SCHEMA = "plural-cognition-local-model-source-freeze-v2"


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _nonempty(value: str, field: str) -> None:
    if type(value) is not str or not value:
        raise ValueError(f"{field} must be a non-empty string")


def _git_revision(value: str, field: str) -> None:
    if type(value) is not str or len(value) != 40:
        raise ValueError(f"{field} must be a full 40-character Git SHA")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{field} must be hexadecimal") from exc
    if value != value.lower():
        raise ValueError(f"{field} must use lowercase hexadecimal")


class ModelArtifactProvenance(str, Enum):
    FIRST_PARTY = "first-party"
    COMMUNITY_QUANTIZATION = "community-quantization"


@dataclass(frozen=True, slots=True)
class LocalInferenceRuntimeFreeze:
    release: str
    upstream_commit: str
    platform: str
    accelerator_backend: str
    binary_archive_sha256: str
    cudart_archive_sha256: str

    def __post_init__(self) -> None:
        for field, value in (
            ("release", self.release),
            ("upstream_commit", self.upstream_commit),
            ("platform", self.platform),
            ("accelerator_backend", self.accelerator_backend),
        ):
            _nonempty(value, field)
        validate_sha256(self.binary_archive_sha256)
        validate_sha256(self.cudart_archive_sha256)
        if self.binary_archive_sha256 == self.cudart_archive_sha256:
            raise ValueError("runtime binary and CUDA runtime archives must differ")

    def canonical_payload(self) -> dict[str, str]:
        return {
            "release": self.release,
            "upstream_commit": self.upstream_commit,
            "platform": self.platform,
            "accelerator_backend": self.accelerator_backend,
            "binary_archive_sha256": self.binary_archive_sha256,
            "cudart_archive_sha256": self.cudart_archive_sha256,
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()


@dataclass(frozen=True, slots=True)
class FrozenModelSource:
    candidate_id: str
    quant_repository: str
    quant_repository_revision: str
    source_repository: str
    source_repository_revision: str
    provenance: ModelArtifactProvenance
    filename: str
    size_bytes: int
    artifact_sha256: str

    def __post_init__(self) -> None:
        for field, value in (
            ("candidate_id", self.candidate_id),
            ("quant_repository", self.quant_repository),
            ("source_repository", self.source_repository),
            ("filename", self.filename),
        ):
            _nonempty(value, field)
        _git_revision(self.quant_repository_revision, "quant_repository_revision")
        _git_revision(self.source_repository_revision, "source_repository_revision")
        if not isinstance(self.provenance, ModelArtifactProvenance):
            raise TypeError("provenance must be ModelArtifactProvenance")
        if type(self.size_bytes) is not int or self.size_bytes < 1:
            raise ValueError("size_bytes must be a positive integer")
        validate_sha256(self.artifact_sha256)

    @property
    def download_url(self) -> str:
        repository = quote(self.quant_repository, safe="/")
        revision = quote(self.quant_repository_revision, safe="")
        filename = quote(self.filename, safe="")
        return (
            f"https://huggingface.co/{repository}/resolve/{revision}/{filename}"
            "?download=true"
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "quant_repository": self.quant_repository,
            "quant_repository_revision": self.quant_repository_revision,
            "source_repository": self.source_repository,
            "source_repository_revision": self.source_repository_revision,
            "provenance": self.provenance.value,
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "artifact_sha256": self.artifact_sha256,
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()


@dataclass(frozen=True, slots=True)
class LocalModelSourceFreeze:
    software_revision: str
    supersedes_v1_manifest_sha256: str
    observed_manifest_sha256: str
    runtime: LocalInferenceRuntimeFreeze
    candidates: tuple[FrozenModelSource, ...]

    def __post_init__(self) -> None:
        _git_revision(self.software_revision, "software_revision")
        validate_sha256(self.supersedes_v1_manifest_sha256)
        validate_sha256(self.observed_manifest_sha256)
        if not isinstance(self.runtime, LocalInferenceRuntimeFreeze):
            raise TypeError("runtime must be LocalInferenceRuntimeFreeze")
        if not self.candidates:
            raise ValueError("at least one frozen candidate is required")
        if any(not isinstance(item, FrozenModelSource) for item in self.candidates):
            raise TypeError("candidates must contain FrozenModelSource values")
        ids = tuple(item.candidate_id for item in self.candidates)
        if len(ids) != len(set(ids)):
            raise ValueError("candidate IDs must be unique")
        artifacts = tuple(item.artifact_sha256 for item in self.candidates)
        if len(artifacts) != len(set(artifacts)):
            raise ValueError("candidate artifact hashes must be unique")

    @property
    def candidate_ids(self) -> tuple[str, ...]:
        return tuple(item.candidate_id for item in self.candidates)

    def candidate(self, candidate_id: str) -> FrozenModelSource:
        _nonempty(candidate_id, "candidate_id")
        for item in self.candidates:
            if item.candidate_id == candidate_id:
                return item
        raise KeyError(candidate_id)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": LOCAL_MODEL_SOURCE_FREEZE_SCHEMA,
            "software_revision": self.software_revision,
            "supersedes_v1_manifest_sha256": self.supersedes_v1_manifest_sha256,
            "observed_manifest_sha256": self.observed_manifest_sha256,
            "runtime": self.runtime.canonical_payload(),
            "candidates": [item.canonical_payload() for item in self.candidates],
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


LOCAL_MODEL_SOURCE_FREEZE_V2 = LocalModelSourceFreeze(
    software_revision="422ba054c003b918b157b0da6729418e1fd185ce",
    supersedes_v1_manifest_sha256=(
        "7ca2c1aa898fcc657a2f3456680602449426d4d241d8d0e63f14ae391d7a06e1"
    ),
    observed_manifest_sha256=(
        "8e4a269bf966684769c0278b76d8fbf408c338d5ecb8d945d0760c03a05b7393"
    ),
    runtime=LocalInferenceRuntimeFreeze(
        release="b10361",
        upstream_commit="14e78ddef",
        platform="windows-x64",
        accelerator_backend="cuda-12.4",
        binary_archive_sha256=(
            "115fc69566deb8d1191b4f79bc31f6e8ca7a6f7a951879008f20db796909c381"
        ),
        cudart_archive_sha256=(
            "8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6"
        ),
    ),
    candidates=(
        FrozenModelSource(
            candidate_id="qwen3-8b-q8",
            quant_repository="Qwen/Qwen3-8B-GGUF",
            quant_repository_revision="7c41481f57cb95916b40956ab2f0b139b296d974",
            source_repository="Qwen/Qwen3-8B",
            source_repository_revision="b968826d9c46dd6066d109eabc6255188de91218",
            provenance=ModelArtifactProvenance.FIRST_PARTY,
            filename="Qwen3-8B-Q8_0.gguf",
            size_bytes=8_709_518_112,
            artifact_sha256=(
                "408b955510e196121c1c375201744783b5c9a43c7956d73fc78df54c66e883d6"
            ),
        ),
        FrozenModelSource(
            candidate_id="qwen2.5-coder-14b-q5km",
            quant_repository="Qwen/Qwen2.5-Coder-14B-Instruct-GGUF",
            quant_repository_revision="d0a692ef765eefbf2fabb130b3cb2e8917e3d225",
            source_repository="Qwen/Qwen2.5-Coder-14B-Instruct",
            source_repository_revision="aedcc2d42b622764e023cf882b6652e646b95671",
            provenance=ModelArtifactProvenance.FIRST_PARTY,
            filename="qwen2.5-coder-14b-instruct-q5_k_m.gguf",
            size_bytes=10_508_873_152,
            artifact_sha256=(
                "98ab25e0132e3f1e6d3554e1b64de2b5021908819b740d9c208430117e49a775"
            ),
        ),
        FrozenModelSource(
            candidate_id="gemma4-12b-it-qat-q4",
            quant_repository="google/gemma-4-12B-it-qat-q4_0-gguf",
            quant_repository_revision="29d097773436b69ff9feafd636ab4cf873786537",
            source_repository="google/gemma-4-12B",
            source_repository_revision="023679ed352de9bb66cc873c9009ce3482585c08",
            provenance=ModelArtifactProvenance.FIRST_PARTY,
            filename="gemma-4-12b-it-qat-q4_0.gguf",
            size_bytes=6_975_879_296,
            artifact_sha256=(
                "93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b"
            ),
        ),
        FrozenModelSource(
            candidate_id="devstral-24b-q4km",
            quant_repository="mistralai/Devstral-Small-2505_gguf",
            quant_repository_revision="def988cdf156b21442504f149ec0296ddbbe1e07",
            source_repository="mistralai/Devstral-Small-2505",
            source_repository_revision="c2a9d81a2989af566682b4cecc828c84556076c5",
            provenance=ModelArtifactProvenance.FIRST_PARTY,
            filename="devstralQ4_K_M.gguf",
            size_bytes=14_333_908_960,
            artifact_sha256=(
                "4a9ec4e1b7fa7b8d3b26e56a54efe251349bb67d8a623bae662353a9d84e4b9b"
            ),
        ),
        FrozenModelSource(
            candidate_id="deepseek-coder-v2-lite-q5km",
            quant_repository="bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF",
            quant_repository_revision="8f248fa2072348f77a8bc37754e470de1f61866e",
            source_repository="deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct",
            source_repository_revision="e434a23f91ba5b4923cf6c9d9a238eb4a08e3a11",
            provenance=ModelArtifactProvenance.COMMUNITY_QUANTIZATION,
            filename="DeepSeek-Coder-V2-Lite-Instruct-Q5_K_M.gguf",
            size_bytes=11_851_313_920,
            artifact_sha256=(
                "3de21719a8ffb4f6acc4b636d4ca38d882e0d0aa9a5d417106f985e0e0a4a735"
            ),
        ),
    ),
)
