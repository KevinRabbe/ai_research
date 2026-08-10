"""Typed, immutable provenance graph for plural-cognition hypothesis packets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Iterable, Sequence, TypeAlias

from plural_cognition.boolean_world.canonical import canonical_text
from plural_cognition.boolean_world.semantics import semantic_key
from plural_cognition.boolean_world.world import PublicTask

from .packet import FragmentRole, ValidatedPacket, validate_and_hash_packet


class NodeKind(str, Enum):
    EVIDENCE = "evidence"
    INTERVENTION = "intervention"
    FRAGMENT = "fragment"
    CANDIDATE = "candidate"
    COUNTEREXAMPLE = "counterexample"
    UNCERTAINTY = "uncertainty"


class EdgeKind(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DERIVED_FROM = "derived-from"
    PART_OF = "part-of"
    EQUIVALENT_TO = "equivalent-to"
    REPAIRS = "repairs"
    PREDICTS = "predicts"


@dataclass(frozen=True, order=True, slots=True)
class SourceRef:
    member_id: str
    packet_sha256: str
    local_id: str

    def __post_init__(self) -> None:
        if not self.member_id or not self.local_id:
            raise ValueError("source member_id and local_id must not be empty")
        if len(self.packet_sha256) != 64:
            raise ValueError("source packet_sha256 must contain 64 hexadecimal characters")
        try:
            int(self.packet_sha256, 16)
        except ValueError as exc:
            raise ValueError(
                "source packet_sha256 must contain 64 hexadecimal characters"
            ) from exc
        if self.packet_sha256 != self.packet_sha256.lower():
            raise ValueError("source packet_sha256 must use lowercase hexadecimal")


@dataclass(frozen=True, slots=True)
class EvidenceNode:
    node_id: str
    case_id: str
    assignment: tuple[bool, ...]
    output: bool

    @property
    def kind(self) -> NodeKind:
        return NodeKind.EVIDENCE

    def __post_init__(self) -> None:
        if not self.node_id or not self.case_id:
            raise ValueError("evidence node identifiers must not be empty")
        if any(type(value) is not bool for value in self.assignment):
            raise TypeError("evidence assignment values must be bool")
        if type(self.output) is not bool:
            raise TypeError("evidence output must be bool")


@dataclass(frozen=True, slots=True)
class InterventionNode:
    node_id: str
    intervention_id: str
    variable: str
    before_case_id: str
    after_case_id: str
    changed_output: bool

    @property
    def kind(self) -> NodeKind:
        return NodeKind.INTERVENTION

    def __post_init__(self) -> None:
        if not all(
            (
                self.node_id,
                self.intervention_id,
                self.variable,
                self.before_case_id,
                self.after_case_id,
            )
        ):
            raise ValueError("intervention node identifiers must not be empty")
        if type(self.changed_output) is not bool:
            raise TypeError("intervention changed_output must be bool")


@dataclass(frozen=True, slots=True)
class ExpressionNode:
    node_id: str
    kind: NodeKind
    semantic_bitset_hex: str
    representative_expression: str
    equivalent_forms: tuple[str, ...]
    roles: tuple[FragmentRole, ...]
    sources: tuple[SourceRef, ...]

    def __post_init__(self) -> None:
        if self.kind not in (NodeKind.FRAGMENT, NodeKind.CANDIDATE):
            raise ValueError("expression node kind must be fragment or candidate")
        if not self.node_id or not self.semantic_bitset_hex:
            raise ValueError("expression node identifiers must not be empty")
        if not self.equivalent_forms or not self.sources:
            raise ValueError("expression node requires forms and provenance sources")
        if tuple(sorted(set(self.equivalent_forms))) != self.equivalent_forms:
            raise ValueError("equivalent_forms must be sorted and unique")
        if self.representative_expression != self.equivalent_forms[0]:
            raise ValueError("representative_expression must be the first equivalent form")
        if tuple(sorted(set(self.sources))) != self.sources:
            raise ValueError("expression sources must be sorted and unique")
        if tuple(sorted(set(self.roles), key=lambda item: item.value)) != self.roles:
            raise ValueError("expression roles must be sorted and unique")
        if self.kind is NodeKind.CANDIDATE and self.roles:
            raise ValueError("candidate nodes must not carry fragment roles")
        if self.kind is NodeKind.FRAGMENT and not self.roles:
            raise ValueError("fragment nodes require at least one role")


@dataclass(frozen=True, slots=True)
class MarkerNode:
    node_id: str
    kind: NodeKind
    reference_id: str
    sources: tuple[SourceRef, ...]

    def __post_init__(self) -> None:
        if self.kind not in (NodeKind.COUNTEREXAMPLE, NodeKind.UNCERTAINTY):
            raise ValueError("marker node kind must be counterexample or uncertainty")
        if not self.node_id or not self.reference_id or not self.sources:
            raise ValueError("marker node fields must not be empty")
        if tuple(sorted(set(self.sources))) != self.sources:
            raise ValueError("marker sources must be sorted and unique")


GraphNode: TypeAlias = EvidenceNode | InterventionNode | ExpressionNode | MarkerNode


@dataclass(frozen=True, slots=True)
class GraphEdge:
    edge_id: str
    kind: EdgeKind
    source_node_ids: tuple[str, ...]
    target_node_id: str
    sources: tuple[SourceRef, ...] = ()
    label: str = ""

    def __post_init__(self) -> None:
        if not self.edge_id or not self.target_node_id:
            raise ValueError("edge identifiers must not be empty")
        if not self.source_node_ids:
            raise ValueError("edge requires at least one source node")
        if tuple(sorted(set(self.source_node_ids))) != self.source_node_ids:
            raise ValueError("edge source_node_ids must be sorted and unique")
        if tuple(sorted(set(self.sources))) != self.sources:
            raise ValueError("edge provenance sources must be sorted and unique")


@dataclass(frozen=True, slots=True)
class ProvenanceGraph:
    task_id: str
    variable_order: tuple[str, ...]
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]

    def __post_init__(self) -> None:
        if not self.task_id or not self.variable_order:
            raise ValueError("graph task_id and variable_order must not be empty")
        if len(self.variable_order) != len(set(self.variable_order)):
            raise ValueError("graph variable_order must be unique")
        node_ids = tuple(node.node_id for node in self.nodes)
        edge_ids = tuple(edge.edge_id for edge in self.edges)
        if tuple(sorted(node_ids)) != node_ids or len(node_ids) != len(set(node_ids)):
            raise ValueError("graph nodes must be uniquely sorted by node_id")
        if tuple(sorted(edge_ids)) != edge_ids or len(edge_ids) != len(set(edge_ids)):
            raise ValueError("graph edges must be uniquely sorted by edge_id")
        known = set(node_ids)
        for edge in self.edges:
            missing = set(edge.source_node_ids).union((edge.target_node_id,)).difference(known)
            if missing:
                raise ValueError(f"edge references unknown nodes: {sorted(missing)!r}")

    def canonical_bytes(self) -> bytes:
        payload = {
            "schema": "plural-cognition-provenance-graph-v1",
            "task_id": self.task_id,
            "variable_order": list(self.variable_order),
            "nodes": [_node_payload(node) for node in self.nodes],
            "edges": [_edge_payload(edge) for edge in self.edges],
        }
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")

    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


def _source_payload(source: SourceRef) -> dict[str, str]:
    return {
        "member_id": source.member_id,
        "packet_sha256": source.packet_sha256,
        "local_id": source.local_id,
    }


def _node_payload(node: GraphNode) -> dict:
    match node:
        case EvidenceNode():
            return {
                "node_id": node.node_id,
                "kind": node.kind.value,
                "case_id": node.case_id,
                "assignment": list(node.assignment),
                "output": node.output,
            }
        case InterventionNode():
            return {
                "node_id": node.node_id,
                "kind": node.kind.value,
                "intervention_id": node.intervention_id,
                "variable": node.variable,
                "before_case_id": node.before_case_id,
                "after_case_id": node.after_case_id,
                "changed_output": node.changed_output,
            }
        case ExpressionNode():
            return {
                "node_id": node.node_id,
                "kind": node.kind.value,
                "semantic_bitset_hex": node.semantic_bitset_hex,
                "representative_expression": node.representative_expression,
                "equivalent_forms": list(node.equivalent_forms),
                "roles": [role.value for role in node.roles],
                "sources": [_source_payload(source) for source in node.sources],
            }
        case MarkerNode():
            return {
                "node_id": node.node_id,
                "kind": node.kind.value,
                "reference_id": node.reference_id,
                "sources": [_source_payload(source) for source in node.sources],
            }
        case _:
            raise TypeError(f"unsupported graph node: {type(node)!r}")


def _edge_payload(edge: GraphEdge) -> dict:
    return {
        "edge_id": edge.edge_id,
        "kind": edge.kind.value,
        "source_node_ids": list(edge.source_node_ids),
        "target_node_id": edge.target_node_id,
        "sources": [_source_payload(source) for source in edge.sources],
        "label": edge.label,
    }


def _semantic_node_id(prefix: str, bitset: int, variable_count: int) -> tuple[str, str]:
    digit_count = max(1, ((1 << variable_count) + 3) // 4)
    encoded = f"{bitset:0{digit_count}x}"
    return f"{prefix}:{encoded}", encoded


def _edge(
    kind: EdgeKind,
    source_node_ids: Iterable[str],
    target_node_id: str,
    sources: Iterable[SourceRef] = (),
    label: str = "",
) -> GraphEdge:
    source_ids = tuple(sorted(set(source_node_ids)))
    source_refs = tuple(sorted(set(sources)))
    identity = json.dumps(
        {
            "kind": kind.value,
            "source_node_ids": source_ids,
            "target_node_id": target_node_id,
            "sources": [_source_payload(source) for source in source_refs],
            "label": label,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    edge_id = f"edge:{sha256(identity).hexdigest()[:24]}"
    return GraphEdge(edge_id, kind, source_ids, target_node_id, source_refs, label)


def _validated_for_task(packet: ValidatedPacket, task: PublicTask) -> ValidatedPacket:
    recomputed = validate_and_hash_packet(packet.packet, task)
    if (
        recomputed.canonical_sha256 != packet.canonical_sha256
        or recomputed.canonical_bytes != packet.canonical_bytes
    ):
        raise ValueError("validated packet does not belong to the supplied public task")
    return recomputed


def build_provenance_graph(
    task: PublicTask,
    packets: Sequence[ValidatedPacket],
    *,
    max_nodes: int = 4096,
    max_edges: int = 16384,
) -> ProvenanceGraph:
    """Build a deterministic visible-only graph from immutable member packets."""

    if not packets:
        raise ValueError("at least one validated packet is required")
    if max_nodes < 1 or max_edges < 1:
        raise ValueError("graph resource limits must be positive")

    checked = tuple(_validated_for_task(packet, task) for packet in packets)
    member_ids = tuple(packet.packet.member_id for packet in checked)
    packet_hashes = tuple(packet.canonical_sha256 for packet in checked)
    if len(member_ids) != len(set(member_ids)):
        raise ValueError("population graph requires unique member IDs")
    if len(packet_hashes) != len(set(packet_hashes)):
        raise ValueError("population graph requires unique packet hashes")

    nodes: list[GraphNode] = []
    edges: set[GraphEdge] = set()
    evidence_node_ids: dict[str, str] = {}

    for case in sorted(task.evidence, key=lambda item: item.case_id):
        node_id = f"evidence:{case.case_id}"
        evidence_node_ids[case.case_id] = node_id
        nodes.append(EvidenceNode(node_id, case.case_id, case.assignment, case.output))

    for item in sorted(task.interventions, key=lambda value: value.intervention_id):
        node_id = f"intervention:{item.intervention_id}"
        nodes.append(
            InterventionNode(
                node_id,
                item.intervention_id,
                item.variable,
                item.before_case_id,
                item.after_case_id,
                item.changed_output,
            )
        )
        edges.add(
            _edge(
                EdgeKind.DERIVED_FROM,
                (
                    evidence_node_ids[item.before_case_id],
                    evidence_node_ids[item.after_case_id],
                ),
                node_id,
                label=item.variable,
            )
        )

    candidate_groups: dict[int, dict[str, set]] = {}
    fragment_groups: dict[int, dict[str, set]] = {}
    candidate_occurrence: dict[str, str] = {}
    fragment_occurrence: dict[tuple[str, str], str] = {}

    for validated in checked:
        packet = validated.packet
        candidate_source = SourceRef(
            packet.member_id, validated.canonical_sha256, "complete_candidate"
        )
        _, candidate_bitset = semantic_key(packet.complete_candidate, task.variable_order)
        candidate_id, candidate_hex = _semantic_node_id(
            "candidate", candidate_bitset, len(task.variable_order)
        )
        candidate_occurrence[validated.canonical_sha256] = candidate_id
        candidate_group = candidate_groups.setdefault(
            candidate_bitset,
            {"forms": set(), "sources": set(), "hex": {candidate_hex}},
        )
        candidate_group["forms"].add(canonical_text(packet.complete_candidate))
        candidate_group["sources"].add(candidate_source)

        for fragment in packet.fragments:
            source = SourceRef(
                packet.member_id, validated.canonical_sha256, fragment.fragment_id
            )
            _, fragment_bitset = semantic_key(fragment.expression, task.variable_order)
            fragment_id, fragment_hex = _semantic_node_id(
                "fragment", fragment_bitset, len(task.variable_order)
            )
            fragment_occurrence[(validated.canonical_sha256, fragment.fragment_id)] = (
                fragment_id
            )
            fragment_group = fragment_groups.setdefault(
                fragment_bitset,
                {
                    "forms": set(),
                    "sources": set(),
                    "roles": set(),
                    "hex": {fragment_hex},
                },
            )
            fragment_group["forms"].add(canonical_text(fragment.expression))
            fragment_group["sources"].add(source)
            fragment_group["roles"].add(fragment.role)

    for bitset, group in candidate_groups.items():
        node_id, encoded = _semantic_node_id(
            "candidate", bitset, len(task.variable_order)
        )
        forms = tuple(sorted(group["forms"]))
        nodes.append(
            ExpressionNode(
                node_id,
                NodeKind.CANDIDATE,
                encoded,
                forms[0],
                forms,
                (),
                tuple(sorted(group["sources"])),
            )
        )

    for bitset, group in fragment_groups.items():
        node_id, encoded = _semantic_node_id(
            "fragment", bitset, len(task.variable_order)
        )
        forms = tuple(sorted(group["forms"]))
        nodes.append(
            ExpressionNode(
                node_id,
                NodeKind.FRAGMENT,
                encoded,
                forms[0],
                forms,
                tuple(sorted(group["roles"], key=lambda role: role.value)),
                tuple(sorted(group["sources"])),
            )
        )

    for validated in checked:
        packet = validated.packet
        candidate_id = candidate_occurrence[validated.canonical_sha256]
        candidate_source = SourceRef(
            packet.member_id, validated.canonical_sha256, "complete_candidate"
        )

        for fragment in packet.fragments:
            source = SourceRef(
                packet.member_id, validated.canonical_sha256, fragment.fragment_id
            )
            fragment_id = fragment_occurrence[
                (validated.canonical_sha256, fragment.fragment_id)
            ]
            edges.add(
                _edge(
                    EdgeKind.PART_OF,
                    (fragment_id,),
                    candidate_id,
                    (source, candidate_source),
                )
            )
            for case_id in fragment.supporting_case_ids:
                edges.add(
                    _edge(
                        EdgeKind.SUPPORTS,
                        (evidence_node_ids[case_id],),
                        fragment_id,
                        (source,),
                    )
                )
            for case_id in fragment.contradicting_case_ids:
                edges.add(
                    _edge(
                        EdgeKind.CONTRADICTS,
                        (evidence_node_ids[case_id],),
                        fragment_id,
                        (source,),
                    )
                )
            for prediction in fragment.predictions:
                edges.add(
                    _edge(
                        EdgeKind.PREDICTS,
                        (fragment_id,),
                        evidence_node_ids[prediction.case_id],
                        (source,),
                        label="true" if prediction.output else "false",
                    )
                )

        for case_id in packet.counterexample_case_ids:
            marker_source = SourceRef(
                packet.member_id,
                validated.canonical_sha256,
                f"counterexample:{case_id}",
            )
            marker_id = (
                f"counterexample:{validated.canonical_sha256}:{case_id}"
            )
            nodes.append(
                MarkerNode(
                    marker_id,
                    NodeKind.COUNTEREXAMPLE,
                    case_id,
                    (marker_source,),
                )
            )
            edges.add(
                _edge(
                    EdgeKind.SUPPORTS,
                    (evidence_node_ids[case_id],),
                    marker_id,
                    (marker_source,),
                )
            )
            edges.add(
                _edge(
                    EdgeKind.CONTRADICTS,
                    (marker_id,),
                    candidate_id,
                    (marker_source, candidate_source),
                )
            )

        for fragment_local_id in packet.uncertainty_fragment_ids:
            marker_source = SourceRef(
                packet.member_id,
                validated.canonical_sha256,
                f"uncertainty:{fragment_local_id}",
            )
            marker_id = (
                f"uncertainty:{validated.canonical_sha256}:{fragment_local_id}"
            )
            target_fragment_id = fragment_occurrence[
                (validated.canonical_sha256, fragment_local_id)
            ]
            nodes.append(
                MarkerNode(
                    marker_id,
                    NodeKind.UNCERTAINTY,
                    fragment_local_id,
                    (marker_source,),
                )
            )
            edges.add(
                _edge(
                    EdgeKind.PART_OF,
                    (marker_id,),
                    target_fragment_id,
                    (marker_source,),
                    label="uncertainty-about",
                )
            )

    ordered_nodes = tuple(sorted(nodes, key=lambda node: node.node_id))
    ordered_edges = tuple(sorted(edges, key=lambda edge: edge.edge_id))
    if len(ordered_nodes) > max_nodes:
        raise ValueError(
            f"graph node limit exceeded: {len(ordered_nodes)} > {max_nodes}"
        )
    if len(ordered_edges) > max_edges:
        raise ValueError(
            f"graph edge limit exceeded: {len(ordered_edges)} > {max_edges}"
        )
    return ProvenanceGraph(task.task_id, task.variable_order, ordered_nodes, ordered_edges)
