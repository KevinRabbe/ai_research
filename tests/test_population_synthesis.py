from plural_cognition.boolean_world import (
    And,
    EvidenceCase,
    Not,
    Or,
    PublicTask,
    Var,
    canonical_text,
)
from plural_cognition.population import (
    FragmentRole,
    HypothesisFragment,
    HypothesisPacket,
    SynthesisConfig,
    synthesize_visible,
    validate_and_hash_packet,
)


def _task() -> PublicTask:
    return PublicTask(
        "TASK-SYNTHESIS",
        ("A", "B"),
        (
            EvidenceCase("E00", (False, False), False),
            EvidenceCase("E01", (False, True), False),
            EvidenceCase("E10", (True, False), False),
            EvidenceCase("E11", (True, True), True),
        ),
        (),
    )


def _population():
    first = HypothesisPacket(
        member_id="M0",
        complete_candidate=Var("A"),
        fragments=(
            HypothesisFragment("A", Var("A"), FragmentRole.ATOM),
            HypothesisFragment(
                "OP",
                And((Var("A"), Not(Var("B")))),
                FragmentRole.ALTERNATIVE,
            ),
        ),
    )
    second = HypothesisPacket(
        member_id="M1",
        complete_candidate=Var("B"),
        fragments=(
            HypothesisFragment("B", Var("B"), FragmentRole.ATOM),
        ),
    )
    return (
        validate_and_hash_packet(first, _task()),
        validate_and_hash_packet(second, _task()),
    )


def test_synthesis_constructs_novel_exact_multi_source_candidate() -> None:
    result = synthesize_visible(
        _task(),
        _population(),
        SynthesisConfig(max_rounds=1, max_unique_candidates=64),
    )

    assert canonical_text(result.best.expression) == "AND(A,B)"
    assert result.best.visible_consistent is True
    assert result.best.novel_semantic_composition is True
    assert {source.member_id for source in result.best.sources} == {"M0", "M1"}
    assert result.trace.allowed_operators == ("AND", "NOT")
    assert result.trace.stopped_reason == "completed"


def test_synthesis_is_deterministic_across_packet_order() -> None:
    packets = _population()
    forward = synthesize_visible(_task(), packets)
    reverse = synthesize_visible(_task(), tuple(reversed(packets)))

    assert forward == reverse


def test_synthesis_does_not_invent_unproposed_operator() -> None:
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
    result = synthesize_visible(_task(), packets)

    assert result.trace.allowed_operators == ()
    assert all(candidate.canonical_expression != "AND(A,B)" for candidate in result.candidates)
    assert result.best.visible_matched == 3


def test_unverified_fragment_cannot_contribute_operator_or_expression() -> None:
    bad = HypothesisPacket(
        member_id="M0",
        complete_candidate=Var("A"),
        fragments=(
            HypothesisFragment(
                "BAD",
                Or((Var("A"), Var("B"))),
                FragmentRole.ALTERNATIVE,
                supporting_case_ids=("E10",),
            ),
        ),
    )
    other = HypothesisPacket(
        member_id="M1",
        complete_candidate=Var("B"),
        fragments=(HypothesisFragment("B", Var("B"), FragmentRole.ATOM),),
    )
    result = synthesize_visible(
        _task(),
        (
            validate_and_hash_packet(bad, _task()),
            validate_and_hash_packet(other, _task()),
        ),
    )

    assert result.trace.excluded_unverified_fragments == 1
    assert "OR" not in result.trace.allowed_operators
    assert all(candidate.canonical_expression != "OR(A,B)" for candidate in result.candidates)


def test_synthesis_stops_at_explicit_resource_bound() -> None:
    result = synthesize_visible(
        _task(),
        _population(),
        SynthesisConfig(
            max_rounds=3,
            max_unique_candidates=64,
            max_candidate_evaluations=128,
            max_generated_composites=1,
        ),
    )

    assert result.trace.generated_composites == 1
    assert result.trace.stopped_reason == "generated-composite-limit"
