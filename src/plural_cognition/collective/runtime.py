"""External cognitive-state and resumable runtime contracts.

The runtime owns addressable state outside model context while preserving the
independent-mind boundary. This module deliberately defines no scheduler loop,
autonomous Dream mode, or tool executor; it freezes the state identities those
systems may later consume.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum, IntEnum
from hashlib import sha256
from typing import Any

from .artifacts import ResourceUsage, TaskIdentity
from .content_store import validate_sha256

COGNITIVE_REFERENCE_SCHEMA = "plural-cognition-cognitive-reference-v1"
RUNTIME_CHECKPOINT_SCHEMA = "plural-cognition-runtime-checkpoint-v1"


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _nonempty(value: str, field: str) -> None:
    if type(value) is not str or not value:
        raise ValueError(f"{field} must be a non-empty string")


def _git_revision(value: str) -> None:
    if type(value) is not str or len(value) != 40:
        raise ValueError("software_revision must be a full 40-character Git SHA")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError("software_revision must be hexadecimal") from exc
    if value != value.lower():
        raise ValueError("software_revision must use lowercase hexadecimal")


class ReferenceKind(str, Enum):
    ARTIFACT = "artifact"
    REPOSITORY = "repository"
    TASK = "task"
    EXPERIMENT = "experiment"
    MEMORY = "memory"
    SKILL = "skill"
    TOOL_OBSERVATION = "tool-observation"


class ReferenceScope(str, Enum):
    """Visibility boundary for one externally stored cognitive object."""

    SYSTEM = "system"
    PRIVATE_MIND = "private-mind"
    SHARED_COLLECTIVE = "shared-collective"


class CognitivePhase(str, Enum):
    INDEPENDENT = "independent"
    SYNTHESIS = "synthesis"
    HARNESS = "harness"
    VERIFICATION = "verification"
    REFINEMENT = "refinement"
    CONSOLIDATION = "consolidation"


class RuntimeTaskState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_TOOL = "waiting-for-tool"
    CHECKPOINTED = "checkpointed"
    PAUSED = "paused"
    VERIFYING = "verifying"
    DONE = "done"
    FAILED = "failed"


class RuntimePriority(IntEnum):
    """Lower numeric values have higher scheduling priority."""

    URGENT_USER = 0
    NORMAL_USER = 1
    SYSTEM = 2
    REFINEMENT = 3
    SPECULATIVE = 4


@dataclass(frozen=True, slots=True)
class CognitiveReference:
    """Content-addressed handle to state kept outside active model context."""

    kind: ReferenceKind
    content_sha256: str
    scope: ReferenceScope
    owner_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ReferenceKind):
            raise TypeError("kind must be ReferenceKind")
        if not isinstance(self.scope, ReferenceScope):
            raise TypeError("scope must be ReferenceScope")
        validate_sha256(self.content_sha256)
        if self.scope is ReferenceScope.PRIVATE_MIND:
            if self.owner_id is None:
                raise ValueError("private-mind reference requires owner_id")
            _nonempty(self.owner_id, "owner_id")
        elif self.owner_id is not None:
            raise ValueError("only private-mind references may declare owner_id")

    @property
    def uri(self) -> str:
        return f"{self.kind.value}://sha256/{self.content_sha256}"

    @property
    def sort_key(self) -> tuple[str, str, str, str]:
        return (
            self.scope.value,
            self.kind.value,
            self.content_sha256,
            self.owner_id or "",
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": COGNITIVE_REFERENCE_SCHEMA,
            "kind": self.kind.value,
            "content_sha256": self.content_sha256,
            "scope": self.scope.value,
            "owner_id": self.owner_id,
        }


@dataclass(frozen=True, slots=True)
class RuntimeCheckpoint:
    """Immutable, resumable state for one runtime task at a declared safe point.

    The checkpoint stores hashes/references rather than raw context. During the
    independent phase, collective-shared state and other minds' private state are
    forbidden, preserving the A0/B0/C0/D0 isolation boundary.
    """

    task: TaskIdentity
    runtime_task_id: str
    owner_id: str
    phase: CognitivePhase
    state: RuntimeTaskState
    priority: RuntimePriority
    producer_configuration_sha256: str
    protocol_sha256: str
    software_revision: str
    objective_sha256: str
    workspace_sha256: str
    working_state_sha256: str
    plan_sha256: str
    tool_state_sha256: str
    references: tuple[CognitiveReference, ...] = ()
    safe_to_preempt: bool = True
    resources: ResourceUsage = ResourceUsage()

    def __post_init__(self) -> None:
        if not isinstance(self.task, TaskIdentity):
            raise TypeError("task must be TaskIdentity")
        if not isinstance(self.phase, CognitivePhase):
            raise TypeError("phase must be CognitivePhase")
        if not isinstance(self.state, RuntimeTaskState):
            raise TypeError("state must be RuntimeTaskState")
        if not isinstance(self.priority, RuntimePriority):
            raise TypeError("priority must be RuntimePriority")
        if not isinstance(self.resources, ResourceUsage):
            raise TypeError("resources must be ResourceUsage")
        if type(self.safe_to_preempt) is not bool:
            raise TypeError("safe_to_preempt must be bool")
        _nonempty(self.runtime_task_id, "runtime_task_id")
        _nonempty(self.owner_id, "owner_id")
        for digest in (
            self.producer_configuration_sha256,
            self.protocol_sha256,
            self.objective_sha256,
            self.workspace_sha256,
            self.working_state_sha256,
            self.plan_sha256,
            self.tool_state_sha256,
        ):
            validate_sha256(digest)
        _git_revision(self.software_revision)

        if any(not isinstance(ref, CognitiveReference) for ref in self.references):
            raise TypeError("references must contain CognitiveReference instances")
        keys = tuple(ref.sort_key for ref in self.references)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("references must be sorted and unique")

        if self.phase is CognitivePhase.INDEPENDENT:
            for ref in self.references:
                if ref.scope is ReferenceScope.SHARED_COLLECTIVE:
                    raise ValueError(
                        "independent phase must not consume shared-collective state"
                    )
                if (
                    ref.scope is ReferenceScope.PRIVATE_MIND
                    and ref.owner_id != self.owner_id
                ):
                    raise ValueError(
                        "independent phase must not consume another mind's private state"
                    )

        if self.state in (RuntimeTaskState.CHECKPOINTED, RuntimeTaskState.PAUSED):
            if not self.safe_to_preempt:
                raise ValueError("checkpointed/paused state must be safe to preempt")
        if self.state in (RuntimeTaskState.DONE, RuntimeTaskState.FAILED):
            if not self.safe_to_preempt:
                raise ValueError("terminal runtime state must be safe to preempt")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": RUNTIME_CHECKPOINT_SCHEMA,
            "task": self.task.canonical_payload(),
            "runtime_task_id": self.runtime_task_id,
            "owner_id": self.owner_id,
            "phase": self.phase.value,
            "state": self.state.value,
            "priority": int(self.priority),
            "producer_configuration_sha256": self.producer_configuration_sha256,
            "protocol_sha256": self.protocol_sha256,
            "software_revision": self.software_revision,
            "objective_sha256": self.objective_sha256,
            "workspace_sha256": self.workspace_sha256,
            "working_state_sha256": self.working_state_sha256,
            "plan_sha256": self.plan_sha256,
            "tool_state_sha256": self.tool_state_sha256,
            "references": [ref.canonical_payload() for ref in self.references],
            "safe_to_preempt": self.safe_to_preempt,
            "resources": self.resources.canonical_payload(),
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()
