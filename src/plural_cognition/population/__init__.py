"""Population packets, metrics, and exact cooperative contribution analysis."""

from .credit import (
    CoalitionEvaluation,
    exact_shapley_values,
    evaluate_all_coalitions,
    leave_one_out_contributions,
)
from .metrics import (
    ErrorCorrelation,
    error_correlation_matrix,
    pairwise_error_correlation,
    semantic_distance_matrix,
)
from .packet import (
    FragmentPrediction,
    FragmentRole,
    HypothesisFragment,
    HypothesisPacket,
    ValidatedPacket,
    validate_and_hash_packet,
)

__all__ = [
    "CoalitionEvaluation",
    "ErrorCorrelation",
    "FragmentPrediction",
    "FragmentRole",
    "HypothesisFragment",
    "HypothesisPacket",
    "ValidatedPacket",
    "error_correlation_matrix",
    "exact_shapley_values",
    "evaluate_all_coalitions",
    "leave_one_out_contributions",
    "pairwise_error_correlation",
    "semantic_distance_matrix",
    "validate_and_hash_packet",
]
