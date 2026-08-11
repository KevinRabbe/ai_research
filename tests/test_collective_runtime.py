from __future__ import annotations

import pytest

from plural_cognition.collective.artifacts import TaskIdentity
from plural_cognition.collective.runtime import (
    CognitivePhase,
    CognitiveReference,
    ReferenceKind,
    ReferenceScope,
    RuntimeCheckpoint,
    RuntimePriority,
    RuntimeTaskState,
)


A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64
E = "e" * 64
F = "f" * 64
REV = "1" * 40


def _task() -> TaskIdentity:
    return TaskIdentity("rs-001", "repository-surgery-v0", A)


def _checkpoint(*, phase=CognitivePhase.INDEPENDENT, state=RuntimeTaskState.RUNNING, refs=(), safe=True):
    return RuntimeCheckpoint(
        task=_task(),
        runtime_task_id="runtime-001",
        owner_id="mind-a",
        phase=phase,
        state=state,
        priority=RuntimePriority.NORMAL_USER,
        producer_configuration_sha256=A,
        protocol_sha256=B,
        software_revision=REV,
        objective_sha256=C,
        workspace_sha256=D,
        working_state_sha256=E,
        plan_sha256=F,
        tool_state_sha256=A,
        references=refs,
        safe_to_preempt=safe,
    )


def test_cognitive_reference_uses_stable_content_addressed_uri() -> None:
    ref = CognitiveReference(
        ReferenceKind.REPOSITORY,
        A,
        ReferenceScope.SYSTEM,
    )
    assert ref.uri == f"repository://sha256/{A}"
    assert ref.canonical_payload()["content_sha256"] == A


def test_private_reference_requires_and_binds_owner() -> None:
    with pytest.raises(ValueError, match="owner_id"):
        CognitiveReference(
            ReferenceKind.MEMORY,
            A,
            ReferenceScope.PRIVATE_MIND,
        )
    ref = CognitiveReference(
        ReferenceKind.MEMORY,
        A,
        ReferenceScope.PRIVATE_MIND,
        owner_id="mind-a",
    )
    assert ref.owner_id == "mind-a"


def test_nonprivate_reference_rejects_owner() -> None:
    with pytest.raises(ValueError, match="only private-mind"):
        CognitiveReference(
            ReferenceKind.SKILL,
            A,
            ReferenceScope.SYSTEM,
            owner_id="mind-a",
        )


def test_independent_checkpoint_allows_system_and_own_private_state() -> None:
    refs = tuple(
        sorted(
            (
                CognitiveReference(ReferenceKind.REPOSITORY, A, ReferenceScope.SYSTEM),
                CognitiveReference(
                    ReferenceKind.MEMORY,
                    B,
                    ReferenceScope.PRIVATE_MIND,
                    owner_id="mind-a",
                ),
            ),
            key=lambda ref: ref.sort_key,
        )
    )
    checkpoint = _checkpoint(refs=refs)
    assert len(checkpoint.sha256) == 64
    assert checkpoint.canonical_payload()["phase"] == "independent"


def test_independent_checkpoint_rejects_shared_collective_state() -> None:
    refs = (
        CognitiveReference(
            ReferenceKind.ARTIFACT,
            A,
            ReferenceScope.SHARED_COLLECTIVE,
        ),
    )
    with pytest.raises(ValueError, match="shared-collective"):
        _checkpoint(refs=refs)


def test_independent_checkpoint_rejects_other_mind_private_state() -> None:
    refs = (
        CognitiveReference(
            ReferenceKind.MEMORY,
            A,
            ReferenceScope.PRIVATE_MIND,
            owner_id="mind-b",
        ),
    )
    with pytest.raises(ValueError, match="another mind"):
        _checkpoint(refs=refs)


def test_synthesis_checkpoint_may_reference_shared_collective_state() -> None:
    refs = (
        CognitiveReference(
            ReferenceKind.ARTIFACT,
            A,
            ReferenceScope.SHARED_COLLECTIVE,
        ),
    )
    checkpoint = _checkpoint(phase=CognitivePhase.SYNTHESIS, refs=refs)
    assert checkpoint.references == refs


def test_references_must_be_canonical() -> None:
    refs = (
        CognitiveReference(ReferenceKind.TASK, B, ReferenceScope.SYSTEM),
        CognitiveReference(ReferenceKind.REPOSITORY, A, ReferenceScope.SYSTEM),
    )
    with pytest.raises(ValueError, match="sorted"):
        _checkpoint(refs=refs)


def test_paused_checkpoint_must_be_safe_to_preempt() -> None:
    with pytest.raises(ValueError, match="safe to preempt"):
        _checkpoint(state=RuntimeTaskState.PAUSED, safe=False)


def test_running_checkpoint_can_mark_atomic_nonpreemptible_work() -> None:
    checkpoint = _checkpoint(state=RuntimeTaskState.RUNNING, safe=False)
    assert not checkpoint.safe_to_preempt
