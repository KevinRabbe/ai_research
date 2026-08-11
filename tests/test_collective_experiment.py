from __future__ import annotations

import pytest

from plural_cognition.collective.artifacts import ResourceUsage, TaskIdentity
from plural_cognition.collective.experiment import ExperimentAttempt, PredictionMeasurement


A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64
E = "e" * 64
F = "f" * 64
REV = "1" * 40


def _task() -> TaskIdentity:
    return TaskIdentity("rs-001", "repository-surgery-v0", A)


def _attempt(*, measurements=(), parents=()) -> ExperimentAttempt:
    return ExperimentAttempt(
        task=_task(),
        attempt_id="attempt-001",
        actor_id="mind-a",
        producer_configuration_sha256=A,
        protocol_sha256=B,
        software_revision=REV,
        observation_sha256=C,
        hypothesis_sha256=D,
        prediction_sha256=E,
        action_sha256=F,
        observed_result_sha256=A,
        explanation_sha256=B,
        successor_hypothesis_sha256=C,
        parent_attempt_sha256s=parents,
        measurements=measurements,
        resources=ResourceUsage(tool_calls=2, wall_time_ms=123),
    )


def test_prediction_measurement_records_error_and_confidence() -> None:
    measurement = PredictionMeasurement(
        "runtime_ms",
        predicted_value=80.0,
        actual_value=95.0,
        confidence=0.7,
    )
    assert measurement.absolute_error == 15.0
    payload = measurement.canonical_payload()
    assert payload["predicted_value"] == 80.0
    assert payload["actual_value"] == 95.0
    assert payload["absolute_error"] == 15.0


def test_prediction_measurement_rejects_bad_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        PredictionMeasurement("runtime_ms", 1.0, 2.0, confidence=1.1)


def test_experiment_attempt_is_content_addressed_and_solver_safe() -> None:
    attempt = _attempt(
        measurements=(PredictionMeasurement("memory_bytes", 100.0, 120.0),)
    )
    assert len(attempt.sha256) == 64
    assert attempt.mean_absolute_prediction_error == 20.0
    payload = attempt.canonical_payload()
    assert payload["actor_id"] == "mind-a"
    assert "protected_expectations_sha256" not in payload
    assert "hidden_tests_sha256" not in payload
    assert "promotion_threshold" not in payload
    assert "score" not in payload


def test_experiment_attempt_requires_sorted_unique_measurements() -> None:
    with pytest.raises(ValueError, match="measurements"):
        _attempt(
            measurements=(
                PredictionMeasurement("z", 1.0, 1.0),
                PredictionMeasurement("a", 1.0, 1.0),
            )
        )


def test_experiment_attempt_requires_sorted_unique_parents() -> None:
    with pytest.raises(ValueError, match="parent_attempt_sha256s"):
        _attempt(parents=(B, A))


def test_experiment_attempt_without_numeric_predictions_has_no_mean_error() -> None:
    assert _attempt().mean_absolute_prediction_error is None
