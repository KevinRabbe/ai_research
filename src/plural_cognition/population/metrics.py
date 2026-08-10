"""Exact functional-diversity metrics for Boolean population members."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Sequence

from plural_cognition.boolean_world.ast import Expr
from plural_cognition.boolean_world.semantics import assignments, evaluate, semantic_distance


@dataclass(frozen=True, slots=True)
class ErrorCorrelation:
    """Pairwise correlation summary for two binary error vectors.

    ``correlation`` is ``None`` when either member has zero error variance, because
    Pearson's phi coefficient is mathematically undefined in that case. Callers
    must not silently replace that state with perfect agreement or zero correlation.
    """

    correlation: float | None
    assignment_count: int
    left_error_count: int
    right_error_count: int
    shared_error_count: int


def _validate_order(variable_order: Sequence[str]) -> tuple[str, ...]:
    order = tuple(variable_order)
    if not order:
        raise ValueError("variable_order must not be empty")
    if len(order) != len(set(order)):
        raise ValueError("variable_order must not contain duplicates")
    return order


def _validate_candidates(candidates: Sequence[Expr]) -> tuple[Expr, ...]:
    result = tuple(candidates)
    if not result:
        raise ValueError("at least one candidate is required")
    return result


def semantic_distance_matrix(
    candidates: Sequence[Expr], variable_order: Sequence[str]
) -> tuple[tuple[float, ...], ...]:
    """Return exact normalized truth-table distances for all candidate pairs."""

    members = _validate_candidates(candidates)
    order = _validate_order(variable_order)
    assignment_count = 1 << len(order)
    rows = [[0.0 for _ in members] for _ in members]

    for left_index, left in enumerate(members):
        for right_index in range(left_index + 1, len(members)):
            distance = semantic_distance(left, members[right_index], order) / assignment_count
            rows[left_index][right_index] = distance
            rows[right_index][left_index] = distance

    return tuple(tuple(row) for row in rows)


def _error_vector(
    candidate: Expr, target: Expr, variable_order: tuple[str, ...]
) -> tuple[bool, ...]:
    return tuple(
        evaluate(candidate, assignment) != evaluate(target, assignment)
        for assignment in assignments(variable_order)
    )


def pairwise_error_correlation(
    left: Expr,
    right: Expr,
    target: Expr,
    variable_order: Sequence[str],
) -> ErrorCorrelation:
    """Return the exact phi/Pearson correlation of two semantic error vectors."""

    order = _validate_order(variable_order)
    left_errors = _error_vector(left, target, order)
    right_errors = _error_vector(right, target, order)
    assignment_count = len(left_errors)

    left_error_count = sum(left_errors)
    right_error_count = sum(right_errors)
    shared_error_count = sum(
        left_error and right_error
        for left_error, right_error in zip(left_errors, right_errors, strict=True)
    )

    left_mean = left_error_count / assignment_count
    right_mean = right_error_count / assignment_count
    left_variance = left_mean * (1.0 - left_mean)
    right_variance = right_mean * (1.0 - right_mean)

    if left_variance == 0.0 or right_variance == 0.0:
        correlation = None
    else:
        covariance = (shared_error_count / assignment_count) - (left_mean * right_mean)
        correlation = covariance / sqrt(left_variance * right_variance)
        correlation = max(-1.0, min(1.0, correlation))

    return ErrorCorrelation(
        correlation=correlation,
        assignment_count=assignment_count,
        left_error_count=left_error_count,
        right_error_count=right_error_count,
        shared_error_count=shared_error_count,
    )


def error_correlation_matrix(
    candidates: Sequence[Expr],
    target: Expr,
    variable_order: Sequence[str],
) -> tuple[tuple[float | None, ...], ...]:
    """Return pairwise semantic error correlations.

    Diagonal entries are ``1.0`` only when the member's error vector has non-zero
    variance. They are ``None`` for always-correct or always-wrong members because
    correlation is undefined for a constant vector.
    """

    members = _validate_candidates(candidates)
    order = _validate_order(variable_order)
    vectors = tuple(_error_vector(member, target, order) for member in members)

    rows: list[list[float | None]] = [
        [None for _ in members] for _ in members
    ]

    for index, vector in enumerate(vectors):
        error_count = sum(vector)
        rows[index][index] = 1.0 if 0 < error_count < len(vector) else None

    for left_index, left in enumerate(members):
        for right_index in range(left_index + 1, len(members)):
            result = pairwise_error_correlation(
                left, members[right_index], target, order
            )
            rows[left_index][right_index] = result.correlation
            rows[right_index][left_index] = result.correlation

    return tuple(tuple(row) for row in rows)
