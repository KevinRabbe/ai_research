"""Architecture-independent immutable artifacts for the capable collective.

These contracts deliberately contain no model-vendor, task-family, or harness logic.
They bind stage outputs, lineage, producer configuration, software revision, and
resource usage so later capability layers can be measured without overwriting
what came before them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from math import isfinite
from typing import Any

ARTIFACT_SCHEMA = "plural-cognition-collective-artifact-v1"
EVALUATION_SCHEMA = "plural-cognition-collective-evaluation-v1"


class CollectiveStage(str, Enum):
    RAW_MIND_OUTPUT = "raw-mind-output"
    EVIDENCE_INTEGRATION = "evidence-integration"
    SYNTHESIS = "synthesis"
    HARNESS = "harness"
    ADVERSARIAL_REVIEW = "adversarial-review"
    VERIFICATION = "verification"
    FINAL = "final"


class EvaluationVisibility(str, Enum):
    DEVELOPMENT = "development"
    PROTECTED = "protected"
    DIAGNOSTIC = "diagnostic"


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _validate_nonempty(value: str, field: str) -> None:
    if type(value) is not str or not value:
        raise ValueError(f"{field} must be a non-empty string")


def _validate_sha256(value: str, field: str) -> None:
    if type(value) is not str or len(value) != 64:
        raise ValueError(f"{field} must contain 64 lowercase hexadecimal characters")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{field} must be hexadecimal") from exc
    if value != value.lower():
        raise ValueError(f"{field} must use lowercase hexadecimal")


def _validate_git_revision(value: str) -> None:
    if type(value) is not str or len(value) != 40:
        raise ValueError("software_revision must be a full 40-character Git SHA")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError("software_revision must be hexadecimal") from exc
    if value != value.lower():
        raise ValueError("software_revision must use lowercase hexadecimal")


def _validate_nonnegative_int(value: int, field: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{field} must be int")
    if value < 0:
        raise ValueError(f"{field} must not be negative")


@dataclass(frozen=True, slots=True)
class TaskIdentity:
    """Visible identity for a task without exposing protected evaluator state."""

    task_id: str
    task_family: str
    payload_sha256: str

    def __post_init__(self) -> None:
        _validate_nonempty(self.task_id, "task_id")
        _validate_nonempty(self.task_family, "task_family")
        _validate_sha256(self.payload_sha256, "payload_sha256")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_family": self.task_family,
            "payload_sha256": self.payload_sha256,
        }


@dataclass(frozen=True, slots=True)
class ResourceUsage:
    """Resource ledger for one immutable cognitive transformation."""

    input_tokens: int = 0
    output_tokens: int = 0
    inference_calls: int = 0
    tool_calls: int = 0
    verifier_calls: int = 0
    wall_time_ms: int = 0
    accelerator_time_ms: int = 0
    peak_accelerator_bytes: int = 0
    cpu_time_ms: int = 0
    peak_ram_bytes: int = 0
    retrieval_bytes: int = 0

    def __post_init__(self) -> None:
        for field in (
            "input_tokens",
            "output_tokens",
            "inference_calls",
            "tool_calls",
            "verifier_calls",
            "wall_time_ms",
            "accelerator_time_ms",
            "peak_accelerator_bytes",
            "cpu_time_ms",
            "peak_ram_bytes",
            "retrieval_bytes",
        ):
            _validate_nonnegative_int(getattr(self, field), field)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def canonical_payload(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "inference_calls": self.inference_calls,
            "tool_calls": self.tool_calls,
            "verifier_calls": self.verifier_calls,
            "wall_time_ms": self.wall_time_ms,
            "accelerator_time_ms": self.accelerator_time_ms,
            "peak_accelerator_bytes": self.peak_accelerator_bytes,
            "cpu_time_ms": self.cpu_time_ms,
            "peak_ram_bytes": self.peak_ram_bytes,
            "retrieval_bytes": self.retrieval_bytes,
        }


@dataclass(frozen=True, slots=True)
class StageArtifact:
    """Hash-bound output from one stage in the collective cognitive lineage."""

    stage: CollectiveStage
    task: TaskIdentity
    run_id: str
    producer_id: str
    producer_configuration_sha256: str
    protocol_sha256: str
    software_revision: str
    content_sha256: str
    parent_sha256s: tuple[str, ...] = ()
    resources: ResourceUsage = ResourceUsage()

    def __post_init__(self) -> None:
        if not isinstance(self.stage, CollectiveStage):
            raise TypeError("stage must be CollectiveStage")
        if not isinstance(self.task, TaskIdentity):
            raise TypeError("task must be TaskIdentity")
        if not isinstance(self.resources, ResourceUsage):
            raise TypeError("resources must be ResourceUsage")
        _validate_nonempty(self.run_id, "run_id")
        _validate_nonempty(self.producer_id, "producer_id")
        _validate_sha256(
            self.producer_configuration_sha256,
            "producer_configuration_sha256",
        )
        _validate_sha256(self.protocol_sha256, "protocol_sha256")
        _validate_git_revision(self.software_revision)
        _validate_sha256(self.content_sha256, "content_sha256")
        for parent in self.parent_sha256s:
            _validate_sha256(parent, "parent_sha256s entry")
        if tuple(sorted(set(self.parent_sha256s))) != self.parent_sha256s:
            raise ValueError("parent_sha256s must be sorted and unique")
        if self.stage is CollectiveStage.RAW_MIND_OUTPUT:
            if self.parent_sha256s:
                raise ValueError("raw mind outputs must not have parent artifacts")
        elif not self.parent_sha256s:
            raise ValueError("non-raw stages require at least one parent artifact")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": ARTIFACT_SCHEMA,
            "stage": self.stage.value,
            "task": self.task.canonical_payload(),
            "run_id": self.run_id,
            "producer_id": self.producer_id,
            "producer_configuration_sha256": self.producer_configuration_sha256,
            "protocol_sha256": self.protocol_sha256,
            "software_revision": self.software_revision,
            "content_sha256": self.content_sha256,
            "parent_sha256s": list(self.parent_sha256s),
            "resources": self.resources.canonical_payload(),
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class MetricValue:
    name: str
    value: float

    def __post_init__(self) -> None:
        _validate_nonempty(self.name, "metric name")
        if type(self.value) not in (int, float):
            raise TypeError("metric value must be a plain int or float")
        if not isfinite(float(self.value)):
            raise ValueError("metric value must be finite")

    def canonical_payload(self) -> dict[str, Any]:
        return {"name": self.name, "value": float(self.value)}


@dataclass(frozen=True, slots=True)
class EvaluationRecord:
    """Immutable evaluation of an already-frozen stage artifact."""

    artifact_sha256: str
    task: TaskIdentity
    evaluator_id: str
    evaluator_configuration_sha256: str
    evaluator_software_revision: str
    visibility: EvaluationVisibility
    metrics: tuple[MetricValue, ...]
    qualified: bool | None = None
    resources: ResourceUsage = ResourceUsage()

    def __post_init__(self) -> None:
        _validate_sha256(self.artifact_sha256, "artifact_sha256")
        if not isinstance(self.task, TaskIdentity):
            raise TypeError("task must be TaskIdentity")
        _validate_nonempty(self.evaluator_id, "evaluator_id")
        _validate_sha256(
            self.evaluator_configuration_sha256,
            "evaluator_configuration_sha256",
        )
        _validate_git_revision(self.evaluator_software_revision)
        if not isinstance(self.visibility, EvaluationVisibility):
            raise TypeError("visibility must be EvaluationVisibility")
        if not isinstance(self.resources, ResourceUsage):
            raise TypeError("resources must be ResourceUsage")
        if self.qualified is not None and type(self.qualified) is not bool:
            raise TypeError("qualified must be bool or None")
        if not self.metrics:
            raise ValueError("evaluation requires at least one metric")
        if any(not isinstance(metric, MetricValue) for metric in self.metrics):
            raise TypeError("metrics must contain MetricValue instances")
        names = tuple(metric.name for metric in self.metrics)
        if tuple(sorted(set(names))) != names:
            raise ValueError("metrics must be sorted by unique name")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": EVALUATION_SCHEMA,
            "artifact_sha256": self.artifact_sha256,
            "task": self.task.canonical_payload(),
            "evaluator_id": self.evaluator_id,
            "evaluator_configuration_sha256": self.evaluator_configuration_sha256,
            "evaluator_software_revision": self.evaluator_software_revision,
            "visibility": self.visibility.value,
            "metrics": [metric.canonical_payload() for metric in self.metrics],
            "qualified": self.qualified,
            "resources": self.resources.canonical_payload(),
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


def sha256_content(content: bytes) -> str:
    """Return the content identity used by StageArtifact without storing payload bytes."""

    if type(content) is not bytes:
        raise TypeError("content must be bytes")
    return sha256(content).hexdigest()
