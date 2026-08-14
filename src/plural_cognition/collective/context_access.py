"""Bounded external-context query and observation contracts.

The model requests explicit operations over content-addressed external state and
receives bounded immutable observations. This is an RLM-style architecture
boundary, not a retrieval implementation: no filesystem, search engine, model,
or network operation is performed here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Any, Protocol, runtime_checkable

from .artifacts import ResourceUsage, TaskIdentity
from .content_store import validate_sha256
from .runtime import CognitivePhase, CognitiveReference, ReferenceScope

CONTEXT_BUDGET_SCHEMA = "plural-cognition-context-budget-v1"
CONTEXT_QUERY_SCHEMA = "plural-cognition-context-query-v1"
CONTEXT_OBSERVATION_SCHEMA = "plural-cognition-context-observation-v1"


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


def _positive_int(value: int, field: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{field} must be a positive integer")


def _reference_visible(
    source: CognitiveReference,
    *,
    requester_id: str,
    phase: CognitivePhase,
) -> bool:
    if source.scope is ReferenceScope.SYSTEM:
        return True
    if source.scope is ReferenceScope.PRIVATE_MIND:
        return source.owner_id == requester_id
    if source.scope is ReferenceScope.SHARED_COLLECTIVE:
        return phase is not CognitivePhase.INDEPENDENT
    raise AssertionError("unhandled reference scope")


class ContextOperation(str, Enum):
    TREE = "tree"
    SEARCH = "search"
    READ = "read"
    SYMBOL = "symbol"
    REFERENCES = "references"
    DEPENDENCIES = "dependencies"


@dataclass(frozen=True, slots=True)
class ContextBudget:
    """Hard result ceiling for one external-context operation."""

    max_result_bytes: int
    max_items: int

    def __post_init__(self) -> None:
        _positive_int(self.max_result_bytes, "max_result_bytes")
        _positive_int(self.max_items, "max_items")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": CONTEXT_BUDGET_SCHEMA,
            "max_result_bytes": self.max_result_bytes,
            "max_items": self.max_items,
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()


@dataclass(frozen=True, slots=True)
class ContextQuery:
    """One explicit request to inspect externally stored cognitive state.

    Operation-specific arguments (path, search string, symbol name, etc.) live in
    ``query_payload_sha256`` so the generic runtime does not privilege one code or
    retrieval representation. The referenced source must be visible to the
    requester in the declared cognitive phase.
    """

    task: TaskIdentity
    query_id: str
    requester_id: str
    phase: CognitivePhase
    source: CognitiveReference
    operation: ContextOperation
    query_payload_sha256: str
    protocol_sha256: str
    budget: ContextBudget

    def __post_init__(self) -> None:
        if not isinstance(self.task, TaskIdentity):
            raise TypeError("task must be TaskIdentity")
        if not isinstance(self.phase, CognitivePhase):
            raise TypeError("phase must be CognitivePhase")
        if not isinstance(self.source, CognitiveReference):
            raise TypeError("source must be CognitiveReference")
        if not isinstance(self.operation, ContextOperation):
            raise TypeError("operation must be ContextOperation")
        if not isinstance(self.budget, ContextBudget):
            raise TypeError("budget must be ContextBudget")
        _nonempty(self.query_id, "query_id")
        _nonempty(self.requester_id, "requester_id")
        validate_sha256(self.query_payload_sha256)
        validate_sha256(self.protocol_sha256)
        if not _reference_visible(
            self.source,
            requester_id=self.requester_id,
            phase=self.phase,
        ):
            if self.phase is CognitivePhase.INDEPENDENT and (
                self.source.scope is ReferenceScope.SHARED_COLLECTIVE
            ):
                raise ValueError(
                    "independent context query must not read shared-collective state"
                )
            raise ValueError("context query source is not visible to requester")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": CONTEXT_QUERY_SCHEMA,
            "task": self.task.canonical_payload(),
            "query_id": self.query_id,
            "requester_id": self.requester_id,
            "phase": self.phase.value,
            "source": self.source.canonical_payload(),
            "operation": self.operation.value,
            "query_payload_sha256": self.query_payload_sha256,
            "protocol_sha256": self.protocol_sha256,
            "budget": self.budget.canonical_payload(),
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class ContextObservation:
    """Immutable bounded result returned for one ContextQuery."""

    query_sha256: str
    budget: ContextBudget
    result_content_sha256: str
    result_bytes: int
    returned_items: int
    truncated: bool
    resources: ResourceUsage

    def __post_init__(self) -> None:
        validate_sha256(self.query_sha256)
        if not isinstance(self.budget, ContextBudget):
            raise TypeError("budget must be ContextBudget")
        validate_sha256(self.result_content_sha256)
        if type(self.result_bytes) is not int or self.result_bytes < 0:
            raise ValueError("result_bytes must be a non-negative integer")
        if type(self.returned_items) is not int or self.returned_items < 0:
            raise ValueError("returned_items must be a non-negative integer")
        if type(self.truncated) is not bool:
            raise TypeError("truncated must be bool")
        if not isinstance(self.resources, ResourceUsage):
            raise TypeError("resources must be ResourceUsage")
        if self.result_bytes > self.budget.max_result_bytes:
            raise ValueError("context observation exceeds max_result_bytes")
        if self.returned_items > self.budget.max_items:
            raise ValueError("context observation exceeds max_items")
        if self.resources.retrieval_bytes != self.result_bytes:
            raise ValueError("retrieval_bytes must equal result_bytes")

    def binds(self, query: ContextQuery) -> bool:
        if not isinstance(query, ContextQuery):
            raise TypeError("query must be ContextQuery")
        return self.query_sha256 == query.sha256 and self.budget == query.budget

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": CONTEXT_OBSERVATION_SCHEMA,
            "query_sha256": self.query_sha256,
            "budget": self.budget.canonical_payload(),
            "result_content_sha256": self.result_content_sha256,
            "result_bytes": self.result_bytes,
            "returned_items": self.returned_items,
            "truncated": self.truncated,
            "resources": self.resources.canonical_payload(),
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


@runtime_checkable
class ContextBackend(Protocol):
    """Replaceable implementation boundary for repository/memory/context access."""

    def query(self, request: ContextQuery) -> ContextObservation:
        ...
