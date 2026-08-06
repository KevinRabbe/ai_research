"""Population-level metrics and exact cooperative contribution analysis."""

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

__all__ = [
    "CoalitionEvaluation",
    "ErrorCorrelation",
    "error_correlation_matrix",
    "exact_shapley_values",
    "evaluate_all_coalitions",
    "leave_one_out_contributions",
    "pairwise_error_correlation",
    "semantic_distance_matrix",
]
