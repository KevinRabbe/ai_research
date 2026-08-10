from plural_cognition.boolean_world import (
    And,
    EvidenceCase,
    Not,
    Or,
    PublicTask,
    Var,
)
from plural_cognition.population import (
    FragmentRole,
    HypothesisFragment,
    HypothesisPacket,
    analyze_population_knowledge,
    validate_and_hash_packet,
)


def _task() -> PublicTask:
    return PublicTask(
        "TASK-KNOWLEDGE",
        ("A", "B"),
        (
            EvidenceCase("E00", (False, False), False),
            EvidenceCase("E01", (False, True), False),
            EvidenceCase("E10", (True, False), False),
            EvidenceCase("E11", (True, True), True),
        ),
        (),
    )


def test_report_separates_unique_and_shared_verified_knowledge() -> None:
    first = HypothesisPacket(
        "M0",
        Var("A"),
        (
            HypothesisFragment("A", Var("A"), FragmentRole.ATOM),
            HypothesisFragment(
                "AND",
                And((Var("A"), Not(Var("B")))),
                FragmentRole.ALTERNATIVE,
            ),
        ),
        counterexample_case_ids=("E10",),
    )
    second = HypothesisPacket(
        "M1",
        Var("B"),
        (
            HypothesisFragment("B", Var("B"), FragmentRole.ATOM),
            HypothesisFragment("A2", Var("A"), FragmentRole.ATOM),
            HypothesisFragment(
                "OR",
                Or((Var("A"), Var("B"))),
                FragmentRole.ALTERNATIVE,
            ),
        ),
        counterexample_case_ids=("E01",),
    )
    report = analyze_population_knowledge(
        _task(),
        (
            validate_and_hash_packet(first, _task()),
            validate_and_hash_packet(second, _task()),
        ),
    )

    m0 = report.for_member("M0")
    m1 = report.for_member("M1")
    assert set(m0.verified_counterexample_case_ids) == {"E10"}
    assert set(m1.verified_counterexample_case_ids) == {"E01"}
    assert m0.unique_counterexample_case_ids == ("E10",)
    assert m1.unique_counterexample_case_ids == ("E01",)
    assert "AND" in m0.unique_operators
    assert "OR" in m1.unique_operators
    assert len(m0.unique_verified_fragment_semantics) == 1
    assert len(m1.unique_verified_fragment_semantics) == 2
    shared = [owners for _, owners in report.fragment_owners if owners == ("M0", "M1")]
    assert len(shared) == 1


def test_false_fragment_metadata_contributes_neither_semantics_nor_operator() -> None:
    packet = HypothesisPacket(
        "M0",
        Var("A"),
        (
            HypothesisFragment(
                "BAD",
                Or((Var("A"), Var("B"))),
                FragmentRole.ALTERNATIVE,
                supporting_case_ids=("E10",),
            ),
        ),
    )
    other = HypothesisPacket(
        "M1",
        Var("B"),
        (HypothesisFragment("B", Var("B"), FragmentRole.ATOM),),
    )
    report = analyze_population_knowledge(
        _task(),
        (
            validate_and_hash_packet(packet, _task()),
            validate_and_hash_packet(other, _task()),
        ),
    )

    m0 = report.for_member("M0")
    assert m0.verified_fragment_semantics == ()
    assert "OR" not in m0.accepted_operators


def test_report_is_packet_order_invariant() -> None:
    packets = (
        validate_and_hash_packet(
            HypothesisPacket(
                "M0",
                Var("A"),
                (HypothesisFragment("A", Var("A"), FragmentRole.ATOM),),
            ),
            _task(),
        ),
        validate_and_hash_packet(
            HypothesisPacket(
                "M1",
                Var("B"),
                (HypothesisFragment("B", Var("B"), FragmentRole.ATOM),),
            ),
            _task(),
        ),
    )
    assert analyze_population_knowledge(_task(), packets) == analyze_population_knowledge(
        _task(), tuple(reversed(packets))
    )
