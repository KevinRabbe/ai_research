"""Insert bounded synthesis results into an immutable provenance graph."""

from __future__ import annotations

import json
from hashlib import sha256

from .graph import (
    EdgeKind,
    ExpressionNode,
    GraphEdge,
    NodeKind,
    ProvenanceGraph,
    SourceRef,
)
from .synthesis import SynthesisResult, SynthesisRule


def _source_payload(source: SourceRef) -> dict[str, str]:
    return {
        "member_id": source.member_id,
        "packet_sha256": source.packet_sha256,
        "local_id": source.local_id,
    }


def _derivation_edge(
    source_node_ids: tuple[str, ...],
    target_node_id: str,
    sources: tuple[SourceRef, ...],
    label: str,
) -> GraphEdge:
    source_ids = tuple(sorted(set(source_node_ids)))
    source_refs = tuple(sorted(set(sources)))
    payload = {
        "kind": EdgeKind.DERIVED_FROM.value,
        "source_node_ids": source_ids,
        "target_node_id": target_node_id,
        "sources": [_source_payload(source) for source in source_refs],
        "label": label,
    }
    identity = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return GraphEdge(
        f"edge:{sha256(identity).hexdigest()[:24]}",
        EdgeKind.DERIVED_FROM,
        source_ids,
        target_node_id,
        source_refs,
        label,
    )


def _fragment_node_for_source(
    nodes: dict[str, object], source: SourceRef, semantic_hex: str
) -> str | None:
    for node in nodes.values():
        if not isinstance(node, ExpressionNode):
            continue
        if node.kind is not NodeKind.FRAGMENT:
            continue
        if node.semantic_bitset_hex != semantic_hex:
            continue
        if source in node.sources:
            return node.node_id
    return None


def integrate_synthesis_result(
    graph: ProvenanceGraph,
    result: SynthesisResult,
    *,
    max_nodes: int = 8192,
    max_edges: int = 32768,
) -> ProvenanceGraph:
    """Return a new graph containing synthesis candidates and derivations.

    Candidate IDs are exact semantic identities, so repeated or equivalent
    generated forms merge into the existing candidate node while preserving all
    source and derivation provenance.
    """

    if max_nodes < 1 or max_edges < 1:
        raise ValueError("graph resource limits must be positive")

    nodes: dict[str, object] = {node.node_id: node for node in graph.nodes}
    edges = set(graph.edges)

    for candidate in result.candidates:
        if not candidate.candidate_id.startswith("candidate:"):
            raise ValueError("synthesis candidate ID is not a semantic candidate ID")
        semantic_hex = candidate.candidate_id.split(":", 1)[1]
        forms = tuple(
            sorted(
                set(candidate.equivalent_forms).union(
                    (candidate.canonical_expression,)
                )
            )
        )
        existing = nodes.get(candidate.candidate_id)
        if existing is None:
            nodes[candidate.candidate_id] = ExpressionNode(
                candidate.candidate_id,
                NodeKind.CANDIDATE,
                semantic_hex,
                forms[0],
                forms,
                (),
                tuple(sorted(set(candidate.sources))),
            )
        else:
            if not isinstance(existing, ExpressionNode):
                raise ValueError("candidate ID collides with a non-expression graph node")
            if existing.kind is not NodeKind.CANDIDATE:
                raise ValueError("candidate ID collides with a non-candidate expression")
            if existing.semantic_bitset_hex != semantic_hex:
                raise ValueError("candidate semantic identity mismatch")
            merged_forms = tuple(
                sorted(set(existing.equivalent_forms).union(forms))
            )
            merged_sources = tuple(
                sorted(set(existing.sources).union(candidate.sources))
            )
            nodes[candidate.candidate_id] = ExpressionNode(
                candidate.candidate_id,
                NodeKind.CANDIDATE,
                semantic_hex,
                merged_forms[0],
                merged_forms,
                (),
                merged_sources,
            )

    for candidate in result.candidates:
        semantic_hex = candidate.candidate_id.split(":", 1)[1]
        for derivation in candidate.derivations:
            if derivation.rule is SynthesisRule.INITIAL_CANDIDATE:
                continue
            if derivation.rule is SynthesisRule.INITIAL_FRAGMENT:
                fragment_sources = tuple(
                    source
                    for source in candidate.sources
                    if source.local_id != "complete_candidate"
                )
                parent_ids = tuple(
                    sorted(
                        {
                            fragment_node
                            for source in fragment_sources
                            if (
                                fragment_node := _fragment_node_for_source(
                                    nodes, source, semantic_hex
                                )
                            )
                            is not None
                        }
                    )
                )
                if not parent_ids:
                    raise ValueError(
                        "initial fragment candidate has no matching fragment node"
                    )
            else:
                parent_ids = derivation.parent_candidate_ids
                missing = set(parent_ids).difference(nodes)
                if missing:
                    raise ValueError(
                        f"synthesis derivation references unknown candidates: {sorted(missing)!r}"
                    )
            edges.add(
                _derivation_edge(
                    parent_ids,
                    candidate.candidate_id,
                    candidate.sources,
                    derivation.rule.value,
                )
            )

    ordered_nodes = tuple(sorted(nodes.values(), key=lambda node: node.node_id))
    ordered_edges = tuple(sorted(edges, key=lambda edge: edge.edge_id))
    if len(ordered_nodes) > max_nodes:
        raise ValueError(
            f"graph node limit exceeded: {len(ordered_nodes)} > {max_nodes}"
        )
    if len(ordered_edges) > max_edges:
        raise ValueError(
            f"graph edge limit exceeded: {len(ordered_edges)} > {max_edges}"
        )
    return ProvenanceGraph(
        graph.task_id,
        graph.variable_order,
        ordered_nodes,
        ordered_edges,
    )
