import pytest

from plural_cognition.boolean_world import (
    And,
    EvidenceCase,
    InterventionCase,
    Not,
    Or,
    PublicTask,
    Var,
)
from plural_cognition.population import (
    EdgeKind,
    EvidenceNode,
    ExpressionNode,
    FragmentRole,
    GraphEdge,
    HypothesisFragment,
    HypothesisPacket,
    NodeKind,
    ProvenanceGraph,
    ValidatedPacket,
    build_provenance_graph,
    validate_and_hash_packet,
)


def _task() -> PublicTask:
    return PublicTask(
        task_id="TASK-GRAPH",
        variable_order=("A", "B"),
        evidence=(
            EvidenceCase("E0", (False, False), False),
            EvidenceCase("E1", (True, False), False),
            EvidenceCase("E2", (True, True), True),
        ),
        interventions=(
            InterventionCase("I0", "A", "E0", "E1", False),
        ),
    )


def _validated(
    member_id: str,
    fragment_expression,
    *,
    fragment_id: str = "F0",
    counterexamples: tuple[str, ...] = (),
    uncertain: bool = False,
):
    packet = HypothesisPacket(
        member_id=member_id,
        complete_candidate=And((Var("A"), Var("B"))),
        fragments=(
            HypothesisFragment(
                fragment_id,
                fragment_expression,
                FragmentRole.CLAUSE,
                supporting_case_ids=("E2",),
                contradicting_case_ids=("E0",),
            ),
        ),
        counterexample_case_ids=counterexamples,
        uncertainty_fragment_ids=(fragment_id,) if uncertain else (),
    )
    return validate_and_hash_packet(packet, _task())


def test_graph_is_deterministic_across_packet_order() -> None:
    first = _validated("M0", And((Var("A"), Var("B"))))
    second = _validated(
        "M1", Not(Or((Not(Var("A")), Not(Var("B"))))), uncertain=True
    )

    left = build_provenance_graph(_task(), (first, second))
    right = build_provenance_graph(_task(), (second, first))

    assert left == right
    assert left.canonical_bytes() == right.canonical_bytes()
    assert left.sha256() == right.sha256()


def test_semantically_equivalent_fragments_merge_without_losing_sources() -> None:
    first = _validated("M0", And((Var("A"), Var("B"))))
    second = _validated(
        "M1", Not(Or((Not(Var("A")), Not(Var("B")))))
    )
    graph = build_provenance_graph(_task(), (first, second))

    fragments = [
        node
        for node in graph.nodes
        if isinstance(node, ExpressionNode) and node.kind is NodeKind.FRAGMENT
    ]
    assert len(fragments) == 1
    fragment = fragments[0]
    assert fragment.equivalent_forms == (
        "AND(A,B)",
        "NOT(OR(NOT(A),NOT(B)))",
    )
    assert {source.member_id for source in fragment.sources} == {"M0", "M1"}
    assert len(fragment.sources) == 2


def test_graph_contains_intervention_hyperedge_and_packet_markers() -> None:
    packet = _validated(
        "M0",
        Var("A"),
        counterexamples=("E1",),
        uncertain=True,
    )
    graph = build_provenance_graph(_task(), (packet,))

    intervention_edges = [
        edge
        for edge in graph.edges
        if edge.kind is EdgeKind.DERIVED_FROM
        and edge.target_node_id == "intervention:I0"
    ]
    assert len(intervention_edges) == 1
    assert intervention_edges[0].source_node_ids == ("evidence:E0", "evidence:E1")
    assert any(node.kind is NodeKind.COUNTEREXAMPLE for node in graph.nodes)
    assert any(node.kind is NodeKind.UNCERTAINTY for node in graph.nodes)


def test_graph_revalidates_packets_and_rejects_duplicate_members() -> None:
    valid = _validated("M0", Var("A"))
    forged = ValidatedPacket(
        valid.packet,
        valid.task_id,
        "0" * 64,
        valid.canonical_bytes,
    )
    with pytest.raises(ValueError, match="does not belong"):
        build_provenance_graph(_task(), (forged,))

    other_packet = HypothesisPacket(
        member_id="M0",
        complete_candidate=Var("A"),
        fragments=(
            HypothesisFragment("F1", Var("B"), FragmentRole.ALTERNATIVE),
        ),
    )
    other = validate_and_hash_packet(other_packet, _task())
    with pytest.raises(ValueError, match="unique member"):
        build_provenance_graph(_task(), (valid, other))


def test_graph_contract_rejects_unknown_edges_and_resource_overflow() -> None:
    evidence = EvidenceNode("evidence:E0", "E0", (False, False), False)
    invalid_edge = GraphEdge(
        "edge:0",
        EdgeKind.SUPPORTS,
        ("missing",),
        evidence.node_id,
    )
    with pytest.raises(ValueError, match="unknown nodes"):
        ProvenanceGraph(
            "TASK",
            ("A", "B"),
            (evidence,),
            (invalid_edge,),
        )

    packet = _validated("M0", Var("A"), uncertain=True)
    with pytest.raises(ValueError, match="node limit"):
        build_provenance_graph(_task(), (packet,), max_nodes=1)
    with pytest.raises(ValueError, match="edge limit"):
        build_provenance_graph(_task(), (packet,), max_edges=1)
