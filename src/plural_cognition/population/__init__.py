"""Population packets, graphs, synthesis, verification, and contribution analysis."""

from .coalition import (
    RealizedMemberContribution,
    SynthesisCoalitionOutcome,
    SynthesisCoalitionReport,
    evaluate_synthesis_coalitions,
)
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
from .graph_synthesis import integrate_synthesis_result
from .knowledge_metrics import (
    MemberKnowledgeContribution,
    PopulationKnowledgeReport,
    analyze_population_knowledge,
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
from .synthesis import (
    Derivation,
    SynthesizedCandidate,
    SynthesisConfig,
    SynthesisResult,
    SynthesisRule,
    SynthesisTrace,
    synthesize_visible,
)
from .verification import (
    FragmentVisibleAudit,
    PacketVisibleAudit,
    audit_visible_packet,
)

__all__ = [
    "CoalitionEvaluation",
    "DecodedPacket",
    "Derivation",
    "EdgeKind",
    "ErrorCorrelation",
    "EvidenceNode",
    "ExpressionNode",
    "FragmentPrediction",
    "FragmentRole",
    "FragmentVisibleAudit",
    "GraphEdge",
    "HypothesisFragment",
    "HypothesisPacket",
    "InterventionNode",
    "MarkerNode",
    "MemberKnowledgeContribution",
    "NodeKind",
    "PacketDecodeError",
    "PacketVisibleAudit",
    "PopulationKnowledgeReport",
    "ProvenanceGraph",
    "RealizedMemberContribution",
    "SourceRef",
    "SynthesizedCandidate",
    "SynthesisCoalitionOutcome",
    "SynthesisCoalitionReport",
    "SynthesisConfig",
    "SynthesisResult",
    "SynthesisRule",
    "SynthesisTrace",
    "ValidatedPacket",
    "analyze_population_knowledge",
    "audit_visible_packet",
    "build_provenance_graph",
    "decode_validated_packet",
    "error_correlation_matrix",
    "evaluate_synthesis_coalitions",
    "exact_shapley_values",
    "evaluate_all_coalitions",
    "integrate_synthesis_result",
    "leave_one_out_contributions",
    "pairwise_error_correlation",
    "semantic_distance_matrix",
    "synthesize_visible",
    "validate_and_hash_packet",
]
