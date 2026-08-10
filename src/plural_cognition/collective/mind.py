"""Architecture-independent contracts for primary minds in the collective."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Protocol, runtime_checkable

from .artifacts import (
    CollectiveStage,
    ResourceUsage,
    StageArtifact,
    TaskIdentity,
)


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


def _sha256(value: str, field: str) -> None:
    if type(value) is not str or len(value) != 64:
        raise ValueError(f"{field} must contain 64 lowercase hexadecimal characters")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{field} must be hexadecimal") from exc
    if value != value.lower():
        raise ValueError(f"{field} must use lowercase hexadecimal")


def _git_sha(value: str) -> None:
    if type(value) is not str or len(value) != 40:
        raise ValueError("software_revision must be a full 40-character Git SHA")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError("software_revision must be hexadecimal") from exc
    if value != value.lower():
        raise ValueError("software_revision must use lowercase hexadecimal")


def _optional_sha256(value: str | None, field: str) -> None:
    if value is not None:
        _sha256(value, field)


@dataclass(frozen=True, slots=True)
class MindIdentity:
    """Exact identity of one primary cognitive backend."""

    mind_id: str
    backend_family: str
    model_id: str
    model_revision: str
    configuration_sha256: str

    def __post_init__(self) -> None:
        _nonempty(self.mind_id, "mind_id")
        _nonempty(self.backend_family, "backend_family")
        _nonempty(self.model_id, "model_id")
        _nonempty(self.model_revision, "model_revision")
        _sha256(self.configuration_sha256, "configuration_sha256")

    def canonical_payload(self) -> dict[str, str]:
        return {
            "mind_id": self.mind_id,
            "backend_family": self.backend_family,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "configuration_sha256": self.configuration_sha256,
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class MindRequest:
    """Solver-visible input identity for one independent primary-mind invocation."""

    task: TaskIdentity
    run_id: str
    protocol_sha256: str
    visible_input_sha256: str
    context_artifact_sha256s: tuple[str, ...] = ()
    tool_manifest_sha256: str | None = None
    memory_snapshot_sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.task, TaskIdentity):
            raise TypeError("task must be TaskIdentity")
        _nonempty(self.run_id, "run_id")
        _sha256(self.protocol_sha256, "protocol_sha256")
        _sha256(self.visible_input_sha256, "visible_input_sha256")
        for digest in self.context_artifact_sha256s:
            _sha256(digest, "context_artifact_sha256s entry")
        if tuple(sorted(set(self.context_artifact_sha256s))) != self.context_artifact_sha256s:
            raise ValueError("context_artifact_sha256s must be sorted and unique")
        _optional_sha256(self.tool_manifest_sha256, "tool_manifest_sha256")
        _optional_sha256(self.memory_snapshot_sha256, "memory_snapshot_sha256")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "task": self.task.canonical_payload(),
            "run_id": self.run_id,
            "protocol_sha256": self.protocol_sha256,
            "visible_input_sha256": self.visible_input_sha256,
            "context_artifact_sha256s": list(self.context_artifact_sha256s),
            "tool_manifest_sha256": self.tool_manifest_sha256,
            "memory_snapshot_sha256": self.memory_snapshot_sha256,
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class MindInvocationResult:
    """Backend result that can be frozen as a raw-mind StageArtifact."""

    mind: MindIdentity
    request_sha256: str
    output_content_sha256: str
    software_revision: str
    resources: ResourceUsage
    finish_reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.mind, MindIdentity):
            raise TypeError("mind must be MindIdentity")
        _sha256(self.request_sha256, "request_sha256")
        _sha256(self.output_content_sha256, "output_content_sha256")
        _git_sha(self.software_revision)
        if not isinstance(self.resources, ResourceUsage):
            raise TypeError("resources must be ResourceUsage")
        _nonempty(self.finish_reason, "finish_reason")

    def to_raw_artifact(self, request: MindRequest) -> StageArtifact:
        if not isinstance(request, MindRequest):
            raise TypeError("request must be MindRequest")
        if request.sha256 != self.request_sha256:
            raise ValueError("request identity does not match invocation result")
        return StageArtifact(
            stage=CollectiveStage.RAW_MIND_OUTPUT,
            task=request.task,
            run_id=request.run_id,
            producer_id=self.mind.mind_id,
            producer_configuration_sha256=self.mind.sha256,
            protocol_sha256=request.protocol_sha256,
            software_revision=self.software_revision,
            content_sha256=self.output_content_sha256,
            resources=self.resources,
        )


@runtime_checkable
class MindBackend(Protocol):
    """Minimal backend boundary seen by the plural scheduler.

    Concrete implementations may wrap a local dense model, local MoE, remote API,
    specialized code model, adapter lineage, or a future architecture. The
    scheduler depends only on this contract.
    """

    @property
    def identity(self) -> MindIdentity:
        ...

    def invoke(self, request: MindRequest) -> MindInvocationResult:
        ...
