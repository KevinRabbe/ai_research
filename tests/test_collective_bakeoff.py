from __future__ import annotations

from hashlib import sha256

from plural_cognition.collective.artifacts import ResourceUsage
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


def _candidate(candidate_id: str, *, accel_bias: int = 0) -> CandidateModel:
    del accel_bias
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


def _results(
    outcomes: dict[str, tuple[bool, ...]],
    *,
    invalid: set[tuple[str, str]] | None = None,
) -> tuple[CandidateTaskResult, ...]:
    invalid = invalid or set()
    task_ids = tuple(f"t{index}" for index in range(1, 7))
    rows: list[CandidateTaskResult] = []
    for candidate_id, vector in outcomes.items():
        for task_id, passed in zip(task_ids, vector, strict=True):
            valid = (candidate_id, task_id) not in invalid
            rows.append(
                CandidateTaskResult(
                    candidate_id=candidate_id,
                    task_id=task_id,
                    valid=valid,
                    passed=passed if valid else False,
                    raw_artifact_sha256=_digest(f"raw:{candidate_id}:{task_id}"),
                    evaluation_sha256=_digest(f"eval:{candidate_id}:{task_id}"),
                    resources=ResourceUsage(
                        input_tokens=10,
                        output_tokens=5,
                        inference_calls=1,
                        accelerator_time_ms=1 if candidate_id == "A" else 2,
                    ),
                )
            )
    return tuple(rows)


def test_selection_keeps_strongest_and_maximizes_unique_coverage() -> None:
    candidates = tuple(_candidate(item) for item in "ABCDE")
    plan = BakeoffPlan(
        task_ids=("t1", "t2", "t3", "t4", "t5", "t6"),
        candidates=candidates,
        min_valid_rate=1.0,
        population_size=4,
    )
    results = _results(
        {
            "A": (True, True, True, False, False, False),
            "B": (False, False, False, True, False, False),
            "C": (False, False, False, False, True, False),
            "D": (False, False, False, False, False, True),
            "E": (True, True, True, False, False, False),
        }
    )

    selected = select_population(plan, results)
    assert selected.status is PopulationSelectionStatus.SELECTED
    assert selected.strongest_candidate_id == "A"
    assert selected.selected_candidate_ids == ("A", "B", "C", "D")
    assert selected.best_constituent_score == 0.5
    assert selected.oracle_union_score == 1.0
    assert selected.complementarity_headroom == 0.5


def test_selection_is_not_top_four_individual_scores() -> None:
    candidates = tuple(_candidate(item) for item in "ABCDE")
    plan = BakeoffPlan(
        task_ids=("t1", "t2", "t3", "t4", "t5", "t6"),
        candidates=candidates,
        min_valid_rate=1.0,
        population_size=4,
    )
    results = _results(
        {
            "A": (True, True, True, True, False, False),
            "B": (True, True, True, False, False, False),
            "C": (True, True, False, True, False, False),
            "D": (True, False, True, True, False, False),
            "E": (False, False, False, False, True, True),
        }
    )

    selected = select_population(plan, results)
    assert selected.strongest_candidate_id == "A"
    assert "E" in selected.selected_candidate_ids
    assert selected.oracle_union_score == 1.0


def test_selection_reports_insufficient_operationally_valid_candidates() -> None:
    candidates = tuple(_candidate(item) for item in "ABCDE")
    plan = BakeoffPlan(
        task_ids=("t1", "t2", "t3", "t4", "t5", "t6"),
        candidates=candidates,
        min_valid_rate=1.0,
        population_size=4,
    )
    outcomes = {
        item: (True, False, False, False, False, False) for item in "ABCDE"
    }
    selected = select_population(
        plan,
        _results(outcomes, invalid={("D", "t1"), ("E", "t1")}),
    )
    assert selected.status is PopulationSelectionStatus.INSUFFICIENT_ELIGIBLE
    assert selected.eligible_candidate_ids == ("A", "B", "C")
    assert selected.selected_candidate_ids == ()


def test_candidate_result_rejects_pass_on_invalid_output() -> None:
    try:
        CandidateTaskResult(
            candidate_id="A",
            task_id="t1",
            valid=False,
            passed=True,
            raw_artifact_sha256=_digest("raw"),
            evaluation_sha256=_digest("eval"),
            resources=ResourceUsage(),
        )
    except ValueError as exc:
        assert "invalid result" in str(exc)
    else:
        raise AssertionError("invalid passed result was accepted")
