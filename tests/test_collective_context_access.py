from __future__ import annotations

import pytest

from plural_cognition.collective.artifacts import ResourceUsage, TaskIdentity
from plural_cognition.collective.context_access import (
    ContextBudget,
    ContextObservation,
    ContextOperation,
    ContextQuery,
)
from plural_cognition.collective.runtime import (
    CognitivePhase,
    CognitiveReference,
    ReferenceKind,
    ReferenceScope,
)


A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64


def _task() -> TaskIdentity:
    return TaskIdentity("rs-001", "repository-surgery-v0", A)


def _budget() -> ContextBudget:
    return ContextBudget(max_result_bytes=4096, max_items=20)


def _query(*, source, phase=CognitivePhase.INDEPENDENT) -> ContextQuery:
    return ContextQuery(
        task=_task(),
        query_id="query-001",
        requester_id="mind-a",
        phase=phase,
        source=source,
        operation=ContextOperation.SEARCH,
        query_payload_sha256=B,
        protocol_sha256=C,
        budget=_budget(),
    )


def test_context_budget_is_content_addressed() -> None:
    budget = _budget()
    assert len(budget.sha256) == 64
    assert budget.canonical_payload()["max_result_bytes"] == 4096


def test_independent_query_can_read_system_repository_reference() -> None:
    source = CognitiveReference(
        ReferenceKind.REPOSITORY,
        A,
        ReferenceScope.SYSTEM,
    )
    query = _query(source=source)
    assert len(query.sha256) == 64
    assert query.source.uri == f"repository://sha256/{A}"


def test_independent_query_can_read_own_private_memory() -> None:
    source = CognitiveReference(
        ReferenceKind.MEMORY,
        A,
        ReferenceScope.PRIVATE_MIND,
        owner_id="mind-a",
    )
    assert _query(source=source).requester_id == "mind-a"


def test_independent_query_rejects_other_mind_private_memory() -> None:
    source = CognitiveReference(
        ReferenceKind.MEMORY,
        A,
        ReferenceScope.PRIVATE_MIND,
        owner_id="mind-b",
    )
    with pytest.raises(ValueError, match="not visible"):
        _query(source=source)


def test_independent_query_rejects_shared_collective_state() -> None:
    source = CognitiveReference(
        ReferenceKind.ARTIFACT,
        A,
        ReferenceScope.SHARED_COLLECTIVE,
    )
    with pytest.raises(ValueError, match="shared-collective"):
        _query(source=source)


def test_synthesis_query_can_read_shared_collective_state() -> None:
    source = CognitiveReference(
        ReferenceKind.ARTIFACT,
        A,
        ReferenceScope.SHARED_COLLECTIVE,
    )
    query = _query(source=source, phase=CognitivePhase.SYNTHESIS)
    assert query.phase is CognitivePhase.SYNTHESIS


def test_context_observation_enforces_result_budget_and_accounting() -> None:
    source = CognitiveReference(
        ReferenceKind.REPOSITORY,
        A,
        ReferenceScope.SYSTEM,
    )
    query = _query(source=source)
    observation = ContextObservation(
        query_sha256=query.sha256,
        budget=query.budget,
        result_content_sha256=D,
        result_bytes=1000,
        returned_items=3,
        truncated=False,
        resources=ResourceUsage(retrieval_bytes=1000, tool_calls=1),
    )
    assert observation.binds(query)
    assert len(observation.sha256) == 64


def test_context_observation_rejects_byte_overflow() -> None:
    with pytest.raises(ValueError, match="max_result_bytes"):
        ContextObservation(
            query_sha256=A,
            budget=_budget(),
            result_content_sha256=B,
            result_bytes=4097,
            returned_items=1,
            truncated=True,
            resources=ResourceUsage(retrieval_bytes=4097),
        )


def test_context_observation_rejects_item_overflow() -> None:
    with pytest.raises(ValueError, match="max_items"):
        ContextObservation(
            query_sha256=A,
            budget=_budget(),
            result_content_sha256=B,
            result_bytes=100,
            returned_items=21,
            truncated=True,
            resources=ResourceUsage(retrieval_bytes=100),
        )


def test_context_observation_requires_exact_retrieval_accounting() -> None:
    with pytest.raises(ValueError, match="retrieval_bytes"):
        ContextObservation(
            query_sha256=A,
            budget=_budget(),
            result_content_sha256=B,
            result_bytes=100,
            returned_items=1,
            truncated=False,
            resources=ResourceUsage(retrieval_bytes=99),
        )


def test_context_payload_contains_no_protected_evaluator_fields() -> None:
    source = CognitiveReference(
        ReferenceKind.REPOSITORY,
        A,
        ReferenceScope.SYSTEM,
    )
    payload = _query(source=source).canonical_payload()
    assert "protected_expectations_sha256" not in payload
    assert "hidden_tests_sha256" not in payload
    assert "evaluator_configuration_sha256" not in payload
