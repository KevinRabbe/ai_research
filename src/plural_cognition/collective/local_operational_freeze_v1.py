"""Final local operational configuration frozen after calibration.

This module is the empirical transition from the preparatory v1 configuration
contract to the exact raw-mind settings that will be used for the untouched
selection bakeoff.  It binds the completed V8 5x6 calibration matrix and the
terminal V9 Gemma resource probe, preserves all five source-frozen candidates,
and does not inspect or construct selection material.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from .content_store import validate_sha256
from .local_models import LOCAL_MODEL_SOURCE_FREEZE_V2, LocalModelSourceFreeze
from .mind import MindIdentity

FINAL_LOCAL_RAW_PROTOCOL_SCHEMA = "plural-cognition-final-local-raw-mind-protocol-v2"
FINAL_LOCAL_CANDIDATE_CONFIG_SCHEMA = "plural-cognition-final-local-candidate-operational-config-v2"
FINAL_LOCAL_OPERATIONAL_FREEZE_SCHEMA = "plural-cognition-final-local-operational-config-freeze-v2"
FINAL_CALIBRATION_EVIDENCE_SCHEMA = "plural-cognition-local-calibration-evidence-freeze-v1"
FINAL_PROMPT_PROTOCOL_SCHEMA = "plural-cognition-local-structured-edit-prompt-protocol-v1"
FINAL_OUTPUT_CONTRACT_SCHEMA = "plural-cognition-local-structured-edit-output-contract-v1"
FINAL_RESOURCE_BUDGET_SCHEMA = "plural-cognition-local-resource-budget-v1"

V8_SOFTWARE_REVISION = "d0fdb8b65b25a439ac296fd711cd7927a48d323e"
V8_REPORT_SHA256 = "83a8f4fb40195118d6eb2194bbf193cdd9af79793eec3cd53395aa6c20d4d437"
V8_PROTOCOL_SHA256 = "c4eb980a4cf882f6621837a5cc205a143722459915358f8d8997d3c11ba79f82"
V9_SOFTWARE_REVISION = "b19f387b6a4e30ec128064c26a741cd2b14e9f41"
V9_REPORT_SHA256 = "32dc48fe87c082e6e11f1fdad2fc4dd9d6f8bc56672f6e5f87f5aab68dd03b19"
V9_PROTOCOL_SHA256 = "f0a90df09b8d86b61fd8c14f1625fdfaae71b5dea7cb68b5ed7d92601db0c74c"

FINAL_CANDIDATE_IDS = (
    "qwen3-8b-q8",
    "qwen2.5-coder-14b-q5km",
    "gemma4-12b-it-qat-q4",
    "devstral-24b-q4km",
    "deepseek-coder-v2-lite-q5km",
)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_json(payload: Any) -> str:
    return sha256(_canonical_json_bytes(payload)).hexdigest()


def final_calibration_evidence_payload() -> dict[str, Any]:
    return {
        "schema": FINAL_CALIBRATION_EVIDENCE_SCHEMA,
        "v8_matrix": {
            "software_revision": V8_SOFTWARE_REVISION,
            "report_sha256": V8_REPORT_SHA256,
            "protocol_sha256": V8_PROTOCOL_SHA256,
            "candidate_count": 5,
            "task_count": 6,
            "result_count": 30,
            "parsed_count": 24,
            "solved_count": 20,
        },
        "v9_gemma_probe": {
            "software_revision": V9_SOFTWARE_REVISION,
            "report_sha256": V9_REPORT_SHA256,
            "protocol_sha256": V9_PROTOCOL_SHA256,
            "candidate_count": 1,
            "task_count": 6,
            "result_count": 6,
            "parsed_count": 0,
            "solved_count": 0,
            "decision": "reject-gemma-4096-override-retain-shared-2048-v1",
        },
    }


FINAL_CALIBRATION_EVIDENCE_SHA256 = _sha256_json(final_calibration_evidence_payload())


def final_prompt_protocol_payload() -> dict[str, Any]:
    return {
        "schema": FINAL_PROMPT_PROTOCOL_SCHEMA,
        "implementation_revision": V8_SOFTWARE_REVISION,
        "module": "plural_cognition.collective.local_raw_calibration_v8",
        "builder": "build_solver_prompt_v8",
        "candidate_contract": "exact-replace-json-v1",
        "prompt_transport": "literal-argv-no-escape-v1",
        "terminal_prompt_lf": False,
        "conversation_mode": True,
        "assistant_output_channel": "llama-cli-output-file-single-turn-v1",
        "reasoning_role": "preserved-diagnostic-not-answer",
    }


FINAL_PROMPT_PROTOCOL_SHA256 = _sha256_json(final_prompt_protocol_payload())


def final_output_contract_payload() -> dict[str, Any]:
    return {
        "schema": FINAL_OUTPUT_CONTRACT_SCHEMA,
        "candidate_output": "exact-replace-json-v1",
        "interpreter": "deterministic-canonical-unified-diff-v1",
        "structured_edit_max_count": 32,
        "max_output_bytes": 65536,
        "path_scope": "solver-visible-existing-files-only-v1",
        "old_match": "exactly-once-current-file-state-v1",
        "edit_application": "listed-order-v1",
        "canonical_patch_context_lines": 3,
        "patch_validation": "qualified-docker-unified-diff-grammar-v1",
        "candidate_output_repair": False,
    }


FINAL_OUTPUT_CONTRACT_SHA256 = _sha256_json(final_output_contract_payload())


def final_resource_budget_payload() -> dict[str, Any]:
    return {
        "schema": FINAL_RESOURCE_BUDGET_SCHEMA,
        "context_tokens": 4096,
        "predict_tokens": 2048,
        "device": "CUDA0",
        "gpu_layers": "all",
        "fit": "off",
        "split_mode": "none",
        "main_gpu": 0,
        "cache_type_k": "f16",
        "cache_type_v": "f16",
        "load_mode": "mmap",
        "offline": True,
        "temperature": 0.0,
        "seed": 1,
        "log_verbosity": 4,
        "cpu_threads": 16,
        "cpu_threads_batch": 16,
        "batch_tokens": 2048,
        "microbatch_tokens": 512,
        "flash_attention_mode": "auto",
        "single_turn": True,
        "max_attempts": 1,
    }


FINAL_RESOURCE_BUDGET_SHA256 = _sha256_json(final_resource_budget_payload())


@dataclass(frozen=True, slots=True)
class FinalLocalRawMindProtocol:
    """Exact raw-mind execution settings frozen before selection material exists."""

    context_tokens: int = 4096
    predict_tokens: int = 2048
    device: str = "CUDA0"
    gpu_layers: str = "all"
    fit: str = "off"
    split_mode: str = "none"
    main_gpu: int = 0
    cache_type_k: str = "f16"
    cache_type_v: str = "f16"
    load_mode: str = "mmap"
    offline: bool = True
    temperature: float = 0.0
    seed: int = 1
    log_verbosity: int = 4
    cpu_threads: int = 16
    cpu_threads_batch: int = 16
    batch_tokens: int = 2048
    microbatch_tokens: int = 512
    flash_attention_mode: str = "auto"
    conversation_mode: bool = True
    simple_io: bool = True
    escape_processing: bool = False
    terminal_prompt_lf: bool = False
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
            ("cpu_threads_batch", self.cpu_threads_batch),
            ("batch_tokens", self.batch_tokens),
            ("microbatch_tokens", self.microbatch_tokens),
            ("max_attempts", self.max_attempts),
        ):
            if type(value) is not int or value < 1:
                raise ValueError(f"{field} must be a positive integer")
        if type(self.main_gpu) is not int or self.main_gpu < 0:
            raise ValueError("main_gpu must be a nonnegative integer")
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError("seed must be a nonnegative integer")
        if type(self.temperature) not in (int, float) or not math.isfinite(float(self.temperature)):
            raise ValueError("temperature must be finite")
        if float(self.temperature) < 0:
            raise ValueError("temperature must be nonnegative")
        if self.flash_attention_mode not in {"auto", "on", "off"}:
            raise ValueError("flash_attention_mode must be auto, on, or off")
        if self.max_attempts != 1:
            raise ValueError("raw-mind protocol must allow exactly one primary attempt")
        if not self.single_turn or not self.conversation_mode or not self.simple_io:
            raise ValueError("final raw-mind protocol must remain single-turn conversation simple-io")
        if self.escape_processing or self.terminal_prompt_lf:
            raise ValueError("final prompt transport must preserve literal bytes without terminal LF")
        if not self.offline:
            raise ValueError("final raw-mind execution must remain offline")
        if self.cross_mind_communication or self.evaluator_access or self.mutable_memory or self.plural_synthesis:
            raise ValueError("final raw-mind protocol cannot expose privileged or plural channels")

    def canonical_payload(self) -> dict[str, Any]:
        payload = final_resource_budget_payload()
        payload.update(
            {
                "schema": FINAL_LOCAL_RAW_PROTOCOL_SCHEMA,
                "conversation_mode": self.conversation_mode,
                "simple_io": self.simple_io,
                "escape_processing": self.escape_processing,
                "terminal_prompt_lf": self.terminal_prompt_lf,
                "cross_mind_communication": self.cross_mind_communication,
                "evaluator_access": self.evaluator_access,
                "mutable_memory": self.mutable_memory,
                "plural_synthesis": self.plural_synthesis,
            }
        )
        return payload

    @property
    def sha256(self) -> str:
        return _sha256_json(self.canonical_payload())


FINAL_RAW_MIND_PROTOCOL = FinalLocalRawMindProtocol()


@dataclass(frozen=True, slots=True)
class FinalLocalCandidateOperationalConfig:
    candidate_id: str
    model_source_freeze_sha256: str
    model_source_sha256: str
    runtime_sha256: str
    protocol: FinalLocalRawMindProtocol
    prompt_protocol_sha256: str
    output_contract_sha256: str
    resource_budget_sha256: str

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": FINAL_LOCAL_CANDIDATE_CONFIG_SCHEMA,
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
        return _sha256_json(self.canonical_payload())

    def validate_against(self, source_freeze: LocalModelSourceFreeze = LOCAL_MODEL_SOURCE_FREEZE_V2) -> None:
        for digest in (
            self.model_source_freeze_sha256,
            self.model_source_sha256,
            self.runtime_sha256,
            self.prompt_protocol_sha256,
            self.output_contract_sha256,
            self.resource_budget_sha256,
        ):
            validate_sha256(digest)
        if self.candidate_id not in FINAL_CANDIDATE_IDS:
            raise ValueError("candidate is outside the frozen five-candidate source pool")
        if self.model_source_freeze_sha256 != source_freeze.sha256:
            raise ValueError("candidate config model-source freeze drifted")
        if self.runtime_sha256 != source_freeze.runtime.sha256:
            raise ValueError("candidate config runtime drifted")
        if self.model_source_sha256 != source_freeze.candidate(self.candidate_id).sha256:
            raise ValueError("candidate config model-source identity drifted")
        if self.protocol != FINAL_RAW_MIND_PROTOCOL:
            raise ValueError("candidate config raw protocol drifted")
        if self.prompt_protocol_sha256 != FINAL_PROMPT_PROTOCOL_SHA256:
            raise ValueError("candidate config prompt protocol drifted")
        if self.output_contract_sha256 != FINAL_OUTPUT_CONTRACT_SHA256:
            raise ValueError("candidate config output contract drifted")
        if self.resource_budget_sha256 != FINAL_RESOURCE_BUDGET_SHA256:
            raise ValueError("candidate config resource budget drifted")

    def mind_identity(self, source_freeze: LocalModelSourceFreeze = LOCAL_MODEL_SOURCE_FREEZE_V2) -> MindIdentity:
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


def _candidate_config(candidate_id: str) -> FinalLocalCandidateOperationalConfig:
    freeze = LOCAL_MODEL_SOURCE_FREEZE_V2
    return FinalLocalCandidateOperationalConfig(
        candidate_id=candidate_id,
        model_source_freeze_sha256=freeze.sha256,
        model_source_sha256=freeze.candidate(candidate_id).sha256,
        runtime_sha256=freeze.runtime.sha256,
        protocol=FINAL_RAW_MIND_PROTOCOL,
        prompt_protocol_sha256=FINAL_PROMPT_PROTOCOL_SHA256,
        output_contract_sha256=FINAL_OUTPUT_CONTRACT_SHA256,
        resource_budget_sha256=FINAL_RESOURCE_BUDGET_SHA256,
    )


@dataclass(frozen=True, slots=True)
class FinalLocalOperationalConfigFreeze:
    model_source_freeze_sha256: str
    calibration_evidence_sha256: str
    configs: tuple[FinalLocalCandidateOperationalConfig, ...]

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": FINAL_LOCAL_OPERATIONAL_FREEZE_SCHEMA,
            "model_source_freeze_sha256": self.model_source_freeze_sha256,
            "calibration_evidence_sha256": self.calibration_evidence_sha256,
            "configs": [item.canonical_payload() for item in self.configs],
        }

    @property
    def sha256(self) -> str:
        return _sha256_json(self.canonical_payload())

    @property
    def candidate_ids(self) -> tuple[str, ...]:
        return tuple(item.candidate_id for item in self.configs)

    def validate_against(self, source_freeze: LocalModelSourceFreeze = LOCAL_MODEL_SOURCE_FREEZE_V2) -> None:
        validate_sha256(self.model_source_freeze_sha256)
        validate_sha256(self.calibration_evidence_sha256)
        if self.model_source_freeze_sha256 != source_freeze.sha256:
            raise ValueError("final operational freeze model-source identity drifted")
        if self.calibration_evidence_sha256 != FINAL_CALIBRATION_EVIDENCE_SHA256:
            raise ValueError("final operational freeze calibration evidence drifted")
        if self.candidate_ids != FINAL_CANDIDATE_IDS:
            raise ValueError("final operational freeze must preserve all five frozen candidates in order")
        if len({item.sha256 for item in self.configs}) != len(self.configs):
            raise ValueError("final candidate operational config hashes must be unique")
        for config in self.configs:
            config.validate_against(source_freeze)


FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1 = FinalLocalOperationalConfigFreeze(
    model_source_freeze_sha256=LOCAL_MODEL_SOURCE_FREEZE_V2.sha256,
    calibration_evidence_sha256=FINAL_CALIBRATION_EVIDENCE_SHA256,
    configs=tuple(_candidate_config(candidate_id) for candidate_id in FINAL_CANDIDATE_IDS),
)
FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.validate_against()
