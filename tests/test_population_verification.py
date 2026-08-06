import pytest

from plural_cognition.boolean_world import (
    And,
    EvidenceCase,
    PublicTask,
    Var,
)
from plural_cognition.population import (
    FragmentPrediction,
    FragmentRole,
    HypothesisFragment,
    HypothesisPacket,
    ValidatedPacket,
    audit_visible_packet,
    validate_and_hash_packet,
)


def _task() -> PublicTask:
    return PublicTask(
        "TASK-VISIBLE",
        ("A", "B"),
        (
            EvidenceCase("E0", (False, False), False),
            EvidenceCase("E1", (True, False), False),
            EvidenceCase("E2", (True, True), True),
        ),
        (),
    )


def test_visible_audit_accepts_truthful_fragment_metadata() -> None:
    packet = HypothesisPacket(
        member_id="M0",
        complete_candidate=And((Var("A"), Var("B"))),
        fragments=(
            HypothesisFragment(
                "F0",
                Var("A"),
                FragmentRole.ATOM,
                supporting_case_ids=("E0", "E2"),
                contradicting_case_ids=("E1",),
                predictions=(
                    FragmentPrediction("E0", False),
                    FragmentPrediction("E2", True),
                ),
            ),
        ),
    )
    audit = audit_visible_packet(validate_and_hash_packet(packet, _task()), _task())

    assert audit.candidate.consistent is True
    assert audit.metadata_verified is True
    assert audit.verified_fragment_ids == ("F0",)
    assert audit.fragments[0].matched_visible == 2
    assert audit.fragments[0].mismatch_case_ids == ("E1",)


def test_visible_audit_rejects_false_support_prediction_and_counterexample_claims() -> None:
    packet = HypothesisPacket(
        member_id="M0",
        complete_candidate=And((Var("A"), Var("B"))),
        fragments=(
            HypothesisFragment(
                "F0",
                Var("A"),
                FragmentRole.ATOM,
                supporting_case_ids=("E1",),
                predictions=(FragmentPrediction("E0", True),),
            ),
        ),
        counterexample_case_ids=("E2",),
    )
    audit = audit_visible_packet(validate_and_hash_packet(packet, _task()), _task())

    assert audit.metadata_verified is False
    assert audit.verified_fragment_ids == ()
    assert audit.fragments[0].metadata_errors == (
        "prediction claim fails on E0",
        "support claim fails on E1",
    )
    assert audit.counterexample_errors == ("counterexample claim fails on E2",)


def test_visible_audit_preserves_wrong_candidate_with_truthful_counterexample() -> None:
    packet = HypothesisPacket(
        member_id="M0",
        complete_candidate=Var("A"),
        fragments=(
            HypothesisFragment("F0", Var("A"), FragmentRole.ALTERNATIVE),
        ),
        counterexample_case_ids=("E1",),
    )
    audit = audit_visible_packet(validate_and_hash_packet(packet, _task()), _task())

    assert audit.candidate.consistent is False
    assert audit.candidate.mismatch_case_ids == ("E1",)
    assert audit.metadata_verified is True
    assert audit.counterexample_errors == ()


def test_visible_audit_revalidates_packet_task_binding() -> None:
    valid = validate_and_hash_packet(
        HypothesisPacket(
            "M0",
            Var("A"),
            (HypothesisFragment("F0", Var("A"), FragmentRole.ATOM),),
        ),
        _task(),
    )
    forged = ValidatedPacket(valid.packet, valid.task_id, "0" * 64, valid.canonical_bytes)

    with pytest.raises(ValueError, match="does not belong"):
        audit_visible_packet(forged, _task())
