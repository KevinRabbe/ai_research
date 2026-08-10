from __future__ import annotations

from pathlib import Path

import pytest

from plural_cognition.collective.artifacts import (
    EvaluationVisibility,
    ResourceUsage,
    TaskIdentity,
)
from plural_cognition.collective.content_store import FileContentStore
from plural_cognition.collective.grading import (
    BlackBoxEvaluationPlan,
    CaseObservation,
    ProtectedCase,
    grade_black_box,
    observation_from_sandbox_result,
    protected_expectation_set_sha256,
    protected_input_set_sha256,
)
from plural_cognition.collective.sandbox import SandboxResult
from plural_cognition.collective.tasks import ProtectedEvaluatorSpec


REV = "1" * 40


def _fixture(tmp_path: Path):
    store = FileContentStore(tmp_path / "store")
    input_a = store.put_bytes(b'{"x":1}\n')
    input_b = store.put_bytes(b'{"x":2}\n')
    expected_a = store.put_bytes(b'{"y":2}\n')
    expected_b = store.put_bytes(b'{"y":4}\n')
    cases = (
        ProtectedCase("case-001", input_a, expected_a),
        ProtectedCase("case-002", input_b, expected_b),
    )
    task = TaskIdentity("rs-001", "repository-surgery-v0", "a" * 64)
    evaluator = ProtectedEvaluatorSpec(
        task_id=task.task_id,
        task_payload_sha256=task.payload_sha256,
        evaluator_id="black-box-exact-v0",
        evaluator_configuration_sha256="b" * 64,
        evaluator_software_revision=REV,
        protected_inputs_sha256=protected_input_set_sha256(cases),
        protected_expectations_sha256=protected_expectation_set_sha256(cases),
        primary_metric="exact_accuracy",
        pass_threshold=0.5,
    )
    return store, task, cases, BlackBoxEvaluationPlan(task, evaluator, cases)


def test_black_box_plan_binds_separate_input_and_expectation_sets(tmp_path: Path) -> None:
    _, _, cases, plan = _fixture(tmp_path)
    assert len(plan.sha256) == 64
    assert plan.evaluator.protected_inputs_sha256 == protected_input_set_sha256(cases)
    assert plan.evaluator.protected_expectations_sha256 == protected_expectation_set_sha256(cases)
    assert plan.evaluator.protected_inputs_sha256 != plan.evaluator.protected_expectations_sha256


def test_grader_compares_expectations_outside_observations(tmp_path: Path) -> None:
    store, task, cases, plan = _fixture(tmp_path)
    correct_output = store.put_bytes(b'{"y":2}\n')
    wrong_output = store.put_bytes(b'{"y":999}\n')
    observations = (
        CaseObservation(
            "case-001",
            cases[0].runtime_input_sha256,
            "c" * 64,
            correct_output,
            True,
        ),
        CaseObservation(
            "case-002",
            cases[1].runtime_input_sha256,
            "d" * 64,
            wrong_output,
            True,
        ),
    )
    for observation in observations:
        payload = observation.canonical_payload()
        assert "expected_output_sha256" not in payload
        assert "protected_expectations_sha256" not in payload

    record = grade_black_box(
        plan=plan,
        artifact_sha256="e" * 64,
        observations=observations,
        store=store,
    )
    assert record.task == task
    assert record.visibility is EvaluationVisibility.PROTECTED
    assert record.evaluator_software_revision == REV
    assert record.qualified is True
    assert tuple((item.name, item.value) for item in record.metrics) == (
        ("exact_accuracy", 0.5),
        ("valid_rate", 1.0),
    )


def test_invalid_execution_counts_as_failure_not_missing_case(tmp_path: Path) -> None:
    store, _, cases, plan = _fixture(tmp_path)
    correct_output = store.put_bytes(b'{"y":2}\n')
    unused_output = store.put_bytes(b"invalid\n")
    record = grade_black_box(
        plan=plan,
        artifact_sha256="e" * 64,
        observations=(
            CaseObservation(
                "case-001",
                cases[0].runtime_input_sha256,
                "c" * 64,
                correct_output,
                True,
            ),
            CaseObservation(
                "case-002",
                cases[1].runtime_input_sha256,
                "d" * 64,
                unused_output,
                False,
            ),
        ),
        store=store,
    )
    assert tuple((item.name, item.value) for item in record.metrics) == (
        ("exact_accuracy", 0.5),
        ("valid_rate", 0.5),
    )


def test_runtime_input_substitution_is_rejected(tmp_path: Path) -> None:
    store, _, cases, plan = _fixture(tmp_path)
    output = store.put_bytes(b'{"y":2}\n')
    with pytest.raises(ValueError, match="runtime input identity differs"):
        grade_black_box(
            plan=plan,
            artifact_sha256="e" * 64,
            observations=(
                CaseObservation("case-001", "f" * 64, "c" * 64, output, True),
                CaseObservation(
                    "case-002",
                    cases[1].runtime_input_sha256,
                    "d" * 64,
                    output,
                    True,
                ),
            ),
            store=store,
        )


def test_observation_helper_uses_only_sandbox_completion_state() -> None:
    result = SandboxResult(
        request_sha256="a" * 64,
        exit_code=0,
        timed_out=False,
        memory_limit_exceeded=False,
        stdout_sha256="b" * 64,
        stderr_sha256="c" * 64,
        resources=ResourceUsage(wall_time_ms=10),
    )
    observation = observation_from_sandbox_result(
        case_id="case-001",
        runtime_input_sha256="d" * 64,
        result=result,
        observed_output_sha256="e" * 64,
    )
    assert observation.execution_valid is True
    assert observation.sandbox_result_sha256 == result.sha256
