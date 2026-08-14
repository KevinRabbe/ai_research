"""Frozen candidate-model bakeoff and four-mind population selection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from itertools import combinations
from statistics import mean
from typing import Any, Iterable, Sequence

from .artifacts import ResourceUsage, TaskIdentity
from .content_store import validate_sha256
from .metrics import OutcomeTable, pairwise_error_correlation
from .mind import MindIdentity

BAKEOFF_PLAN_SCHEMA = "plural-cognition-capable-bakeoff-plan-v1"
BAKEOFF_RESULT_SCHEMA = "plural-cognition-capable-bakeoff-result-v1"


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


class DeploymentClass(str, Enum):
    LOCAL = "local"
    REMOTE = "remote"


class PopulationSelectionStatus(str, Enum):
    SELECTED = "selected"
    INSUFFICIENT_ELIGIBLE = "insufficient-eligible"


@dataclass(frozen=True, slots=True)
class CandidateModel:
    """Research metadata for one model/backend configuration in the bakeoff."""

    candidate_id: str
    mind: MindIdentity
    deployment_class: DeploymentClass
    architecture_class: str
    context_tokens: int
    quantization: str
    total_parameters: int | None = None
    active_parameters: int | None = None

    def __post_init__(self) -> None:
        if type(self.candidate_id) is not str or not self.candidate_id:
            raise ValueError("candidate_id must be a non-empty string")
        if not isinstance(self.mind, MindIdentity):
            raise TypeError("mind must be MindIdentity")
        if not isinstance(self.deployment_class, DeploymentClass):
            raise TypeError("deployment_class must be DeploymentClass")
        if type(self.architecture_class) is not str or not self.architecture_class:
            raise ValueError("architecture_class must be a non-empty string")
        if type(self.context_tokens) is not int or self.context_tokens < 1:
            raise ValueError("context_tokens must be a positive integer")
        if type(self.quantization) is not str or not self.quantization:
            raise ValueError("quantization must be a non-empty string")
        for field, value in (
            ("total_parameters", self.total_parameters),
            ("active_parameters", self.active_parameters),
        ):
            if value is not None and (type(value) is not int or value < 1):
                raise ValueError(f"{field} must be a positive integer or None")
        if (
            self.total_parameters is not None
            and self.active_parameters is not None
            and self.active_parameters > self.total_parameters
        ):
            raise ValueError("active_parameters cannot exceed total_parameters")
        if self.candidate_id != self.mind.mind_id:
            raise ValueError("candidate_id must equal mind.mind_id")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "mind": self.mind.canonical_payload(),
            "deployment_class": self.deployment_class.value,
            "architecture_class": self.architecture_class,
            "context_tokens": self.context_tokens,
            "quantization": self.quantization,
            "total_parameters": self.total_parameters,
            "active_parameters": self.active_parameters,
        }


@dataclass(frozen=True, slots=True)
class BakeoffPlan:
    """Predeclared exact task set, candidate set, protocol, and selection rule."""

    tasks: tuple[TaskIdentity, ...]
    candidates: tuple[CandidateModel, ...]
    raw_protocol_sha256: str
    resource_budget_sha256: str
    min_valid_rate: float = 0.95
    population_size: int = 4
    require_strongest_member: bool = True

    def __post_init__(self) -> None:
        if not self.tasks:
            raise ValueError("at least one selection task is required")
        if any(not isinstance(task, TaskIdentity) for task in self.tasks):
            raise TypeError("tasks must contain TaskIdentity values")
        task_ids = tuple(task.task_id for task in self.tasks)
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("task IDs must be unique")
        if not self.candidates:
            raise ValueError("at least one candidate is required")
        candidate_ids = tuple(candidate.candidate_id for candidate in self.candidates)
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate IDs must be unique")
        validate_sha256(self.raw_protocol_sha256)
        validate_sha256(self.resource_budget_sha256)
        if type(self.min_valid_rate) not in (int, float):
            raise TypeError("min_valid_rate must be a plain int or float")
        if not 0.0 <= float(self.min_valid_rate) <= 1.0:
            raise ValueError("min_valid_rate must be in [0, 1]")
        if type(self.population_size) is not int or self.population_size < 1:
            raise ValueError("population_size must be a positive integer")
        if self.population_size > len(self.candidates):
            raise ValueError("population_size cannot exceed candidate count")
        if type(self.require_strongest_member) is not bool:
            raise TypeError("require_strongest_member must be bool")

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(task.task_id for task in self.tasks)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": BAKEOFF_PLAN_SCHEMA,
            "tasks": [task.canonical_payload() for task in self.tasks],
            "candidates": [candidate.canonical_payload() for candidate in self.candidates],
            "raw_protocol_sha256": self.raw_protocol_sha256,
            "resource_budget_sha256": self.resource_budget_sha256,
            "min_valid_rate": float(self.min_valid_rate),
            "population_size": self.population_size,
            "require_strongest_member": self.require_strongest_member,
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class CandidateTaskResult:
    candidate_id: str
    task: TaskIdentity
    valid: bool
    passed: bool
    raw_artifact_sha256: str
    evaluation_sha256: str
    resources: ResourceUsage

    def __post_init__(self) -> None:
        if type(self.candidate_id) is not str or not self.candidate_id:
            raise ValueError("candidate_id must be a non-empty string")
        if not isinstance(self.task, TaskIdentity):
            raise TypeError("task must be TaskIdentity")
        if type(self.valid) is not bool or type(self.passed) is not bool:
            raise TypeError("valid and passed must be bool")
        if self.passed and not self.valid:
            raise ValueError("an invalid result cannot be marked passed")
        validate_sha256(self.raw_artifact_sha256)
        validate_sha256(self.evaluation_sha256)
        if not isinstance(self.resources, ResourceUsage):
            raise TypeError("resources must be ResourceUsage")

    @property
    def task_id(self) -> str:
        return self.task.task_id

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": BAKEOFF_RESULT_SCHEMA,
            "candidate_id": self.candidate_id,
            "task": self.task.canonical_payload(),
            "valid": self.valid,
            "passed": self.passed,
            "raw_artifact_sha256": self.raw_artifact_sha256,
            "evaluation_sha256": self.evaluation_sha256,
            "resources": self.resources.canonical_payload(),
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()


@dataclass(frozen=True, slots=True)
class CandidateDiagnostic:
    candidate_id: str
    score: float
    valid_rate: float
    pass_count: int
    valid_count: int
    total_accelerator_time_ms: int
    total_tokens: int


@dataclass(frozen=True, slots=True)
class PopulationSelection:
    status: PopulationSelectionStatus
    bakeoff_plan_sha256: str
    diagnostics: tuple[CandidateDiagnostic, ...]
    eligible_candidate_ids: tuple[str, ...]
    strongest_candidate_id: str | None
    selected_candidate_ids: tuple[str, ...]
    best_constituent_score: float | None
    oracle_union_score: float | None
    complementarity_headroom: float | None
    mean_pairwise_error_correlation: float | None


@dataclass(frozen=True, slots=True)
class _IndexedResults:
    tasks: tuple[TaskIdentity, ...]
    candidate_ids: tuple[str, ...]
    by_candidate: dict[str, tuple[CandidateTaskResult, ...]]

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(task.task_id for task in self.tasks)

    def outcomes(self, candidate_id: str) -> tuple[bool, ...]:
        return tuple(item.valid and item.passed for item in self.by_candidate[candidate_id])


def _index_results(
    plan: BakeoffPlan,
    results: Sequence[CandidateTaskResult],
) -> _IndexedResults:
    expected_candidates = tuple(candidate.candidate_id for candidate in plan.candidates)
    expected_tasks = {task.task_id: task for task in plan.tasks}
    expected_pairs = {
        (candidate_id, task.task_id)
        for candidate_id in expected_candidates
        for task in plan.tasks
    }
    actual: dict[tuple[str, str], CandidateTaskResult] = {}
    for item in results:
        key = (item.candidate_id, item.task_id)
        if key in actual:
            raise ValueError(f"duplicate bakeoff result: {key!r}")
        expected_task = expected_tasks.get(item.task_id)
        if expected_task is not None and item.task != expected_task:
            raise ValueError(
                f"bakeoff result task payload differs from plan for {item.task_id!r}"
            )
        actual[key] = item
    if set(actual) != expected_pairs:
        missing = expected_pairs.difference(actual)
        extra = set(actual).difference(expected_pairs)
        raise ValueError(
            f"bakeoff result matrix mismatch: missing={len(missing)}, extra={len(extra)}"
        )
    by_candidate = {
        candidate_id: tuple(
            actual[(candidate_id, task.task_id)] for task in plan.tasks
        )
        for candidate_id in expected_candidates
    }
    return _IndexedResults(plan.tasks, expected_candidates, by_candidate)


def _diagnostics(indexed: _IndexedResults) -> tuple[CandidateDiagnostic, ...]:
    result: list[CandidateDiagnostic] = []
    task_count = len(indexed.tasks)
    for candidate_id in indexed.candidate_ids:
        items = indexed.by_candidate[candidate_id]
        valid_count = sum(item.valid for item in items)
        pass_count = sum(item.valid and item.passed for item in items)
        result.append(
            CandidateDiagnostic(
                candidate_id=candidate_id,
                score=pass_count / task_count,
                valid_rate=valid_count / task_count,
                pass_count=pass_count,
                valid_count=valid_count,
                total_accelerator_time_ms=sum(
                    item.resources.accelerator_time_ms for item in items
                ),
                total_tokens=sum(item.resources.total_tokens for item in items),
            )
        )
    return tuple(result)


def _mean_error_correlation(table: OutcomeTable) -> float | None:
    values: list[float] = []
    for left, right in combinations(table.member_ids, 2):
        correlation = pairwise_error_correlation(
            table.member_outcomes(left), table.member_outcomes(right)
        ).correlation
        if correlation is not None:
            values.append(correlation)
    return mean(values) if values else None


def _table_for(
    indexed: _IndexedResults,
    candidate_ids: Iterable[str],
) -> OutcomeTable:
    members = tuple(candidate_ids)
    rows = tuple(
        tuple(
            indexed.by_candidate[candidate_id][task_index].valid
            and indexed.by_candidate[candidate_id][task_index].passed
            for candidate_id in members
        )
        for task_index in range(len(indexed.tasks))
    )
    return OutcomeTable(indexed.task_ids, members, rows)


def select_population(
    plan: BakeoffPlan,
    results: Sequence[CandidateTaskResult],
) -> PopulationSelection:
    """Select a four-mind population without using protected confirmation data.

    Selection is deterministic and lexicographic:

    1. require results for the exact content-bound tasks in ``plan``;
    2. exclude candidates below ``min_valid_rate``;
    3. identify the strongest eligible individual by pass count, then lower
       accelerator time, lower token use, then candidate ID;
    4. if configured, require every candidate population to contain that strongest
       individual so plural uplift cannot be inflated by choosing a weaker anchor;
    5. maximize oracle-union solved-task count;
    6. maximize summed individual solved-task counts;
    7. minimize total accelerator time;
    8. break remaining ties by candidate IDs.

    Error correlation is reported diagnostically but is not used as a tie-breaker
    because it is undefined for constant error vectors.
    """

    indexed = _index_results(plan, results)
    diagnostics = _diagnostics(indexed)
    diagnostic_by_id = {item.candidate_id: item for item in diagnostics}
    eligible = tuple(
        candidate_id
        for candidate_id in indexed.candidate_ids
        if diagnostic_by_id[candidate_id].valid_rate >= plan.min_valid_rate
    )

    if len(eligible) < plan.population_size:
        return PopulationSelection(
            status=PopulationSelectionStatus.INSUFFICIENT_ELIGIBLE,
            bakeoff_plan_sha256=plan.sha256,
            diagnostics=diagnostics,
            eligible_candidate_ids=eligible,
            strongest_candidate_id=None,
            selected_candidate_ids=(),
            best_constituent_score=None,
            oracle_union_score=None,
            complementarity_headroom=None,
            mean_pairwise_error_correlation=None,
        )

    strongest = min(
        eligible,
        key=lambda candidate_id: (
            -diagnostic_by_id[candidate_id].pass_count,
            diagnostic_by_id[candidate_id].total_accelerator_time_ms,
            diagnostic_by_id[candidate_id].total_tokens,
            candidate_id,
        ),
    )

    coalitions = tuple(combinations(eligible, plan.population_size))
    if plan.require_strongest_member:
        coalitions = tuple(coalition for coalition in coalitions if strongest in coalition)
    if not coalitions:
        raise AssertionError("eligible population exists but no coalition survived")

    def coalition_key(coalition: tuple[str, ...]) -> tuple[int, int, int, tuple[str, ...]]:
        table = _table_for(indexed, coalition)
        union_count = sum(any(row) for row in table.outcomes)
        summed_passes = sum(diagnostic_by_id[item].pass_count for item in coalition)
        accelerator_time = sum(
            diagnostic_by_id[item].total_accelerator_time_ms for item in coalition
        )
        return (-union_count, -summed_passes, accelerator_time, coalition)

    selected = min(coalitions, key=coalition_key)
    table = _table_for(indexed, selected)
    return PopulationSelection(
        status=PopulationSelectionStatus.SELECTED,
        bakeoff_plan_sha256=plan.sha256,
        diagnostics=diagnostics,
        eligible_candidate_ids=eligible,
        strongest_candidate_id=strongest,
        selected_candidate_ids=selected,
        best_constituent_score=table.best_constituent_score,
        oracle_union_score=table.oracle_union_score,
        complementarity_headroom=table.complementarity_headroom,
        mean_pairwise_error_correlation=_mean_error_correlation(table),
    )
