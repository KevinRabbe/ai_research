"""Solver-visible task and protected-evaluator contracts for capable-model experiments."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from math import isfinite
from typing import Any

from .artifacts import TaskIdentity


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


def _sha256(value: str, field: str) -> None:
    if type(value) is not str or len(value) != 64:
        raise ValueError(f"{field} must contain 64 lowercase hexadecimal characters")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{field} must be hexadecimal") from exc
    if value != value.lower():
        raise ValueError(f"{field} must use lowercase hexadecimal")


def _nonnegative_int(value: int, field: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")


def _positive_int(value: int, field: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{field} must be a positive integer")


class TaskSplit(str, Enum):
    """Visibility role of one capable-system task."""

    CALIBRATION = "calibration"
    SELECTION = "selection"
    CONFIRMATION = "confirmation"


@dataclass(frozen=True, slots=True)
class SolverVisibleTask:
    """Exact task material that a mind is allowed to receive.

    Protected tests and evaluator configuration are deliberately absent. The
    ``TaskIdentity.payload_sha256`` must equal the hash of ``visible_payload``.
    """

    task: TaskIdentity
    split: TaskSplit
    repository_sha256: str
    prompt_sha256: str
    language: str
    max_visible_bytes: int
    public_tests_sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.task, TaskIdentity):
            raise TypeError("task must be TaskIdentity")
        if not isinstance(self.split, TaskSplit):
            raise TypeError("split must be TaskSplit")
        _sha256(self.repository_sha256, "repository_sha256")
        _sha256(self.prompt_sha256, "prompt_sha256")
        _nonempty(self.language, "language")
        _positive_int(self.max_visible_bytes, "max_visible_bytes")
        if self.public_tests_sha256 is not None:
            _sha256(self.public_tests_sha256, "public_tests_sha256")
        if self.task.payload_sha256 != self.visible_payload_sha256:
            raise ValueError("task payload hash does not match solver-visible payload")

    def visible_payload(self) -> dict[str, Any]:
        return {
            "repository_sha256": self.repository_sha256,
            "prompt_sha256": self.prompt_sha256,
            "language": self.language,
            "max_visible_bytes": self.max_visible_bytes,
            "public_tests_sha256": self.public_tests_sha256,
        }

    @property
    def visible_payload_sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.visible_payload())).hexdigest()

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "task": self.task.canonical_payload(),
            "split": self.split.value,
            "visible": self.visible_payload(),
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()

    @classmethod
    def create(
        cls,
        *,
        task_id: str,
        task_family: str,
        split: TaskSplit,
        repository_sha256: str,
        prompt_sha256: str,
        language: str,
        max_visible_bytes: int,
        public_tests_sha256: str | None = None,
    ) -> "SolverVisibleTask":
        visible = {
            "repository_sha256": repository_sha256,
            "prompt_sha256": prompt_sha256,
            "language": language,
            "max_visible_bytes": max_visible_bytes,
            "public_tests_sha256": public_tests_sha256,
        }
        payload_sha256 = sha256(_canonical_json_bytes(visible)).hexdigest()
        return cls(
            task=TaskIdentity(task_id, task_family, payload_sha256),
            split=split,
            repository_sha256=repository_sha256,
            prompt_sha256=prompt_sha256,
            language=language,
            max_visible_bytes=max_visible_bytes,
            public_tests_sha256=public_tests_sha256,
        )


@dataclass(frozen=True, slots=True)
class TaskResourceBudget:
    """Per-task ceiling shared by compared capable-model conditions."""

    max_output_tokens: int
    max_inference_calls: int
    max_tool_calls: int
    max_wall_time_ms: int
    max_accelerator_time_ms: int
    max_retrieval_bytes: int

    def __post_init__(self) -> None:
        _positive_int(self.max_output_tokens, "max_output_tokens")
        _positive_int(self.max_inference_calls, "max_inference_calls")
        _nonnegative_int(self.max_tool_calls, "max_tool_calls")
        _positive_int(self.max_wall_time_ms, "max_wall_time_ms")
        _positive_int(self.max_accelerator_time_ms, "max_accelerator_time_ms")
        _nonnegative_int(self.max_retrieval_bytes, "max_retrieval_bytes")

    def canonical_payload(self) -> dict[str, int]:
        return {
            "max_output_tokens": self.max_output_tokens,
            "max_inference_calls": self.max_inference_calls,
            "max_tool_calls": self.max_tool_calls,
            "max_wall_time_ms": self.max_wall_time_ms,
            "max_accelerator_time_ms": self.max_accelerator_time_ms,
            "max_retrieval_bytes": self.max_retrieval_bytes,
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()


@dataclass(frozen=True, slots=True)
class ProtectedEvaluatorSpec:
    """Privileged evaluator identity that must never be included in a mind request."""

    task_id: str
    task_payload_sha256: str
    evaluator_id: str
    evaluator_configuration_sha256: str
    hidden_tests_sha256: str
    primary_metric: str
    pass_threshold: float

    def __post_init__(self) -> None:
        _nonempty(self.task_id, "task_id")
        _sha256(self.task_payload_sha256, "task_payload_sha256")
        _nonempty(self.evaluator_id, "evaluator_id")
        _sha256(self.evaluator_configuration_sha256, "evaluator_configuration_sha256")
        _sha256(self.hidden_tests_sha256, "hidden_tests_sha256")
        _nonempty(self.primary_metric, "primary_metric")
        if type(self.pass_threshold) not in (int, float):
            raise TypeError("pass_threshold must be a plain int or float")
        if not isfinite(float(self.pass_threshold)):
            raise ValueError("pass_threshold must be finite")

    def binds(self, task: SolverVisibleTask) -> bool:
        if not isinstance(task, SolverVisibleTask):
            raise TypeError("task must be SolverVisibleTask")
        return (
            self.task_id == task.task.task_id
            and self.task_payload_sha256 == task.task.payload_sha256
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_payload_sha256": self.task_payload_sha256,
            "evaluator_id": self.evaluator_id,
            "evaluator_configuration_sha256": self.evaluator_configuration_sha256,
            "hidden_tests_sha256": self.hidden_tests_sha256,
            "primary_metric": self.primary_metric,
            "pass_threshold": float(self.pass_threshold),
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()
