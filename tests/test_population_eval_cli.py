import pytest

from plural_cognition.boolean_world import (
    And,
    EvidenceCase,
    PublicTask,
    Var,
    canonical_text,
    encode_causal_example,
)
from plural_cognition.population_eval_cli import (
    FixedGenerationProtocol,
    FixedMemberCase,
    FixedMemberEvaluation,
    PopulationEvaluationError,
    run_population_evaluation,
)


def _example():
    order = ("A", "B", "C")
    evidence = tuple(
        EvidenceCase(
            f"E{value:03b}",
            tuple(bool((value >> shift) & 1) for shift in (2, 1, 0)),
            bool((value & 0b100) and (value & 0b010)),
        )
        for value in range(8)
    )
    task = PublicTask("TASK-POP-EVAL", order, evidence, ())
    return encode_causal_example(task, And((Var("A"), Var("B"))))


def _member(
    member_id: str,
    expression,
    shard_hash: str = "a" * 64,
    *,
    checkpoint_sha: str | None = None,
    generation: FixedGenerationProtocol | None = None,
):
    identity = member_id[-1] if member_id[-1].isdigit() else "1"
    return FixedMemberEvaluation(
        member_id,
        (shard_hash,),
        (
            FixedMemberCase(
                0,
                True,
                canonical_text(expression),
                None,
            ),
        ),
        identity * 64,
        checkpoint_sha or identity * 64,
        generation or FixedGenerationProtocol("greedy", None, None, None),
    )


def test_four_member_population_command_payload_reaches_strong_gate() -> None:
    evaluations = (
        _member("M0", And((Var("A"), Var("C")))),
        _member("M1", Var("B")),
        _member("M2", Var("C")),
        _member("M3", Var("A")),
    )

    payload = run_population_evaluation(
        (_example(),),
        evaluations,
        bootstrap_resamples=200,
    )

    assert payload["schema"] == "plural-cognition-population-evaluation-v1"
    assert payload["population_type"] == "different-checkpoint-greedy"
    assert payload["case_count"] == 1
    assert payload["qualification"]["passed"] is True
    assert payload["summary"]["mean_synthesis_gain"] == 0.25
    assert payload["summary"]["strong_synthesis_event_count"] == 1
    assert payload["tasks"][0]["full_synthesis_exact"] is True
    assert set(payload["tasks"][0]["score_necessary_members"]) == {"M0", "M1"}


def test_same_checkpoint_sampled_control_is_classified_explicitly() -> None:
    expressions = (
        And((Var("A"), Var("C"))),
        Var("B"),
        Var("C"),
        Var("A"),
    )
    evaluations = tuple(
        _member(
            f"M{index}",
            expression,
            checkpoint_sha="f" * 64,
            generation=FixedGenerationProtocol(
                "sampled",
                301 + index,
                1.0,
                None,
            ),
        )
        for index, expression in enumerate(expressions)
    )

    payload = run_population_evaluation(
        (_example(),),
        evaluations,
        bootstrap_resamples=200,
    )

    assert payload["population_type"] == "same-checkpoint-sampled"
    assert [
        item["generation"]["sampling_seed"] for item in payload["members"]
    ] == [301, 302, 303, 304]


def test_population_evaluation_rejects_different_validation_shards() -> None:
    evaluations = (
        _member("M0", Var("A")),
        _member("M1", Var("B")),
        _member("M2", Var("C")),
        _member("M3", Var("A"), shard_hash="9" * 64),
    )

    with pytest.raises(PopulationEvaluationError, match="different validation shards"):
        run_population_evaluation((_example(),), evaluations, bootstrap_resamples=200)
