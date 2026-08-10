from __future__ import annotations

from hashlib import sha256

import pytest

from plural_cognition.collective.artifacts import ResourceUsage, TaskIdentity
from plural_cognition.collective.bakeoff import (
    BakeoffPlan,
    CandidateModel,
    CandidateTaskResult,
    DeploymentClass,
    PopulationSelectionStatus,
    select_population,
)
from plural_cognition.collective.mind import MindIdentity


def _digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _tasks() -> tuple[TaskIdentity, ...]:
    return tuple(
        TaskIdentity(f"t{index}", "repository-surgery-v0", _digest(f"task:{index}"))
        for index in range(1, 7)
    )


def _candidate(candidate_id: str) -> CandidateModel:
    return CandidateModel(
        candidate_id=candidate_id,
        mind=MindIdentity(
            mind_id=candidate_id,
            backend_family="test-backend",
            model_id=f"model-{candidate_id}",
            model_revision="rev-1",
            configuration_sha256=_digest(f"config:{candidate_id}"),
        ),
        deployment_class=DeploymentClass.LOCAL,
        architecture_class="dense",
        context_tokens=32_768,
        quantization="test-q4",
        total_parameters=8_000_000_000,
        active_parameters=8_000_000_000,
    )


def _plan() -> BakeoffPlan:
    return BakeoffPlan(
        tasks=_tasks(),
        candidates=tuple(_candidate(item) for item in "ABCDE"),
        raw_protocol_sha256=_digest("raw-protocol"),
        resource_budget_sha256=_digest("resource-budget"),
        min_valid_rate=1.0,
        population_size=4,
    )


def _results(
    plan: BakeoffPlan,
    outcomes: dict[str, tuple[bool, ...]],
    *,
    invalid: set[tuple[str, str]] | None = None,
) -> tuple[CandidateTaskResult, ...]:
    invalid = invalid or set()
    rows: list[CandidateTaskResult] = []
    for candidate_id, vector in outcomes.items():
        for task, passed in zip(plan.tasks, vector, strict=True):
            valid = (candidate_id, task.task_id) not in invalid
            rows.append(
                CandidateTaskResult(
                    candidate_id=candidate_id,
                    task=task,
                    valid=valid,
                    passed=passed if valid else False,
                    raw_artifact_sha256=_digest(
                        f"raw:{candidate_id}:{task.task_id}"
                    ),
                    evaluation_sha256=_digest(
                        f"eval:{candidate_id}:{task.task_id}"
                    ),
                    resources=ResourceUsage(
                        input_tokens=10,
                        output_tokens=5,
                        inference_calls=1,
                        accelerator_time_ms=1 if candidate_id == "A" else 2,
                    ),
                )
            )
    return tuple(rows)


def test_plan_hash_binds_tasks_protocol_budget_and_candidates() -> None:
    plan = _plan()
    assert len(plan.sha256) == 64
    changed_budget = BakeoffPlan(
        tasks=plan.tasks,
        candidates=plan.candidates,
        raw_protocol_sha256=plan.raw_protocol_sha256,
        resource_budget_sha256=_digest("different-budget"),
        min_valid_rate=plan.min_valid_rate,
        population_size=plan.population_size,
    )
    assert changed_budget.sha256 != plan.sha256


def test_selection_keeps_strongest_and_maximizes_unique_coverage() -> None:
    plan = _plan()
    results = _results(
        plan,
        {
            "A": (True, True, True, False, False, False),
            "B": (False, False, False, True, False, False),
            "C": (False, False, False, False, True, False),
            "D": (False, False, False, False, False, True),
            "E": (True, True, True, False, False, False),
        },
    )

    selected = select_population(plan, results)
    assert selected.status is PopulationSelectionStatus.SELECTED
    assert selected.bakeoff_plan_sha256 == plan.sha256
    assert selected.strongest_candidate_id == "A"
    assert selected.selected_candidate_ids == ("A", "B", "C", "D")
    assert selected.best_constituent_score == 0.5
    assert selected.oracle_union_score == 1.0
    assert selected.complementarity_headroom == 0.5


def test_selection_is_not_top_four_individual_scores() -> None:
    plan = _plan()
    results = _results(
        plan,
        {
            "A": (True, True, True, True, False, False),
            "B": (True, True, True, False, False, False),
            "C": (True, True, False, True, False, False),
            "D": (True, False, True, True, False, False),
            "E": (False, False, False, False, True, True),
        },
    )

    selected = select_population(plan, results)
    assert selected.strongest_candidate_id == "A"
    assert "E" in selected.selected_candidate_ids
    assert selected.oracle_union_score == 1.0


def test_selection_reports_insufficient_operationally_valid_candidates() -> None:
    plan = _plan()
    outcomes = {
        item: (True, False, False, False, False, False) for item in "ABCDE"
    }
    selected = select_population(
        plan,
        _results(plan, outcomes, invalid={("D", "t1"), ("E", "t1")}),
    )
    assert selected.status is PopulationSelectionStatus.INSUFFICIENT_ELIGIBLE
    assert selected.bakeoff_plan_sha256 == plan.sha256
    assert selected.eligible_candidate_ids == ("A", "B", "C")
    assert selected.selected_candidate_ids == ()


def test_result_with_same_task_id_but_different_payload_is_rejected() -> None:
    plan = _plan()
    results = list(
        _results(
            plan,
            {item: (False,) * 6 for item in "ABCDE"},
        )
    )
    first = results[0]
    results[0] = CandidateTaskResult(
        candidate_id=first.candidate_id,
        task=TaskIdentity(first.task.task_id, first.task.task_family, _digest("changed")),
        valid=first.valid,
        passed=first.passed,
        raw_artifact_sha256=first.raw_artifact_sha256,
        evaluation_sha256=first.evaluation_sha256,
        resources=first.resources,
    )
    with pytest.raises(ValueError, match="task payload differs"):
        select_population(plan, results)


def test_candidate_result_rejects_pass_on_invalid_output() -> None:
    with pytest.raises(ValueError, match="invalid result"):
        CandidateTaskResult(
            candidate_id="A",
            task=_tasks()[0],
            valid=False,
            passed=True,
            raw_artifact_sha256=_digest("raw"),
            evaluation_sha256=_digest("eval"),
            resources=ResourceUsage(),
        )
