from plural_cognition.boolean_world import (
    And,
    EvidenceCase,
    Not,
    PublicTask,
    Var,
    canonical_text,
)
from plural_cognition.population import (
    AblationMode,
    FragmentRole,
    HypothesisFragment,
    HypothesisPacket,
    SynthesisConfig,
    run_ablation,
    run_ablation_suite,
    validate_and_hash_packet,
)


def _task() -> PublicTask:
    return PublicTask(
        "TASK-ABLATION",
        ("A", "B"),
        (
            EvidenceCase("E00", (False, False), False),
            EvidenceCase("E01", (False, True), False),
            EvidenceCase("E10", (True, False), False),
            EvidenceCase("E11", (True, True), True),
        ),
        (),
    )


def _packets():
    first = HypothesisPacket(
        "M0",
        Var("A"),
        (
            HypothesisFragment("A", Var("A"), FragmentRole.ATOM),
            HypothesisFragment(
                "OP",
                And((Var("A"), Not(Var("B")))),
                FragmentRole.ALTERNATIVE,
            ),
        ),
    )
    second = HypothesisPacket(
        "M1",
        Var("B"),
        (HypothesisFragment("B", Var("B"), FragmentRole.ATOM),),
    )
    return (
        validate_and_hash_packet(first, _task()),
        validate_and_hash_packet(second, _task()),
    )


def test_selection_controls_do_not_receive_synthesis_gain() -> None:
    complete = run_ablation(
        _task(), _packets(), AblationMode.COMPLETE_SELECTION
    )
    fragments = run_ablation(
        _task(), _packets(), AblationMode.VERIFIED_FRAGMENT_SELECTION
    )
    synthesis = run_ablation(
        _task(),
        _packets(),
        AblationMode.VERIFIED_SYNTHESIS,
        synthesis_config=SynthesisConfig(max_rounds=1, max_unique_candidates=64),
    )

    assert complete.generated_composites == 0
    assert fragments.generated_composites == 0
    assert complete.selected.visible_matched == 3
    assert fragments.selected.visible_matched == 3
    assert canonical_text(synthesis.selected.expression) == "AND(A,B)"
    assert synthesis.selected.visible_matched == 4
    assert synthesis.generated_composites > 0


def test_external_score_cannot_change_ablation_selection() -> None:
    positive = run_ablation_suite(
        _task(),
        _packets(),
        synthesis_config=SynthesisConfig(max_rounds=1, max_unique_candidates=64),
        external_score=lambda expression: 1.0,
    )
    negative = run_ablation_suite(
        _task(),
        _packets(),
        synthesis_config=SynthesisConfig(max_rounds=1, max_unique_candidates=64),
        external_score=lambda expression: -1.0,
    )

    assert [item.selected.candidate_id for item in positive] == [
        item.selected.candidate_id for item in negative
    ]
    assert [item.external_score for item in positive] == [1.0] * 4
    assert [item.external_score for item in negative] == [-1.0] * 4


def test_ablation_suite_has_one_deterministic_outcome_per_mode() -> None:
    suite = run_ablation_suite(_task(), _packets())

    assert tuple(item.mode for item in suite) == tuple(AblationMode)
    assert suite == run_ablation_suite(_task(), tuple(reversed(_packets())))
