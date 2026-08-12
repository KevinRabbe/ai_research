from __future__ import annotations

from dataclasses import replace

import pytest

from plural_cognition.collective.local_models import (
    LOCAL_MODEL_SOURCE_FREEZE_V2,
    FrozenModelSource,
    LocalModelSourceFreeze,
    ModelArtifactProvenance,
)


def test_frozen_local_model_pool_reconstructs_canonical_identity() -> None:
    freeze = LOCAL_MODEL_SOURCE_FREEZE_V2
    assert freeze.sha256 == (
        "e8b22970d505ed0ffb8ea07a122c63d497db89454745083d9e69fa6950942248"
    )
    assert freeze.observed_manifest_sha256 == (
        "8e4a269bf966684769c0278b76d8fbf408c338d5ecb8d945d0760c03a05b7393"
    )
    assert freeze.supersedes_v1_manifest_sha256 == (
        "7ca2c1aa898fcc657a2f3456680602449426d4d241d8d0e63f14ae391d7a06e1"
    )
    assert freeze.candidate_ids == (
        "qwen3-8b-q8",
        "qwen2.5-coder-14b-q5km",
        "gemma4-12b-it-qat-q4",
        "devstral-24b-q4km",
        "deepseek-coder-v2-lite-q5km",
    )


def test_runtime_identity_matches_target_machine_preflight() -> None:
    runtime = LOCAL_MODEL_SOURCE_FREEZE_V2.runtime
    assert runtime.release == "b10361"
    assert runtime.upstream_commit == "14e78ddef"
    assert runtime.platform == "windows-x64"
    assert runtime.accelerator_backend == "cuda-12.4"
    assert runtime.binary_archive_sha256 == (
        "115fc69566deb8d1191b4f79bc31f6e8ca7a6f7a951879008f20db796909c381"
    )
    assert runtime.cudart_archive_sha256 == (
        "8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6"
    )


def test_download_urls_are_revision_pinned() -> None:
    for candidate in LOCAL_MODEL_SOURCE_FREEZE_V2.candidates:
        assert f"/resolve/{candidate.quant_repository_revision}/" in candidate.download_url
        assert "/resolve/main/" not in candidate.download_url
        assert candidate.filename in candidate.download_url


def test_deepseek_quantization_provenance_is_explicit() -> None:
    deepseek = LOCAL_MODEL_SOURCE_FREEZE_V2.candidate(
        "deepseek-coder-v2-lite-q5km"
    )
    assert deepseek.provenance is ModelArtifactProvenance.COMMUNITY_QUANTIZATION
    assert deepseek.quant_repository == (
        "bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF"
    )
    assert deepseek.source_repository == (
        "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct"
    )
    assert deepseek.artifact_sha256 == (
        "3de21719a8ffb4f6acc4b636d4ca38d882e0d0aa9a5d417106f985e0e0a4a735"
    )


def test_duplicate_candidate_ids_are_rejected() -> None:
    freeze = LOCAL_MODEL_SOURCE_FREEZE_V2
    with pytest.raises(ValueError, match="candidate IDs must be unique"):
        replace(freeze, candidates=(freeze.candidates[0], freeze.candidates[0]))


def test_candidate_lookup_fails_closed() -> None:
    with pytest.raises(KeyError):
        LOCAL_MODEL_SOURCE_FREEZE_V2.candidate("not-frozen")


def test_frozen_source_requires_full_repository_revisions() -> None:
    candidate = LOCAL_MODEL_SOURCE_FREEZE_V2.candidates[0]
    with pytest.raises(ValueError, match="full 40-character Git SHA"):
        replace(candidate, quant_repository_revision="main")


def test_frozen_source_rejects_nonpositive_file_size() -> None:
    candidate = LOCAL_MODEL_SOURCE_FREEZE_V2.candidates[0]
    with pytest.raises(ValueError, match="positive integer"):
        replace(candidate, size_bytes=0)


def test_frozen_source_requires_typed_provenance() -> None:
    candidate = LOCAL_MODEL_SOURCE_FREEZE_V2.candidates[0]
    with pytest.raises(TypeError, match="ModelArtifactProvenance"):
        FrozenModelSource(
            candidate_id=candidate.candidate_id,
            quant_repository=candidate.quant_repository,
            quant_repository_revision=candidate.quant_repository_revision,
            source_repository=candidate.source_repository,
            source_repository_revision=candidate.source_repository_revision,
            provenance="first-party",  # type: ignore[arg-type]
            filename=candidate.filename,
            size_bytes=candidate.size_bytes,
            artifact_sha256=candidate.artifact_sha256,
        )


def test_freeze_requires_typed_candidates() -> None:
    freeze = LOCAL_MODEL_SOURCE_FREEZE_V2
    with pytest.raises(TypeError, match="FrozenModelSource"):
        LocalModelSourceFreeze(
            software_revision=freeze.software_revision,
            supersedes_v1_manifest_sha256=freeze.supersedes_v1_manifest_sha256,
            observed_manifest_sha256=freeze.observed_manifest_sha256,
            runtime=freeze.runtime,
            candidates=(object(),),  # type: ignore[arg-type]
        )
