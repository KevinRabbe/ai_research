import pytest

from plural_cognition.boolean_world import (
    And,
    EvidenceCase,
    Not,
    PublicTask,
    Var,
)
from plural_cognition.population import (
    EdgeKind,
    FragmentRole,
    HypothesisFragment,
    HypothesisPacket,
    NodeKind,
    SynthesisConfig,
    build_provenance_graph,
    integrate_synthesis_result,
    synthesize_visible,
    validate_and_hash_packet,
)


def _task() -> PublicTask:
    return PublicTask(
        "TASK-GRAPH-SYNTHESIS",
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


def test_generated_candidate_and_hyperedge_enter_graph() -> None:
    packets = _packets()
    base = build_provenance_graph(_task(), packets)
    result = synthesize_visible(
        _task(), packets, SynthesisConfig(max_rounds=1, max_unique_candidates=64)
    )
    integrated = integrate_synthesis_result(base, result)

    best = result.best
    node = next(item for item in integrated.nodes if item.node_id == best.candidate_id)
    assert node.kind is NodeKind.CANDIDATE
    assert {source.member_id for source in node.sources} == {"M0", "M1"}

    derivations = [
        edge
        for edge in integrated.edges
        if edge.kind is EdgeKind.DERIVED_FROM
        and edge.target_node_id == best.candidate_id
        and edge.label == "and"
    ]
    assert len(derivations) == 1
    assert len(derivations[0].source_node_ids) == 2
    assert set(derivations[0].source_node_ids).issubset(
        {candidate.candidate_id for candidate in result.candidates}
    )


def test_initial_fragment_promotion_is_explicit() -> None:
    packets = _packets()
    result = synthesize_visible(_task(), packets)
    integrated = integrate_synthesis_result(
        build_provenance_graph(_task(), packets), result
    )

    promoted = [
        edge
        for edge in integrated.edges
        if edge.kind is EdgeKind.DERIVED_FROM
        and edge.label == "initial-fragment"
    ]
    assert promoted
    assert all(
        all(source_id.startswith("fragment:") for source_id in edge.source_node_ids)
        for edge in promoted
    )
    assert all(edge.target_node_id.startswith("candidate:") for edge in promoted)


def test_graph_integration_is_packet_order_invariant() -> None:
    packets = _packets()

    def build(order):
        result = synthesize_visible(_task(), order)
        graph = build_provenance_graph(_task(), order)
        return integrate_synthesis_result(graph, result)

    forward = build(packets)
    reverse = build(tuple(reversed(packets)))
    assert forward.canonical_bytes() == reverse.canonical_bytes()
    assert forward.sha256() == reverse.sha256()


def test_graph_integration_enforces_resource_limits() -> None:
    packets = _packets()
    result = synthesize_visible(_task(), packets)
    base = build_provenance_graph(_task(), packets)

    with pytest.raises(ValueError, match="node limit"):
        integrate_synthesis_result(base, result, max_nodes=len(base.nodes))
