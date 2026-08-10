"""Architecture-independent contracts for capable collective cognition."""

from .artifacts import (
    ARTIFACT_SCHEMA,
    EVALUATION_SCHEMA,
    CollectiveStage,
    EvaluationRecord,
    EvaluationVisibility,
    MetricValue,
    ResourceUsage,
    StageArtifact,
    TaskIdentity,
    sha256_content,
)
from .metrics import (
    CollectiveSummary,
    ErrorCorrelation,
    FourMindCredit,
    OutcomeTable,
    StageDelta,
    compare_stages,
    error_correlation_matrix,
    evaluate_four_mind_credit,
    pairwise_error_correlation,
    summarize_collective,
)
from .mind import MindBackend, MindIdentity, MindInvocationResult, MindRequest

__all__ = [
    "ARTIFACT_SCHEMA",
    "EVALUATION_SCHEMA",
    "CollectiveStage",
    "CollectiveSummary",
    "ErrorCorrelation",
    "EvaluationRecord",
    "EvaluationVisibility",
    "FourMindCredit",
    "MetricValue",
    "MindBackend",
    "MindIdentity",
    "MindInvocationResult",
    "MindRequest",
    "OutcomeTable",
    "ResourceUsage",
    "StageArtifact",
    "StageDelta",
    "TaskIdentity",
    "compare_stages",
    "error_correlation_matrix",
    "evaluate_four_mind_credit",
    "pairwise_error_correlation",
    "sha256_content",
    "summarize_collective",
]
