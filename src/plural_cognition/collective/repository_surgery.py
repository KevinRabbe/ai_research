"""Immutable contracts for the Repository Surgery v0 coding benchmark."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Any

from .content_store import validate_sha256
from .tasks import SolverVisibleTask, TaskSplit

REPOSITORY_SURGERY_FAMILY = "repository-surgery-v0"
GENERATION_RECORD_SCHEMA = "plural-cognition-repository-surgery-generation-v1"
SUBMISSION_SCHEMA = "plural-cognition-repository-surgery-submission-v1"


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


class MutationKind(str, Enum):
    LOCAL_LOGIC = "local-logic"
    BOUNDARY = "boundary"
    API_CONTRACT = "api-contract"
    MULTI_FILE_BEHAVIOR = "multi-file-behavior"
    STATE_MANAGEMENT = "state-management"
    ERROR_HANDLING = "error-handling"
    ALIASING = "aliasing"
    PERFORMANCE = "performance"


class PatchFormat(str, Enum):
    UNIFIED_DIFF = "unified-diff-v1"


@dataclass(frozen=True, slots=True)
class RepositorySurgeryGenerationRecord:
    """Protected provenance for one generated repository-repair task."""

    task_id: str
    task_payload_sha256: str
    split: TaskSplit
    generation_seed: int
    mutation_kind: MutationKind
    mutation_configuration_sha256: str
    clean_repository_sha256: str
    buggy_repository_sha256: str
    issue_prompt_sha256: str
    public_tests_sha256: str | None
    hidden_tests_sha256: str
    gold_patch_sha256: str

    def __post_init__(self) -> None:
        _nonempty(self.task_id, "task_id")
        validate_sha256(self.task_payload_sha256)
        if not isinstance(self.split, TaskSplit):
            raise TypeError("split must be TaskSplit")
        if type(self.generation_seed) is not int:
            raise TypeError("generation_seed must be int")
        if not isinstance(self.mutation_kind, MutationKind):
            raise TypeError("mutation_kind must be MutationKind")
        for digest in (
            self.mutation_configuration_sha256,
            self.clean_repository_sha256,
            self.buggy_repository_sha256,
            self.issue_prompt_sha256,
            self.hidden_tests_sha256,
            self.gold_patch_sha256,
        ):
            validate_sha256(digest)
        if self.public_tests_sha256 is not None:
            validate_sha256(self.public_tests_sha256)
        if self.clean_repository_sha256 == self.buggy_repository_sha256:
            raise ValueError("buggy repository must differ from clean repository")

    def binds(self, task: SolverVisibleTask) -> bool:
        if not isinstance(task, SolverVisibleTask):
            raise TypeError("task must be SolverVisibleTask")
        return (
            task.task.task_family == REPOSITORY_SURGERY_FAMILY
            and task.task.task_id == self.task_id
            and task.task.payload_sha256 == self.task_payload_sha256
            and task.split is self.split
            and task.repository_sha256 == self.buggy_repository_sha256
            and task.prompt_sha256 == self.issue_prompt_sha256
            and task.public_tests_sha256 == self.public_tests_sha256
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": GENERATION_RECORD_SCHEMA,
            "task_id": self.task_id,
            "task_payload_sha256": self.task_payload_sha256,
            "split": self.split.value,
            "generation_seed": self.generation_seed,
            "mutation_kind": self.mutation_kind.value,
            "mutation_configuration_sha256": self.mutation_configuration_sha256,
            "clean_repository_sha256": self.clean_repository_sha256,
            "buggy_repository_sha256": self.buggy_repository_sha256,
            "issue_prompt_sha256": self.issue_prompt_sha256,
            "public_tests_sha256": self.public_tests_sha256,
            "hidden_tests_sha256": self.hidden_tests_sha256,
            "gold_patch_sha256": self.gold_patch_sha256,
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class RepositorySurgerySubmission:
    """Immutable patch submitted by one mind or later collective stage."""

    task_id: str
    task_payload_sha256: str
    producer_artifact_sha256: str
    patch_sha256: str
    patch_format: PatchFormat
    patch_size_bytes: int

    def __post_init__(self) -> None:
        _nonempty(self.task_id, "task_id")
        validate_sha256(self.task_payload_sha256)
        validate_sha256(self.producer_artifact_sha256)
        validate_sha256(self.patch_sha256)
        if not isinstance(self.patch_format, PatchFormat):
            raise TypeError("patch_format must be PatchFormat")
        _positive_int(self.patch_size_bytes, "patch_size_bytes")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": SUBMISSION_SCHEMA,
            "task_id": self.task_id,
            "task_payload_sha256": self.task_payload_sha256,
            "producer_artifact_sha256": self.producer_artifact_sha256,
            "patch_sha256": self.patch_sha256,
            "patch_format": self.patch_format.value,
            "patch_size_bytes": self.patch_size_bytes,
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


def build_visible_repository_surgery_task(
    *,
    task_id: str,
    split: TaskSplit,
    buggy_repository_sha256: str,
    issue_prompt_sha256: str,
    public_tests_sha256: str | None,
    max_visible_bytes: int,
    language: str = "python",
) -> SolverVisibleTask:
    """Construct the exact solver-visible half of a Repository Surgery task."""

    return SolverVisibleTask.create(
        task_id=task_id,
        task_family=REPOSITORY_SURGERY_FAMILY,
        split=split,
        repository_sha256=buggy_repository_sha256,
        prompt_sha256=issue_prompt_sha256,
        language=language,
        max_visible_bytes=max_visible_bytes,
        public_tests_sha256=public_tests_sha256,
    )
