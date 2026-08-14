from __future__ import annotations

import pytest

from plural_cognition.collective.tasks import (
    ProtectedEvaluatorSpec,
    SolverVisibleTask,
    TaskResourceBudget,
    TaskSplit,
)


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
SHA_E = "e" * 64
REV = "1" * 40


def test_solver_visible_task_binds_exact_payload() -> None:
    task = SolverVisibleTask.create(
        task_id="repo-fix-001",
        task_family="repository-surgery-v0",
        split=TaskSplit.SELECTION,
        repository_sha256=SHA_A,
        prompt_sha256=SHA_B,
        language="python",
        max_visible_bytes=100_000,
        public_tests_sha256=SHA_C,
    )
    assert task.task.payload_sha256 == task.visible_payload_sha256
    assert task.split is TaskSplit.SELECTION


def test_solver_visible_task_rejects_mismatched_task_hash() -> None:
    task = SolverVisibleTask.create(
        task_id="repo-fix-001",
        task_family="repository-surgery-v0",
        split=TaskSplit.SELECTION,
        repository_sha256=SHA_A,
        prompt_sha256=SHA_B,
        language="python",
        max_visible_bytes=100_000,
    )
    with pytest.raises(ValueError, match="payload hash"):
        SolverVisibleTask(
            task=type(task.task)(task.task.task_id, task.task.task_family, SHA_C),
            split=task.split,
            repository_sha256=task.repository_sha256,
            prompt_sha256=task.prompt_sha256,
            language=task.language,
            max_visible_bytes=task.max_visible_bytes,
        )


def test_resource_budget_is_fail_closed() -> None:
    budget = TaskResourceBudget(
        max_output_tokens=4096,
        max_inference_calls=1,
        max_tool_calls=0,
        max_wall_time_ms=120_000,
        max_accelerator_time_ms=120_000,
        max_retrieval_bytes=0,
    )
    assert len(budget.sha256) == 64
    with pytest.raises(ValueError, match="max_output_tokens"):
        TaskResourceBudget(0, 1, 0, 1, 1, 0)


def test_protected_evaluator_binds_without_entering_visible_task() -> None:
    task = SolverVisibleTask.create(
        task_id="repo-fix-001",
        task_family="repository-surgery-v0",
        split=TaskSplit.CONFIRMATION,
        repository_sha256=SHA_A,
        prompt_sha256=SHA_B,
        language="python",
        max_visible_bytes=100_000,
    )
    evaluator = ProtectedEvaluatorSpec(
        task_id=task.task.task_id,
        task_payload_sha256=task.task.payload_sha256,
        evaluator_id="black-box-grader-v0",
        evaluator_configuration_sha256=SHA_C,
        evaluator_software_revision=REV,
        protected_inputs_sha256=SHA_D,
        protected_expectations_sha256=SHA_E,
        primary_metric="pass_fraction",
        pass_threshold=1.0,
    )
    assert evaluator.binds(task)
    assert evaluator.canonical_payload()["evaluator_software_revision"] == REV
    visible = task.canonical_payload()["visible"]
    assert "protected_inputs_sha256" not in visible
    assert "protected_expectations_sha256" not in visible


def test_protected_inputs_and_expectations_must_be_distinct() -> None:
    with pytest.raises(ValueError, match="distinct"):
        ProtectedEvaluatorSpec(
            task_id="repo-fix-001",
            task_payload_sha256=SHA_A,
            evaluator_id="grader",
            evaluator_configuration_sha256=SHA_B,
            evaluator_software_revision=REV,
            protected_inputs_sha256=SHA_C,
            protected_expectations_sha256=SHA_C,
            primary_metric="score",
            pass_threshold=1.0,
        )


def test_protected_evaluator_requires_full_software_revision() -> None:
    with pytest.raises(ValueError, match="40-character"):
        ProtectedEvaluatorSpec(
            task_id="repo-fix-001",
            task_payload_sha256=SHA_A,
            evaluator_id="grader",
            evaluator_configuration_sha256=SHA_B,
            evaluator_software_revision="abc",
            protected_inputs_sha256=SHA_C,
            protected_expectations_sha256=SHA_D,
            primary_metric="score",
            pass_threshold=1.0,
        )
