"""Immutable target-free candidate pools for architectural evolution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Sequence

from plural_cognition.boolean_world import (
    PublicTask,
    canonical_text,
    decode_public_task,
    encode_public_task,
    parse_canonical_text,
)


class CandidatePoolError(ValueError):
    pass


def _hex64(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise CandidatePoolError(f"{field} must contain 64 hexadecimal characters")
    try:
        int(value, 16)
    except ValueError as exc:
        raise CandidatePoolError(f"{field} must be hexadecimal") from exc
    return value


def _plain_int(value: Any, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise CandidatePoolError(f"{field} must be an integer >= {minimum}")
    return value


@dataclass(frozen=True, slots=True, order=True)
class GenerationSource:
    source_id: str
    mode: str
    sampling_seed: int | None
    temperature: float | None
    top_k: int | None

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("source_id must not be empty")
        if self.mode not in {"greedy", "sampled"}:
            raise ValueError("generation mode must be greedy or sampled")
        if self.mode == "greedy":
            if any(
                value is not None
                for value in (self.sampling_seed, self.temperature, self.top_k)
            ):
                raise ValueError("greedy source cannot contain sampling parameters")
        else:
            if type(self.sampling_seed) is not int:
                raise ValueError("sampled source requires an integer seed")
            if type(self.temperature) not in (int, float) or self.temperature <= 0.0:
                raise ValueError("sampled source requires positive temperature")
            if self.top_k is not None and (
                type(self.top_k) is not int or self.top_k < 1
            ):
                raise ValueError("sampled source top_k must be positive")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "mode": self.mode,
            "sampling_seed": self.sampling_seed,
            "temperature": self.temperature,
            "top_k": self.top_k,
        }


@dataclass(frozen=True, slots=True, order=True)
class FrozenCandidate:
    source_id: str
    valid: bool
    expression_text: str | None
    generated_token_ids: tuple[int, ...]
    error: str | None

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("candidate source_id must not be empty")
        if any(type(token) is not int or token < 0 for token in self.generated_token_ids):
            raise ValueError("candidate token IDs must be nonnegative integers")
        if self.valid:
            if not self.generated_token_ids:
                raise ValueError("valid candidate token sequence must not be empty")
            if not isinstance(self.expression_text, str) or not self.expression_text:
                raise ValueError("valid candidate requires an expression")
            if self.error is not None:
                raise ValueError("valid candidate cannot contain an error")
        else:
            if self.expression_text is not None:
                raise ValueError("invalid candidate cannot contain an expression")
            if not isinstance(self.error, str) or not self.error:
                raise ValueError("invalid candidate requires an error")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "valid": self.valid,
            "expression": self.expression_text,
            "generated_token_ids": list(self.generated_token_ids),
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class CandidatePoolTask:
    case_index: int
    public_task_token_ids: tuple[int, ...]
    candidates: tuple[FrozenCandidate, ...]

    def __post_init__(self) -> None:
        if self.case_index < 0:
            raise ValueError("case_index must not be negative")
        if not self.public_task_token_ids:
            raise ValueError("public task token IDs must not be empty")
        if not self.candidates:
            raise ValueError("candidate-pool task must contain candidates")
        source_ids = tuple(candidate.source_id for candidate in self.candidates)
        if source_ids != tuple(sorted(source_ids)):
            raise ValueError("task candidates must be ordered by source_id")
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("task candidate source IDs must be unique")

    @property
    def public_task(self) -> PublicTask:
        return decode_public_task(self.public_task_token_ids)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "case_index": self.case_index,
            "public_task_token_ids": list(self.public_task_token_ids),
            "candidates": [candidate.canonical_payload() for candidate in self.candidates],
        }


@dataclass(frozen=True, slots=True)
class FrozenCandidatePool:
    checkpoint_sha256: str
    execution_sha256: str
    task_shard_manifest_sha256s: tuple[str, ...]
    sources: tuple[GenerationSource, ...]
    tasks: tuple[CandidatePoolTask, ...]

    SCHEMA = "plural-cognition-si-candidate-pool-v1"

    def __post_init__(self) -> None:
        _hex64(self.checkpoint_sha256, "checkpoint_sha256")
        _hex64(self.execution_sha256, "execution_sha256")
        if not self.task_shard_manifest_sha256s:
            raise ValueError("candidate pool requires task-shard identities")
        for value in self.task_shard_manifest_sha256s:
            _hex64(value, "task shard identity")
        if not self.sources or not self.tasks:
            raise ValueError("candidate pool requires sources and tasks")
        if self.sources != tuple(sorted(self.sources)):
            raise ValueError("candidate-pool sources must be sorted")
        source_ids = tuple(source.source_id for source in self.sources)
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("candidate-pool source IDs must be unique")
        if tuple(task.case_index for task in self.tasks) != tuple(range(len(self.tasks))):
            raise ValueError("candidate-pool case indices must be contiguous from zero")
        expected_sources = set(source_ids)
        for task in self.tasks:
            if {item.source_id for item in task.candidates} != expected_sources:
                raise ValueError("every task must contain exactly one path from every source")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "schema": self.SCHEMA,
            "checkpoint_sha256": self.checkpoint_sha256,
            "execution_sha256": self.execution_sha256,
            "task_shard_manifest_sha256s": list(
                self.task_shard_manifest_sha256s
            ),
            "sources": [source.canonical_payload() for source in self.sources],
            "tasks": [task.canonical_payload() for task in self.tasks],
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
    def from_payload(cls, payload: object) -> FrozenCandidatePool:
        if not isinstance(payload, dict):
            raise CandidatePoolError("candidate-pool payload must be an object")
        expected = {
            "schema",
            "checkpoint_sha256",
            "execution_sha256",
            "task_shard_manifest_sha256s",
            "sources",
            "tasks",
        }
        if set(payload) != expected or payload["schema"] != cls.SCHEMA:
            raise CandidatePoolError("candidate-pool payload has wrong fields or schema")
        try:
            sources = tuple(
                GenerationSource(
                    item["source_id"],
                    item["mode"],
                    item["sampling_seed"],
                    item["temperature"],
                    item["top_k"],
                )
                for item in payload["sources"]
            )
            tasks = tuple(
                CandidatePoolTask(
                    item["case_index"],
                    tuple(item["public_task_token_ids"]),
                    tuple(
                        FrozenCandidate(
                            candidate["source_id"],
                            candidate["valid"],
                            candidate["expression"],
                            tuple(candidate["generated_token_ids"]),
                            candidate["error"],
                        )
                        for candidate in item["candidates"]
                    ),
                )
                for item in payload["tasks"]
            )
            pool = cls(
                payload["checkpoint_sha256"],
                payload["execution_sha256"],
                tuple(payload["task_shard_manifest_sha256s"]),
                sources,
                tasks,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise CandidatePoolError("invalid candidate-pool payload") from exc
        if pool.canonical_payload() != payload:
            raise CandidatePoolError("candidate-pool payload is not canonical")
        return pool


def _source_from_generation(generation: object) -> GenerationSource:
    if not isinstance(generation, dict) or set(generation) != {
        "mode",
        "sampling_seed",
        "temperature",
        "top_k",
    }:
        raise CandidatePoolError("evaluation generation protocol is invalid")
    mode = generation["mode"]
    seed = generation["sampling_seed"]
    temperature = generation["temperature"]
    top_k = generation["top_k"]
    if mode == "greedy":
        source_id = "greedy"
    elif mode == "sampled":
        if type(seed) is not int:
            raise CandidatePoolError("sampled evaluation requires integer seed")
        source_id = f"sample-{seed}"
    else:
        raise CandidatePoolError("unsupported evaluation generation mode")
    try:
        return GenerationSource(source_id, mode, seed, temperature, top_k)
    except ValueError as exc:
        raise CandidatePoolError("invalid generation protocol") from exc


def build_frozen_candidate_pool(
    public_tasks: Sequence[PublicTask],
    evaluation_payloads: Sequence[object],
) -> FrozenCandidatePool:
    """Combine same-checkpoint evaluation artifacts into one target-free pool."""

    if not public_tasks or not evaluation_payloads:
        raise CandidatePoolError("candidate-pool construction requires tasks and evaluations")
    evaluations: list[tuple[GenerationSource, dict[str, Any]]] = []
    checkpoint_hashes: set[str] = set()
    execution_hashes: set[str] = set()
    shard_sets: set[tuple[str, ...]] = set()
    for raw_payload in evaluation_payloads:
        if not isinstance(raw_payload, dict):
            raise CandidatePoolError("evaluation payload must be an object")
        expected = {
            "schema",
            "execution_sha256",
            "checkpoint_sha256",
            "validation_shard_manifest_sha256s",
            "generation",
            "case_count",
            "parse_rate",
            "exact_accuracy",
            "visible_consistency_rate",
            "mean_semantic_accuracy",
            "cases",
        }
        if set(raw_payload) != expected:
            raise CandidatePoolError("evaluation payload has wrong fields")
        if raw_payload["schema"] != "plural-cognition-validation-evaluation-v1":
            raise CandidatePoolError("unsupported evaluation schema")
        source = _source_from_generation(raw_payload["generation"])
        checkpoint_hashes.add(_hex64(raw_payload["checkpoint_sha256"], "checkpoint"))
        execution_hashes.add(_hex64(raw_payload["execution_sha256"], "execution"))
        shard_values = raw_payload["validation_shard_manifest_sha256s"]
        if not isinstance(shard_values, list) or not shard_values:
            raise CandidatePoolError("evaluation has no task-shard identities")
        shard_sets.add(tuple(_hex64(value, "task shard") for value in shard_values))
        cases = raw_payload["cases"]
        count = _plain_int(raw_payload["case_count"], "case_count", minimum=1)
        if not isinstance(cases, list) or len(cases) != count:
            raise CandidatePoolError("evaluation case count is inconsistent")
        if count != len(public_tasks):
            raise CandidatePoolError("evaluation tasks do not match supplied public tasks")
        evaluations.append((source, raw_payload))

    if len(checkpoint_hashes) != 1:
        raise CandidatePoolError("candidate paths come from different checkpoints")
    if len(execution_hashes) != 1:
        raise CandidatePoolError("candidate paths come from different executions")
    if len(shard_sets) != 1:
        raise CandidatePoolError("candidate paths use different task shards")
    if len({source.source_id for source, _ in evaluations}) != len(evaluations):
        raise CandidatePoolError("candidate-pool generation sources must be unique")

    evaluations.sort(key=lambda item: item[0])
    sources = tuple(source for source, _ in evaluations)
    tasks: list[CandidatePoolTask] = []
    for case_index, public_task in enumerate(public_tasks):
        encoded_task = tuple(encode_public_task(public_task))
        candidates: list[FrozenCandidate] = []
        for source, evaluation in evaluations:
            raw_case = evaluation["cases"][case_index]
            expected_case_fields = {
                "case_index",
                "task_id",
                "valid",
                "expression",
                "generated_token_ids",
                "generation_error",
                "exact",
                "visible_consistent",
                "semantic_accuracy",
            }
            if not isinstance(raw_case, dict) or set(raw_case) != expected_case_fields:
                raise CandidatePoolError("evaluation case has wrong fields")
            if raw_case["case_index"] != case_index:
                raise CandidatePoolError("evaluation case order is inconsistent")
            if type(raw_case["valid"]) is not bool:
                raise CandidatePoolError("evaluation valid flag must be Boolean")
            token_ids = raw_case["generated_token_ids"]
            if not isinstance(token_ids, list):
                raise CandidatePoolError("generated token IDs must be a list")
            expression_text = raw_case["expression"]
            error = raw_case["generation_error"]
            if raw_case["valid"]:
                if not isinstance(expression_text, str) or error is not None:
                    raise CandidatePoolError("valid evaluation case has invalid metadata")
                expression = parse_canonical_text(
                    expression_text,
                    allowed_variables=public_task.variable_order,
                )
                expression_text = canonical_text(expression)
            else:
                if expression_text is not None or not isinstance(error, str):
                    raise CandidatePoolError("invalid evaluation case has invalid metadata")
            candidates.append(
                FrozenCandidate(
                    source.source_id,
                    raw_case["valid"],
                    expression_text,
                    tuple(token_ids),
                    error,
                )
            )
        tasks.append(CandidatePoolTask(case_index, encoded_task, tuple(candidates)))

    return FrozenCandidatePool(
        checkpoint_hashes.pop(),
        execution_hashes.pop(),
        shard_sets.pop(),
        sources,
        tuple(tasks),
    )
