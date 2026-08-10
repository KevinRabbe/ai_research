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
from .mind import MindBackend, MindIdentity, MindInvocationResult, MindRequest

__all__ = [
    "ARTIFACT_SCHEMA",
    "EVALUATION_SCHEMA",
    "CollectiveStage",
    "EvaluationRecord",
    "EvaluationVisibility",
    "MetricValue",
    "MindBackend",
    "MindIdentity",
    "MindInvocationResult",
    "MindRequest",
    "ResourceUsage",
    "StageArtifact",
    "TaskIdentity",
    "sha256_content",
]
