import math

import pytest

from plural_cognition.boolean_world import (
    And,
    EvidenceCase,
    Not,
    PublicTask,
    Var,
    semantic_distance,
)
from plural_cognition.population import (
    FragmentRole,
    HypothesisFragment,
    HypothesisPacket,
    SynthesisConfig,
    evaluate_synthesis_coalitions,
    validate_and_hash_packet,
)


def _task() -> PublicTask:
    return PublicTask(
        "TASK-COALITION",
        ("A", "B"),
        (
            EvidenceCase("E00", (False, False), False),
            EvidenceCase("E01", (False, True), False),
            EvidenceCase("E10", (True, False), False),
            EvidenceCase("E11", (True, True), True),
        ),
        (),
    )


def _packet_a():
    packet = HypothesisPacket(
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
    return validate_and_hash_packet(packet, _task())


def _packet_b(member_id: str = "M1"):
    packet = HypothesisPacket(
        member_id,
        Var("B"),
        (HypothesisFragment("B", Var("B"), FragmentRole.ATOM),),
    )
    return validate_and_hash_packet(packet, _task())


def _score(expression) -> float:
    target = And((Var("A"), Var("B")))
    return 1.0 - semantic_distance(expression, target, _task().variable_order) / 4.0


def _config() -> SynthesisConfig:
    return SynthesisConfig(max_rounds=1, max_unique_candidates=64)


def test_coalition_report_runs_every_subset_and_attributes_realized_gain() -> None:
    calls = 0

    def score(expression) -> float:
        nonlocal calls
        calls += 1
        return _score(expression)

    report = evaluate_synthesis_coalitions(
        _task(),
        (_packet_a(), _packet_b()),
        score,
        synthesis_config=_config(),
    )

    assert len(report.outcomes) == 4
    assert calls == 3
    assert report.full_outcome.selected_canonical_expression == "AND(A,B)"
    assert report.full_outcome.score == 1.0
    assert report.full_outcome.novel_semantic_composition is True
    assert report.full_provenance_members == ("M0", "M1")
    assert report.score_necessary_members == ("M0", "M1")

    contributions = {item.member_id: item for item in report.contributions}
    assert contributions["M0"].full_score_drop == 0.25
    assert contributions["M1"].full_score_drop == 0.25
    assert contributions["M0"].shapley_value == pytest.approx(0.5)
    assert contributions["M1"].shapley_value == pytest.approx(0.5)
    assert sum(item.shapley_value for item in report.contributions) == pytest.approx(1.0)


def test_provenance_is_not_confused_with_realized_necessity() -> None:
    report = evaluate_synthesis_coalitions(
        _task(),
        (_packet_a(), _packet_b("M1"), _packet_b("M2")),
        _score,
        synthesis_config=_config(),
    )

    assert report.full_provenance_members == ("M0", "M1", "M2")
    assert report.score_necessary_members == ("M0",)
    contributions = {item.member_id: item for item in report.contributions}
    assert contributions["M1"].appears_in_full_provenance is True
    assert contributions["M2"].appears_in_full_provenance is True
    assert contributions["M1"].full_score_drop == 0.0
    assert contributions["M2"].full_score_drop == 0.0
    assert contributions["M1"].changes_selected_semantics is False
    assert contributions["M2"].changes_selected_semantics is False


def test_external_score_cannot_change_visible_synthesis_selection() -> None:
    packets = (_packet_a(), _packet_b())
    exact = evaluate_synthesis_coalitions(
        _task(), packets, _score, synthesis_config=_config()
    )
    inverted = evaluate_synthesis_coalitions(
        _task(), packets, lambda expression: 1.0 - _score(expression), synthesis_config=_config()
    )

    assert {
        coalition: outcome.selected_candidate_id
        for coalition, outcome in exact.outcomes.items()
    } == {
        coalition: outcome.selected_candidate_id
        for coalition, outcome in inverted.outcomes.items()
    }


def test_coalition_report_rejects_duplicate_members_and_nonfinite_scores() -> None:
    with pytest.raises(ValueError, match="duplicate member"):
        evaluate_synthesis_coalitions(
            _task(),
            (_packet_b("M1"), _packet_b("M1")),
            _score,
        )

    with pytest.raises(ValueError, match="non-finite"):
        evaluate_synthesis_coalitions(
            _task(),
            (_packet_a(),),
            lambda expression: math.nan,
        )

    with pytest.raises(ValueError, match="empty_value"):
        evaluate_synthesis_coalitions(
            _task(),
            (_packet_a(),),
            _score,
            empty_value=math.inf,
        )
