from __future__ import annotations

import pytest

from plural_cognition.collective.repository_surgery import (
    MutationKind,
    PatchFormat,
    REPOSITORY_SURGERY_FAMILY,
    RepositorySurgeryGenerationRecord,
    RepositorySurgerySubmission,
    build_visible_repository_surgery_task,
)
from plural_cognition.collective.tasks import TaskSplit


A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64
E = "e" * 64
F = "f" * 64


def test_generation_record_binds_exact_visible_task() -> None:
    task = build_visible_repository_surgery_task(
        task_id="rs-001",
        split=TaskSplit.SELECTION,
        buggy_repository_sha256=B,
        issue_prompt_sha256=C,
        public_tests_sha256=D,
        max_visible_bytes=200_000,
    )
    assert task.task.task_family == REPOSITORY_SURGERY_FAMILY

    record = RepositorySurgeryGenerationRecord(
        task_id=task.task.task_id,
        task_payload_sha256=task.task.payload_sha256,
        split=task.split,
        generation_seed=20260811,
        mutation_kind=MutationKind.BOUNDARY,
        mutation_configuration_sha256=A,
        clean_repository_sha256=A,
        buggy_repository_sha256=B,
        issue_prompt_sha256=C,
        public_tests_sha256=D,
        hidden_tests_sha256=E,
        gold_patch_sha256=F,
    )
    assert record.binds(task)
    assert len(record.sha256) == 64
    assert "hidden_tests_sha256" not in task.canonical_payload()["visible"]


def test_generation_record_rejects_noop_mutation() -> None:
    task = build_visible_repository_surgery_task(
        task_id="rs-001",
        split=TaskSplit.SELECTION,
        buggy_repository_sha256=A,
        issue_prompt_sha256=C,
        public_tests_sha256=None,
        max_visible_bytes=100_000,
    )
    with pytest.raises(ValueError, match="must differ"):
        RepositorySurgeryGenerationRecord(
            task_id=task.task.task_id,
            task_payload_sha256=task.task.payload_sha256,
            split=task.split,
            generation_seed=1,
            mutation_kind=MutationKind.LOCAL_LOGIC,
            mutation_configuration_sha256=B,
            clean_repository_sha256=A,
            buggy_repository_sha256=A,
            issue_prompt_sha256=C,
            public_tests_sha256=None,
            hidden_tests_sha256=E,
            gold_patch_sha256=F,
        )


def test_submission_is_content_addressed_and_binds_producer() -> None:
    submission = RepositorySurgerySubmission(
        task_id="rs-001",
        task_payload_sha256=A,
        producer_artifact_sha256=B,
        patch_sha256=C,
        patch_format=PatchFormat.UNIFIED_DIFF,
        patch_size_bytes=123,
    )
    assert len(submission.sha256) == 64
    assert submission.canonical_payload()["patch_format"] == "unified-diff-v1"


def test_submission_rejects_empty_patch() -> None:
    with pytest.raises(ValueError, match="patch_size_bytes"):
        RepositorySurgerySubmission(
            task_id="rs-001",
            task_payload_sha256=A,
            producer_artifact_sha256=B,
            patch_sha256=C,
            patch_format=PatchFormat.UNIFIED_DIFF,
            patch_size_bytes=0,
        )
