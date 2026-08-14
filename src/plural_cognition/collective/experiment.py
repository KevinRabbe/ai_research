"""Immutable hypothesis/prediction/experiment records for capable-system learning.

These records capture what an actor believed, predicted, changed, observed, and
learned without importing protected evaluator expectations into solver-visible
state. They are intentionally execution-agnostic: a sandbox, tool harness, or
future simulator may produce the observations, but this module only freezes the
scientific lineage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from typing import Any

from .artifacts import ResourceUsage, TaskIdentity
from .content_store import validate_sha256

EXPERIMENT_ATTEMPT_SCHEMA = "plural-cognition-experiment-attempt-v1"
PREDICTION_MEASUREMENT_SCHEMA = "plural-cognition-prediction-measurement-v1"


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


def _git_revision(value: str) -> None:
    if type(value) is not str or len(value) != 40:
        raise ValueError("software_revision must be a full 40-character Git SHA")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError("software_revision must be hexadecimal") from exc
    if value != value.lower():
        raise ValueError("software_revision must use lowercase hexadecimal")


def _finite_number(value: float, field: str) -> None:
    if type(value) not in (int, float):
        raise TypeError(f"{field} must be a plain int or float")
    if not isfinite(float(value)):
        raise ValueError(f"{field} must be finite")


@dataclass(frozen=True, slots=True)
class PredictionMeasurement:
    """One numerical prediction paired with the later measured outcome."""

    name: str
    predicted_value: float
    actual_value: float
    confidence: float | None = None

    def __post_init__(self) -> None:
        _nonempty(self.name, "name")
        _finite_number(self.predicted_value, "predicted_value")
        _finite_number(self.actual_value, "actual_value")
        if self.confidence is not None:
            _finite_number(self.confidence, "confidence")
            if not 0.0 <= float(self.confidence) <= 1.0:
                raise ValueError("confidence must be between 0 and 1")

    @property
    def absolute_error(self) -> float:
        return abs(float(self.predicted_value) - float(self.actual_value))

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": PREDICTION_MEASUREMENT_SCHEMA,
            "name": self.name,
            "predicted_value": float(self.predicted_value),
            "actual_value": float(self.actual_value),
            "confidence": None if self.confidence is None else float(self.confidence),
            "absolute_error": self.absolute_error,
        }


@dataclass(frozen=True, slots=True)
class ExperimentAttempt:
    """One immutable observe→hypothesize→predict→act→measure→update attempt.

    All substantive textual/structured payloads are stored separately and bound
    here by SHA-256. Protected expectations, hidden tests, promotion thresholds,
    and privileged scores do not belong in this record.
    """

    task: TaskIdentity
    attempt_id: str
    actor_id: str
    producer_configuration_sha256: str
    protocol_sha256: str
    software_revision: str
    observation_sha256: str
    hypothesis_sha256: str
    prediction_sha256: str
    action_sha256: str
    observed_result_sha256: str
    explanation_sha256: str
    successor_hypothesis_sha256: str | None = None
    parent_attempt_sha256s: tuple[str, ...] = ()
    measurements: tuple[PredictionMeasurement, ...] = ()
    resources: ResourceUsage = ResourceUsage()

    def __post_init__(self) -> None:
        if not isinstance(self.task, TaskIdentity):
            raise TypeError("task must be TaskIdentity")
        if not isinstance(self.resources, ResourceUsage):
            raise TypeError("resources must be ResourceUsage")
        _nonempty(self.attempt_id, "attempt_id")
        _nonempty(self.actor_id, "actor_id")
        for digest in (
            self.producer_configuration_sha256,
            self.protocol_sha256,
            self.observation_sha256,
            self.hypothesis_sha256,
            self.prediction_sha256,
            self.action_sha256,
            self.observed_result_sha256,
            self.explanation_sha256,
        ):
            validate_sha256(digest)
        if self.successor_hypothesis_sha256 is not None:
            validate_sha256(self.successor_hypothesis_sha256)
        _git_revision(self.software_revision)

        for digest in self.parent_attempt_sha256s:
            validate_sha256(digest)
        if tuple(sorted(set(self.parent_attempt_sha256s))) != self.parent_attempt_sha256s:
            raise ValueError("parent_attempt_sha256s must be sorted and unique")

        if any(not isinstance(item, PredictionMeasurement) for item in self.measurements):
            raise TypeError("measurements must contain PredictionMeasurement instances")
        names = tuple(item.name for item in self.measurements)
        if names != tuple(sorted(set(names))):
            raise ValueError("measurements must be sorted by unique name")

    @property
    def mean_absolute_prediction_error(self) -> float | None:
        if not self.measurements:
            return None
        return sum(item.absolute_error for item in self.measurements) / len(self.measurements)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": EXPERIMENT_ATTEMPT_SCHEMA,
            "task": self.task.canonical_payload(),
            "attempt_id": self.attempt_id,
            "actor_id": self.actor_id,
            "producer_configuration_sha256": self.producer_configuration_sha256,
            "protocol_sha256": self.protocol_sha256,
            "software_revision": self.software_revision,
            "observation_sha256": self.observation_sha256,
            "hypothesis_sha256": self.hypothesis_sha256,
            "prediction_sha256": self.prediction_sha256,
            "action_sha256": self.action_sha256,
            "observed_result_sha256": self.observed_result_sha256,
            "explanation_sha256": self.explanation_sha256,
            "successor_hypothesis_sha256": self.successor_hypothesis_sha256,
            "parent_attempt_sha256s": list(self.parent_attempt_sha256s),
            "measurements": [item.canonical_payload() for item in self.measurements],
            "resources": self.resources.canonical_payload(),
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()
