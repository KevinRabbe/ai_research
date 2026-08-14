"""Generic capability, complementarity, and attribution metrics for capable minds."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Callable, Mapping, Sequence

from plural_cognition.population.credit import (
    CoalitionEvaluation,
    evaluate_all_coalitions,
    exact_shapley_values,
    leave_one_out_contributions,
)


@dataclass(frozen=True, slots=True)
class OutcomeTable:
    """Binary task outcomes for a fixed ordered population."""

    task_ids: tuple[str, ...]
    member_ids: tuple[str, ...]
    outcomes: tuple[tuple[bool, ...], ...]

    def __post_init__(self) -> None:
        if not self.task_ids:
            raise ValueError("at least one task is required")
        if not self.member_ids:
            raise ValueError("at least one member is required")
        if any(type(value) is not str or not value for value in self.task_ids):
            raise ValueError("task_ids must contain non-empty strings")
        if any(type(value) is not str or not value for value in self.member_ids):
            raise ValueError("member_ids must contain non-empty strings")
        if len(self.task_ids) != len(set(self.task_ids)):
            raise ValueError("task_ids must be unique")
        if len(self.member_ids) != len(set(self.member_ids)):
            raise ValueError("member_ids must be unique")
        if len(self.outcomes) != len(self.task_ids):
            raise ValueError("outcome row count must match task_ids")
        for row in self.outcomes:
            if len(row) != len(self.member_ids):
                raise ValueError("every outcome row must match member_ids")
            if any(type(value) is not bool for value in row):
                raise TypeError("outcomes must be bool")

    @property
    def task_count(self) -> int:
        return len(self.task_ids)

    @property
    def member_count(self) -> int:
        return len(self.member_ids)

    def member_outcomes(self, member_id: str) -> tuple[bool, ...]:
        try:
            index = self.member_ids.index(member_id)
        except ValueError as exc:
            raise KeyError(member_id) from exc
        return tuple(row[index] for row in self.outcomes)

    def member_scores(self) -> dict[str, float]:
        return {
            member_id: sum(self.member_outcomes(member_id)) / self.task_count
            for member_id in self.member_ids
        }

    @property
    def best_constituent_score(self) -> float:
        return max(self.member_scores().values())

    @property
    def strongest_member_ids(self) -> tuple[str, ...]:
        scores = self.member_scores()
        best = max(scores.values())
        return tuple(member for member in self.member_ids if scores[member] == best)

    @property
    def oracle_union_score(self) -> float:
        return sum(any(row) for row in self.outcomes) / self.task_count

    @property
    def complementarity_headroom(self) -> float:
        return self.oracle_union_score - self.best_constituent_score

    def unique_solve_counts(self) -> dict[str, int]:
        counts = {member_id: 0 for member_id in self.member_ids}
        for row in self.outcomes:
            if sum(row) != 1:
                continue
            index = row.index(True)
            counts[self.member_ids[index]] += 1
        return counts


@dataclass(frozen=True, slots=True)
class CollectiveSummary:
    task_count: int
    strongest_member_ids: tuple[str, ...]
    best_constituent_score: float
    oracle_union_score: float
    complementarity_headroom: float
    collective_score: float
    plural_uplift: float
    selection_headroom_utilization: float | None
    novel_collective_solve_count: int
    novel_collective_solve_rate: float


@dataclass(frozen=True, slots=True)
class StageDelta:
    task_count: int
    before_score: float
    after_score: float
    rescue_count: int
    damage_count: int
    unchanged_pass_count: int
    unchanged_fail_count: int

    @property
    def rescue_rate(self) -> float:
        return self.rescue_count / self.task_count

    @property
    def damage_rate(self) -> float:
        return self.damage_count / self.task_count

    @property
    def net_uplift(self) -> float:
        return self.after_score - self.before_score


@dataclass(frozen=True, slots=True)
class ErrorCorrelation:
    correlation: float | None
    task_count: int
    left_error_count: int
    right_error_count: int
    shared_error_count: int


@dataclass(frozen=True, slots=True)
class FourMindCredit:
    evaluation: CoalitionEvaluation[str]
    shapley_values: Mapping[str, float]
    leave_one_out: Mapping[str, float]


def _validate_binary_vector(values: Sequence[bool], task_count: int, field: str) -> tuple[bool, ...]:
    result = tuple(values)
    if len(result) != task_count:
        raise ValueError(f"{field} length must match task count")
    if any(type(value) is not bool for value in result):
        raise TypeError(f"{field} must contain bool values")
    return result


def summarize_collective(
    table: OutcomeTable,
    collective_outcomes: Sequence[bool],
) -> CollectiveSummary:
    outcomes = _validate_binary_vector(
        collective_outcomes,
        table.task_count,
        "collective_outcomes",
    )
    collective_score = sum(outcomes) / table.task_count
    best = table.best_constituent_score
    oracle = table.oracle_union_score
    headroom = oracle - best
    uplift = collective_score - best
    utilization = uplift / headroom if headroom > 0.0 else None
    novel_count = sum(
        collective and not any(row)
        for row, collective in zip(table.outcomes, outcomes, strict=True)
    )
    return CollectiveSummary(
        task_count=table.task_count,
        strongest_member_ids=table.strongest_member_ids,
        best_constituent_score=best,
        oracle_union_score=oracle,
        complementarity_headroom=headroom,
        collective_score=collective_score,
        plural_uplift=uplift,
        selection_headroom_utilization=utilization,
        novel_collective_solve_count=novel_count,
        novel_collective_solve_rate=novel_count / table.task_count,
    )


def compare_stages(
    task_ids: Sequence[str],
    before: Sequence[bool],
    after: Sequence[bool],
) -> StageDelta:
    tasks = tuple(task_ids)
    if not tasks:
        raise ValueError("at least one task is required")
    if any(type(task_id) is not str or not task_id for task_id in tasks):
        raise ValueError("task_ids must contain non-empty strings")
    if len(tasks) != len(set(tasks)):
        raise ValueError("task_ids must be unique")
    before_values = _validate_binary_vector(before, len(tasks), "before")
    after_values = _validate_binary_vector(after, len(tasks), "after")

    rescue = damage = unchanged_pass = unchanged_fail = 0
    for left, right in zip(before_values, after_values, strict=True):
        if not left and right:
            rescue += 1
        elif left and not right:
            damage += 1
        elif left and right:
            unchanged_pass += 1
        else:
            unchanged_fail += 1

    return StageDelta(
        task_count=len(tasks),
        before_score=sum(before_values) / len(tasks),
        after_score=sum(after_values) / len(tasks),
        rescue_count=rescue,
        damage_count=damage,
        unchanged_pass_count=unchanged_pass,
        unchanged_fail_count=unchanged_fail,
    )


def pairwise_error_correlation(
    left_outcomes: Sequence[bool],
    right_outcomes: Sequence[bool],
) -> ErrorCorrelation:
    left = tuple(left_outcomes)
    right = tuple(right_outcomes)
    if not left:
        raise ValueError("at least one task outcome is required")
    if len(left) != len(right):
        raise ValueError("outcome vectors must have equal length")
    if any(type(value) is not bool for value in left + right):
        raise TypeError("outcome vectors must contain bool values")

    left_errors = tuple(not value for value in left)
    right_errors = tuple(not value for value in right)
    count = len(left)
    left_error_count = sum(left_errors)
    right_error_count = sum(right_errors)
    shared_error_count = sum(
        left_error and right_error
        for left_error, right_error in zip(left_errors, right_errors, strict=True)
    )

    left_mean = left_error_count / count
    right_mean = right_error_count / count
    left_variance = left_mean * (1.0 - left_mean)
    right_variance = right_mean * (1.0 - right_mean)

    if left_variance == 0.0 or right_variance == 0.0:
        correlation = None
    else:
        covariance = (shared_error_count / count) - (left_mean * right_mean)
        correlation = covariance / sqrt(left_variance * right_variance)
        correlation = max(-1.0, min(1.0, correlation))

    return ErrorCorrelation(
        correlation=correlation,
        task_count=count,
        left_error_count=left_error_count,
        right_error_count=right_error_count,
        shared_error_count=shared_error_count,
    )


def error_correlation_matrix(table: OutcomeTable) -> tuple[tuple[float | None, ...], ...]:
    rows: list[list[float | None]] = [
        [None for _ in table.member_ids] for _ in table.member_ids
    ]
    member_vectors = tuple(
        table.member_outcomes(member_id) for member_id in table.member_ids
    )

    for index, vector in enumerate(member_vectors):
        error_count = sum(not value for value in vector)
        rows[index][index] = 1.0 if 0 < error_count < table.task_count else None

    for left_index in range(table.member_count):
        for right_index in range(left_index + 1, table.member_count):
            result = pairwise_error_correlation(
                member_vectors[left_index],
                member_vectors[right_index],
            )
            rows[left_index][right_index] = result.correlation
            rows[right_index][left_index] = result.correlation

    return tuple(tuple(row) for row in rows)


def evaluate_four_mind_credit(
    member_ids: Sequence[str],
    value_function: Callable[[frozenset[str]], float],
) -> FourMindCredit:
    members = tuple(member_ids)
    if len(members) != 4:
        raise ValueError("exact capable-collective credit currently requires four minds")
    evaluation = evaluate_all_coalitions(members, value_function)
    return FourMindCredit(
        evaluation=evaluation,
        shapley_values=exact_shapley_values(evaluation),
        leave_one_out=leave_one_out_contributions(evaluation),
    )
