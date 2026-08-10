"""Frozen candidate-model bakeoff and four-mind population selection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import combinations
from statistics import mean
from typing import Iterable, Sequence

from .artifacts import ResourceUsage
from .metrics import OutcomeTable, pairwise_error_correlation
from .mind import MindIdentity


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


@dataclass(frozen=True, slots=True)
class BakeoffPlan:
    """Predeclared candidate set, task set, and population-selection rule."""

    task_ids: tuple[str, ...]
    candidates: tuple[CandidateModel, ...]
    min_valid_rate: float = 0.95
    population_size: int = 4
    require_strongest_member: bool = True

    def __post_init__(self) -> None:
        if not self.task_ids:
            raise ValueError("at least one selection task is required")
        if any(type(task_id) is not str or not task_id for task_id in self.task_ids):
            raise ValueError("task_ids must contain non-empty strings")
        if len(self.task_ids) != len(set(self.task_ids)):
            raise ValueError("task_ids must be unique")
        if not self.candidates:
            raise ValueError("at least one candidate is required")
        candidate_ids = tuple(candidate.candidate_id for candidate in self.candidates)
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate IDs must be unique")
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


@dataclass(frozen=True, slots=True)
class CandidateTaskResult:
    candidate_id: str
    task_id: str
    valid: bool
    passed: bool
    raw_artifact_sha256: str
    evaluation_sha256: str
    resources: ResourceUsage

    def __post_init__(self) -> None:
        if type(self.candidate_id) is not str or not self.candidate_id:
            raise ValueError("candidate_id must be a non-empty string")
        if type(self.task_id) is not str or not self.task_id:
            raise ValueError("task_id must be a non-empty string")
        if type(self.valid) is not bool or type(self.passed) is not bool:
            raise TypeError("valid and passed must be bool")
        if self.passed and not self.valid:
            raise ValueError("an invalid result cannot be marked passed")
        for field in ("raw_artifact_sha256", "evaluation_sha256"):
            value = getattr(self, field)
            if type(value) is not str or len(value) != 64:
                raise ValueError(f"{field} must contain 64 lowercase hexadecimal characters")
            try:
                int(value, 16)
            except ValueError as exc:
                raise ValueError(f"{field} must be hexadecimal") from exc
            if value != value.lower():
                raise ValueError(f"{field} must use lowercase hexadecimal")
        if not isinstance(self.resources, ResourceUsage):
            raise TypeError("resources must be ResourceUsage")


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
    task_ids: tuple[str, ...]
    candidate_ids: tuple[str, ...]
    by_candidate: dict[str, tuple[CandidateTaskResult, ...]]

    def outcomes(self, candidate_id: str) -> tuple[bool, ...]:
        return tuple(item.valid and item.passed for item in self.by_candidate[candidate_id])


def _index_results(
    plan: BakeoffPlan,
    results: Sequence[CandidateTaskResult],
) -> _IndexedResults:
    expected_candidates = tuple(candidate.candidate_id for candidate in plan.candidates)
    expected_pairs = {
        (candidate_id, task_id)
        for candidate_id in expected_candidates
        for task_id in plan.task_ids
    }
    actual: dict[tuple[str, str], CandidateTaskResult] = {}
    for item in results:
        key = (item.candidate_id, item.task_id)
        if key in actual:
            raise ValueError(f"duplicate bakeoff result: {key!r}")
        actual[key] = item
    if set(actual) != expected_pairs:
        missing = expected_pairs.difference(actual)
        extra = set(actual).difference(expected_pairs)
        raise ValueError(
            f"bakeoff result matrix mismatch: missing={len(missing)}, extra={len(extra)}"
        )
    by_candidate = {
        candidate_id: tuple(actual[(candidate_id, task_id)] for task_id in plan.task_ids)
        for candidate_id in expected_candidates
    }
    return _IndexedResults(plan.task_ids, expected_candidates, by_candidate)


def _diagnostics(indexed: _IndexedResults) -> tuple[CandidateDiagnostic, ...]:
    result: list[CandidateDiagnostic] = []
    task_count = len(indexed.task_ids)
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
                total_tokens=sum(
                    item.resources.input_tokens + item.resources.output_tokens
                    for item in items
                ),
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
        tuple(indexed.by_candidate[candidate_id][task_index].valid and indexed.by_candidate[candidate_id][task_index].passed for candidate_id in members)
        for task_index in range(len(indexed.task_ids))
    )
    return OutcomeTable(indexed.task_ids, members, rows)


def select_population(
    plan: BakeoffPlan,
    results: Sequence[CandidateTaskResult],
) -> PopulationSelection:
    """Select a four-mind population without using protected confirmation data.

    Selection is deterministic and lexicographic:

    1. exclude candidates below ``min_valid_rate``;
    2. identify the strongest eligible individual by pass count, then lower
       accelerator time, lower token use, then candidate ID;
    3. if configured, require every candidate population to contain that strongest
       individual so plural uplift cannot be inflated by choosing a weaker anchor;
    4. maximize oracle-union solved-task count;
    5. maximize summed individual solved-task counts;
    6. minimize total accelerator time;
    7. break remaining ties by candidate IDs.

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
        coalitions = tuple(
            coalition for coalition in coalitions if strongest in coalition
        )
    if not coalitions:
        raise AssertionError("eligible population exists but no coalition survived")

    def coalition_key(coalition: tuple[str, ...]) -> tuple[int, int, int, tuple[str, ...]]:
        table = _table_for(indexed, coalition)
        union_count = round(table.oracle_union_score * table.task_count)
        summed_passes = sum(diagnostic_by_id[item].pass_count for item in coalition)
        accelerator_time = sum(
            diagnostic_by_id[item].total_accelerator_time_ms for item in coalition
        )
        return (-union_count, -summed_passes, accelerator_time, coalition)

    selected = min(coalitions, key=coalition_key)
    table = _table_for(indexed, selected)
    return PopulationSelection(
        status=PopulationSelectionStatus.SELECTED,
        diagnostics=diagnostics,
        eligible_candidate_ids=eligible,
        strongest_candidate_id=strongest,
        selected_candidate_ids=selected,
        best_constituent_score=table.best_constituent_score,
        oracle_union_score=table.oracle_union_score,
        complementarity_headroom=table.complementarity_headroom,
        mean_pairwise_error_correlation=_mean_error_correlation(table),
    )
