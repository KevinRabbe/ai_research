import pytest

from plural_cognition.boolean_world import And, EvidenceCase, PublicTask, Var
from plural_cognition.population import (
    FragmentPrediction,
    FragmentRole,
    HypothesisFragment,
    HypothesisPacket,
    validate_and_hash_packet,
)


def _task() -> PublicTask:
    return PublicTask(
        task_id="TASK-1",
        variable_order=("A", "B"),
        evidence=(
            EvidenceCase("E0", (False, False), False),
            EvidenceCase("E1", (True, False), False),
            EvidenceCase("E2", (True, True), True),
        ),
        interventions=(),
    )


def _packet(fragment_order: tuple[str, ...] = ("F1", "F2")) -> HypothesisPacket:
    fragments = {
        "F1": HypothesisFragment(
            fragment_id="F1",
            expression=Var("A"),
            role=FragmentRole.ATOM,
            supporting_case_ids=("E2",),
            predictions=(FragmentPrediction("E1", True),),
            confidence=0.75,
        ),
        "F2": HypothesisFragment(
            fragment_id="F2",
            expression=Var("B"),
            role=FragmentRole.CONDITION,
            supporting_case_ids=("E2",),
            contradicting_case_ids=("E0",),
            predictions=(FragmentPrediction("E1", False),),
            confidence=0.625,
        ),
    }
    return HypothesisPacket(
        member_id="M0",
        complete_candidate=And((Var("A"), Var("B"))),
        fragments=tuple(fragments[item] for item in fragment_order),
        counterexample_case_ids=("E1",),
        uncertainty_fragment_ids=("F1",),
    )


def test_packet_hash_is_canonical_across_nonsemantic_ordering() -> None:
    first = validate_and_hash_packet(_packet(("F1", "F2")), _task())
    second = validate_and_hash_packet(_packet(("F2", "F1")), _task())

    assert first.canonical_sha256 == second.canonical_sha256
    assert first.canonical_bytes == second.canonical_bytes
    assert len(first.canonical_sha256) == 64
    assert first.task_id == "TASK-1"


def test_packet_hash_binds_member_and_complete_public_task() -> None:
    base = _packet()
    other_member = HypothesisPacket(
        member_id="M1",
        complete_candidate=base.complete_candidate,
        fragments=base.fragments,
        counterexample_case_ids=base.counterexample_case_ids,
        uncertainty_fragment_ids=base.uncertainty_fragment_ids,
    )
    renamed_task = PublicTask(
        "TASK-2", _task().variable_order, _task().evidence, _task().interventions
    )
    changed_evidence_same_id = PublicTask(
        "TASK-1",
        _task().variable_order,
        (
            EvidenceCase("E0", (False, False), True),
            *_task().evidence[1:],
        ),
        _task().interventions,
    )

    base_hash = validate_and_hash_packet(base, _task()).canonical_sha256

    assert validate_and_hash_packet(other_member, _task()).canonical_sha256 != base_hash
    assert validate_and_hash_packet(base, renamed_task).canonical_sha256 != base_hash
    assert (
        validate_and_hash_packet(base, changed_evidence_same_id).canonical_sha256
        != base_hash
    )


def test_packet_validation_rejects_unknown_variables_and_case_references() -> None:
    unknown_variable = HypothesisPacket(
        member_id="M0",
        complete_candidate=Var("OUTSIDE"),
        fragments=(
            HypothesisFragment("F0", Var("A"), FragmentRole.ATOM),
        ),
    )
    unknown_case = HypothesisPacket(
        member_id="M0",
        complete_candidate=Var("A"),
        fragments=(
            HypothesisFragment(
                "F0",
                Var("A"),
                FragmentRole.ATOM,
                supporting_case_ids=("MISSING",),
            ),
        ),
    )

    with pytest.raises(ValueError, match="out-of-task"):
        validate_and_hash_packet(unknown_variable, _task())
    with pytest.raises(ValueError, match="unknown cases"):
        validate_and_hash_packet(unknown_case, _task())


def test_packet_contract_rejects_ambiguous_or_invalid_metadata() -> None:
    with pytest.raises(ValueError, match="both support and contradict"):
        HypothesisFragment(
            "F0",
            Var("A"),
            FragmentRole.ATOM,
            supporting_case_ids=("E0",),
            contradicting_case_ids=("E0",),
        )
    with pytest.raises(ValueError, match="confidence"):
        HypothesisFragment(
            "F0", Var("A"), FragmentRole.ATOM, confidence=float("nan")
        )
    with pytest.raises(TypeError, match="confidence"):
        HypothesisFragment(
            "F0", Var("A"), FragmentRole.ATOM, confidence=True
        )
    with pytest.raises(ValueError, match="unknown fragments"):
        HypothesisPacket(
            member_id="M0",
            complete_candidate=Var("A"),
            fragments=(HypothesisFragment("F0", Var("A"), FragmentRole.ATOM),),
            uncertainty_fragment_ids=("F1",),
        )
