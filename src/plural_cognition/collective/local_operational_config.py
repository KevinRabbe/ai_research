"""Fail-closed contracts for freezing local raw-mind operational configurations."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from .content_store import validate_sha256
from .local_models import LOCAL_MODEL_SOURCE_FREEZE_V2, LocalModelSourceFreeze
from .mind import MindIdentity

LOCAL_RAW_PROTOCOL_SCHEMA = "plural-cognition-local-raw-mind-protocol-v1"
LOCAL_CANDIDATE_OPERATIONAL_CONFIG_SCHEMA = (
    "plural-cognition-local-candidate-operational-config-v1"
)
LOCAL_OPERATIONAL_CONFIG_FREEZE_SCHEMA = (
    "plural-cognition-local-operational-config-freeze-v1"
)


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


def _positive_int(value: int, field: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{field} must be a positive integer")


def _nonnegative_int(value: int, field: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")


@dataclass(frozen=True, slots=True)
class LocalRawMindProtocol:
    """Exact local llama.cpp execution settings for one raw-mind condition.

    The contract encodes the initial bakeoff invariants that must not be weakened
    after the selection split is frozen: one primary call, no retries, no
    inter-mind communication, no evaluator access, no mutable cross-task memory,
    and no plural synthesis.
    """

    context_tokens: int
    predict_tokens: int
    device: str
    gpu_layers: str
    fit: str
    split_mode: str
    main_gpu: int
    cache_type_k: str
    cache_type_v: str
    load_mode: str
    offline: bool
    temperature: float
    seed: int
    log_verbosity: int
    cpu_threads: int
    batch_tokens: int
    microbatch_tokens: int
    flash_attention: bool
    single_turn: bool = True
    max_attempts: int = 1
    cross_mind_communication: bool = False
    evaluator_access: bool = False
    mutable_memory: bool = False
    plural_synthesis: bool = False

    def __post_init__(self) -> None:
        for field, value in (
            ("context_tokens", self.context_tokens),
            ("predict_tokens", self.predict_tokens),
            ("log_verbosity", self.log_verbosity),
            ("cpu_threads", self.cpu_threads),
            ("batch_tokens", self.batch_tokens),
            ("microbatch_tokens", self.microbatch_tokens),
        ):
            _positive_int(value, field)
        _nonnegative_int(self.main_gpu, "main_gpu")
        _nonnegative_int(self.seed, "seed")
        _positive_int(self.max_attempts, "max_attempts")
        for field, value in (
            ("device", self.device),
            ("gpu_layers", self.gpu_layers),
            ("fit", self.fit),
            ("split_mode", self.split_mode),
            ("cache_type_k", self.cache_type_k),
            ("cache_type_v", self.cache_type_v),
            ("load_mode", self.load_mode),
        ):
            _nonempty(value, field)
        if type(self.temperature) not in (int, float):
            raise TypeError("temperature must be a plain int or float")
        if not math.isfinite(float(self.temperature)) or float(self.temperature) < 0:
            raise ValueError("temperature must be finite and nonnegative")
        for field, value in (
            ("offline", self.offline),
            ("flash_attention", self.flash_attention),
            ("single_turn", self.single_turn),
            ("cross_mind_communication", self.cross_mind_communication),
            ("evaluator_access", self.evaluator_access),
            ("mutable_memory", self.mutable_memory),
            ("plural_synthesis", self.plural_synthesis),
        ):
            if type(value) is not bool:
                raise TypeError(f"{field} must be bool")
        if self.single_turn is not True:
            raise ValueError("raw-mind protocol must remain single-turn")
        if self.max_attempts != 1:
            raise ValueError("raw-mind protocol must allow exactly one primary attempt")
        if self.cross_mind_communication:
            raise ValueError("raw minds cannot communicate during the initial bakeoff")
        if self.evaluator_access:
            raise ValueError("raw minds cannot access protected evaluators")
        if self.mutable_memory:
            raise ValueError("raw minds cannot carry mutable memory between tasks")
        if self.plural_synthesis:
            raise ValueError("raw-mind bakeoff cannot perform plural synthesis")
        if not self.offline:
            raise ValueError("local raw-mind execution must remain offline")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": LOCAL_RAW_PROTOCOL_SCHEMA,
            "context_tokens": self.context_tokens,
            "predict_tokens": self.predict_tokens,
            "device": self.device,
            "gpu_layers": self.gpu_layers,
            "fit": self.fit,
            "split_mode": self.split_mode,
            "main_gpu": self.main_gpu,
            "cache_type_k": self.cache_type_k,
            "cache_type_v": self.cache_type_v,
            "load_mode": self.load_mode,
            "offline": self.offline,
            "temperature": float(self.temperature),
            "seed": self.seed,
            "log_verbosity": self.log_verbosity,
            "cpu_threads": self.cpu_threads,
            "batch_tokens": self.batch_tokens,
            "microbatch_tokens": self.microbatch_tokens,
            "flash_attention": self.flash_attention,
            "single_turn": self.single_turn,
            "max_attempts": self.max_attempts,
            "cross_mind_communication": self.cross_mind_communication,
            "evaluator_access": self.evaluator_access,
            "mutable_memory": self.mutable_memory,
            "plural_synthesis": self.plural_synthesis,
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()


@dataclass(frozen=True, slots=True)
class LocalCandidateOperationalConfig:
    """Content-addressed producer configuration for one frozen local model."""

    candidate_id: str
    model_source_freeze_sha256: str
    model_source_sha256: str
    runtime_sha256: str
    protocol: LocalRawMindProtocol
    prompt_protocol_sha256: str
    output_contract_sha256: str
    resource_budget_sha256: str

    def __post_init__(self) -> None:
        _nonempty(self.candidate_id, "candidate_id")
        for digest in (
            self.model_source_freeze_sha256,
            self.model_source_sha256,
            self.runtime_sha256,
            self.prompt_protocol_sha256,
            self.output_contract_sha256,
            self.resource_budget_sha256,
        ):
            validate_sha256(digest)
        if not isinstance(self.protocol, LocalRawMindProtocol):
            raise TypeError("protocol must be LocalRawMindProtocol")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": LOCAL_CANDIDATE_OPERATIONAL_CONFIG_SCHEMA,
            "candidate_id": self.candidate_id,
            "model_source_freeze_sha256": self.model_source_freeze_sha256,
            "model_source_sha256": self.model_source_sha256,
            "runtime_sha256": self.runtime_sha256,
            "protocol": self.protocol.canonical_payload(),
            "prompt_protocol_sha256": self.prompt_protocol_sha256,
            "output_contract_sha256": self.output_contract_sha256,
            "resource_budget_sha256": self.resource_budget_sha256,
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()

    def validate_against(
        self,
        source_freeze: LocalModelSourceFreeze = LOCAL_MODEL_SOURCE_FREEZE_V2,
    ) -> None:
        if self.model_source_freeze_sha256 != source_freeze.sha256:
            raise ValueError("operational config is bound to a different model-source freeze")
        if self.runtime_sha256 != source_freeze.runtime.sha256:
            raise ValueError("operational config runtime identity drifted")
        source = source_freeze.candidate(self.candidate_id)
        if self.model_source_sha256 != source.sha256:
            raise ValueError("operational config model-source identity drifted")

    def mind_identity(
        self,
        source_freeze: LocalModelSourceFreeze = LOCAL_MODEL_SOURCE_FREEZE_V2,
    ) -> MindIdentity:
        self.validate_against(source_freeze)
        source = source_freeze.candidate(self.candidate_id)
        runtime = source_freeze.runtime
        return MindIdentity(
            mind_id=self.candidate_id,
            backend_family=f"llama.cpp-{runtime.release}-{runtime.accelerator_backend}",
            model_id=f"{source.quant_repository}/{source.filename}",
            model_revision=source.artifact_sha256,
            configuration_sha256=self.sha256,
        )


@dataclass(frozen=True, slots=True)
class LocalOperationalConfigFreeze:
    """Final candidate operational identities frozen after calibration."""

    model_source_freeze_sha256: str
    calibration_evidence_sha256: str
    configs: tuple[LocalCandidateOperationalConfig, ...]

    def __post_init__(self) -> None:
        validate_sha256(self.model_source_freeze_sha256)
        validate_sha256(self.calibration_evidence_sha256)
        if not self.configs:
            raise ValueError("at least one operational config is required")
        if any(not isinstance(item, LocalCandidateOperationalConfig) for item in self.configs):
            raise TypeError("configs must contain LocalCandidateOperationalConfig values")
        candidate_ids = tuple(item.candidate_id for item in self.configs)
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("operational config candidate IDs must be unique")
        config_hashes = tuple(item.sha256 for item in self.configs)
        if len(config_hashes) != len(set(config_hashes)):
            raise ValueError("operational config hashes must be unique")

    @property
    def candidate_ids(self) -> tuple[str, ...]:
        return tuple(item.candidate_id for item in self.configs)

    def config(self, candidate_id: str) -> LocalCandidateOperationalConfig:
        _nonempty(candidate_id, "candidate_id")
        for item in self.configs:
            if item.candidate_id == candidate_id:
                return item
        raise KeyError(candidate_id)

    def validate_against(
        self,
        source_freeze: LocalModelSourceFreeze = LOCAL_MODEL_SOURCE_FREEZE_V2,
    ) -> None:
        if self.model_source_freeze_sha256 != source_freeze.sha256:
            raise ValueError("operational freeze is bound to a different model-source freeze")
        for config in self.configs:
            config.validate_against(source_freeze)
            if config.model_source_freeze_sha256 != self.model_source_freeze_sha256:
                raise ValueError("candidate config does not match operational freeze source")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": LOCAL_OPERATIONAL_CONFIG_FREEZE_SCHEMA,
            "model_source_freeze_sha256": self.model_source_freeze_sha256,
            "calibration_evidence_sha256": self.calibration_evidence_sha256,
            "configs": [item.canonical_payload() for item in self.configs],
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()
