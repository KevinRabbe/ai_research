"""Target-free checkpoint generation artifacts and candidate-pool assembly."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Sequence

import torch
from torch import nn

from plural_cognition.boolean_world import (
    PublicTask,
    canonical_text,
    decode_public_task,
    encode_public_task,
    parse_canonical_text,
)
from plural_cognition.inference import (
    GenerationResult,
    greedy_generate_mechanism,
    sample_generate_mechanism,
)
from plural_cognition.validation import derive_validation_sampling_seed

from .candidate_pool import (
    CandidatePoolTask,
    FrozenCandidate,
    FrozenCandidatePool,
    GenerationSource,
)


@dataclass(frozen=True, slots=True)
class TargetFreeGenerationCase:
    case_index: int
    public_task_token_ids: tuple[int, ...]
    valid: bool
    expression_text: str | None
    generated_token_ids: tuple[int, ...]
    error: str | None

    def __post_init__(self) -> None:
        if self.case_index < 0:
            raise ValueError("generation case_index must not be negative")
        if not self.public_task_token_ids:
            raise ValueError("generation case requires public task token IDs")
        public = decode_public_task(self.public_task_token_ids)
        if self.valid:
            if not isinstance(self.expression_text, str) or not self.expression_text:
                raise ValueError("valid generation case requires expression")
            if self.error is not None:
                raise ValueError("valid generation case cannot contain error")
            parsed = parse_canonical_text(
                self.expression_text,
                allowed_variables=public.variable_order,
            )
            if canonical_text(parsed) != self.expression_text:
                raise ValueError("generation expression is not canonical")
        else:
            if self.expression_text is not None:
                raise ValueError("invalid generation case cannot contain expression")
            if not isinstance(self.error, str) or not self.error:
                raise ValueError("invalid generation case requires error")
        if any(type(token) is not int or token < 0 for token in self.generated_token_ids):
            raise ValueError("generated token IDs must be nonnegative integers")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "case_index": self.case_index,
            "public_task_token_ids": list(self.public_task_token_ids),
            "valid": self.valid,
            "expression": self.expression_text,
            "generated_token_ids": list(self.generated_token_ids),
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class TargetFreeGenerationArtifact:
    execution_sha256: str
    checkpoint_sha256: str
    task_shard_manifest_sha256s: tuple[str, ...]
    source: GenerationSource
    max_new_tokens: int
    cases: tuple[TargetFreeGenerationCase, ...]

    SCHEMA = "plural-cognition-si-target-free-generation-v1"

    def __post_init__(self) -> None:
        for field in ("execution_sha256", "checkpoint_sha256"):
            value = getattr(self, field)
            if not isinstance(value, str) or len(value) != 64:
                raise ValueError(f"{field} must contain 64 hexadecimal characters")
            int(value, 16)
        if not self.task_shard_manifest_sha256s:
            raise ValueError("generation artifact requires task-shard identities")
        for value in self.task_shard_manifest_sha256s:
            if not isinstance(value, str) or len(value) != 64:
                raise ValueError("task-shard identity must contain 64 characters")
            int(value, 16)
        if type(self.max_new_tokens) is not int or self.max_new_tokens < 1:
            raise ValueError("max_new_tokens must be positive")
        if not self.cases:
            raise ValueError("generation artifact requires cases")
        if tuple(case.case_index for case in self.cases) != tuple(range(len(self.cases))):
            raise ValueError("generation cases must be contiguous from zero")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "schema": self.SCHEMA,
            "execution_sha256": self.execution_sha256,
            "checkpoint_sha256": self.checkpoint_sha256,
            "task_shard_manifest_sha256s": list(
                self.task_shard_manifest_sha256s
            ),
            "source": self.source.canonical_payload(),
            "max_new_tokens": self.max_new_tokens,
            "case_count": len(self.cases),
            "cases": [case.canonical_payload() for case in self.cases],
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_payload(cls, payload: object) -> TargetFreeGenerationArtifact:
        if not isinstance(payload, dict):
            raise ValueError("generation artifact payload must be an object")
        expected = {
            "schema",
            "execution_sha256",
            "checkpoint_sha256",
            "task_shard_manifest_sha256s",
            "source",
            "max_new_tokens",
            "case_count",
            "cases",
        }
        if set(payload) != expected or payload["schema"] != cls.SCHEMA:
            raise ValueError("generation artifact payload has wrong fields or schema")
        source_payload = payload["source"]
        if not isinstance(source_payload, dict) or set(source_payload) != {
            "source_id",
            "mode",
            "sampling_seed",
            "temperature",
            "top_k",
        }:
            raise ValueError("generation source payload is invalid")
        raw_cases = payload["cases"]
        if not isinstance(raw_cases, list) or payload["case_count"] != len(raw_cases):
            raise ValueError("generation artifact case count is inconsistent")
        try:
            artifact = cls(
                payload["execution_sha256"],
                payload["checkpoint_sha256"],
                tuple(payload["task_shard_manifest_sha256s"]),
                GenerationSource(
                    source_payload["source_id"],
                    source_payload["mode"],
                    source_payload["sampling_seed"],
                    source_payload["temperature"],
                    source_payload["top_k"],
                ),
                payload["max_new_tokens"],
                tuple(
                    TargetFreeGenerationCase(
                        case["case_index"],
                        tuple(case["public_task_token_ids"]),
                        case["valid"],
                        case["expression"],
                        tuple(case["generated_token_ids"]),
                        case["error"],
                    )
                    for case in raw_cases
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid generation artifact payload") from exc
        if artifact.canonical_payload() != payload:
            raise ValueError("generation artifact payload is not canonical")
        return artifact


def _case_from_result(
    case_index: int,
    task: PublicTask,
    result: GenerationResult,
) -> TargetFreeGenerationCase:
    return TargetFreeGenerationCase(
        case_index,
        tuple(encode_public_task(task)),
        result.valid,
        None if result.expression is None else canonical_text(result.expression),
        result.generated_token_ids,
        result.error,
    )


def generate_target_free_artifact(
    model: nn.Module,
    public_tasks: Sequence[PublicTask],
    *,
    device: torch.device,
    execution_sha256: str,
    checkpoint_sha256: str,
    task_shard_manifest_sha256s: tuple[str, ...],
    source: GenerationSource,
    max_new_tokens: int = 64,
) -> TargetFreeGenerationArtifact:
    """Generate fixed paths without accepting or decoding any target expression."""

    if not public_tasks:
        raise ValueError("target-free generation requires public tasks")
    cases: list[TargetFreeGenerationCase] = []
    for case_index, task in enumerate(public_tasks):
        if source.mode == "greedy":
            result = greedy_generate_mechanism(
                model,
                task,
                device=device,
                max_new_tokens=max_new_tokens,
            )
        else:
            if source.sampling_seed is None or source.temperature is None:
                raise AssertionError("sampled source lost sampling parameters")
            result = sample_generate_mechanism(
                model,
                task,
                device=device,
                seed=derive_validation_sampling_seed(
                    source.sampling_seed,
                    case_index,
                ),
                temperature=source.temperature,
                top_k=source.top_k,
                max_new_tokens=max_new_tokens,
            )
        cases.append(_case_from_result(case_index, task, result))
    return TargetFreeGenerationArtifact(
        execution_sha256,
        checkpoint_sha256,
        task_shard_manifest_sha256s,
        source,
        max_new_tokens,
        tuple(cases),
    )


def build_pool_from_generation_artifacts(
    artifacts: Sequence[TargetFreeGenerationArtifact],
) -> FrozenCandidatePool:
    """Combine target-free generation paths into one immutable candidate pool."""

    if not artifacts:
        raise ValueError("candidate-pool construction requires generation artifacts")
    ordered = tuple(sorted(artifacts, key=lambda item: item.source.source_id))
    if len({item.source.source_id for item in ordered}) != len(ordered):
        raise ValueError("generation source IDs must be unique")
    if len({item.execution_sha256 for item in ordered}) != 1:
        raise ValueError("generation artifacts use different executions")
    if len({item.checkpoint_sha256 for item in ordered}) != 1:
        raise ValueError("generation artifacts use different checkpoints")
    if len({item.task_shard_manifest_sha256s for item in ordered}) != 1:
        raise ValueError("generation artifacts use different task shards")
    if len({len(item.cases) for item in ordered}) != 1:
        raise ValueError("generation artifacts contain different case counts")
    if len({item.max_new_tokens for item in ordered}) != 1:
        raise ValueError("generation artifacts use different token ceilings")

    case_count = len(ordered[0].cases)
    tasks: list[CandidatePoolTask] = []
    for case_index in range(case_count):
        token_sets = {
            artifact.cases[case_index].public_task_token_ids for artifact in ordered
        }
        if len(token_sets) != 1:
            raise ValueError("generation artifacts contain different public tasks")
        candidates = tuple(
            FrozenCandidate(
                artifact.source.source_id,
                artifact.cases[case_index].valid,
                artifact.cases[case_index].expression_text,
                artifact.cases[case_index].generated_token_ids,
                artifact.cases[case_index].error,
            )
            for artifact in ordered
        )
        tasks.append(
            CandidatePoolTask(
                case_index,
                token_sets.pop(),
                candidates,
            )
        )
    return FrozenCandidatePool(
        ordered[0].checkpoint_sha256,
        ordered[0].execution_sha256,
        ordered[0].task_shard_manifest_sha256s,
        tuple(item.source for item in ordered),
        tuple(tasks),
    )
