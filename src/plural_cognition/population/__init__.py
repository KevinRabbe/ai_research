"""Population packets, graphs, metrics, and cooperative contribution analysis."""

from .credit import (
    CoalitionEvaluation,
    exact_shapley_values,
    evaluate_all_coalitions,
    leave_one_out_contributions,
)
from .graph import (
    EdgeKind,
    EvidenceNode,
    ExpressionNode,
    GraphEdge,
    InterventionNode,
    MarkerNode,
    NodeKind,
    ProvenanceGraph,
    SourceRef,
    build_provenance_graph,
)
from .metrics import (
    ErrorCorrelation,
    error_correlation_matrix,
    pairwise_error_correlation,
    semantic_distance_matrix,
)
from .packet import (
    DecodedPacket,
    FragmentPrediction,
    FragmentRole,
    HypothesisFragment,
    HypothesisPacket,
    PacketDecodeError,
    ValidatedPacket,
    decode_validated_packet,
    validate_and_hash_packet,
)

__all__ = [
    "CoalitionEvaluation",
    "DecodedPacket",
    "EdgeKind",
    "ErrorCorrelation",
    "EvidenceNode",
    "ExpressionNode",
    "FragmentPrediction",
    "FragmentRole",
    "GraphEdge",
    "HypothesisFragment",
    "HypothesisPacket",
    "InterventionNode",
    "MarkerNode",
    "NodeKind",
    "PacketDecodeError",
    "ProvenanceGraph",
    "SourceRef",
    "ValidatedPacket",
    "build_provenance_graph",
    "decode_validated_packet",
    "error_correlation_matrix",
    "exact_shapley_values",
    "evaluate_all_coalitions",
    "leave_one_out_contributions",
    "pairwise_error_correlation",
    "semantic_distance_matrix",
    "validate_and_hash_packet",
]