"""Exact cooperative contribution metrics for small plural-cognition populations."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import factorial, isfinite
from typing import Callable, Hashable, Iterable, TypeVar

Member = TypeVar("Member", bound=Hashable)
CoalitionValue = Callable[[frozenset[Member]], float]


@dataclass(frozen=True, slots=True)
class CoalitionEvaluation:
    """Deterministic values for every subset of a fixed member population."""

    members: tuple[Member, ...]
    values: dict[frozenset[Member], float]

    def __post_init__(self) -> None:
        if not self.members:
            raise ValueError("at least one member is required")
        if len(self.members) != len(set(self.members)):
            raise ValueError("member IDs must be unique")

        expected = set(_coalitions(self.members))
        if set(self.values) != expected:
            missing = expected.difference(self.values)
            extra = set(self.values).difference(expected)
            raise ValueError(
                f"coalition map mismatch: missing={len(missing)}, extra={len(extra)}"
            )
        if any(not isfinite(float(value)) for value in self.values.values()):
            raise ValueError("coalition values must be finite")

    @property
    def empty_value(self) -> float:
        return self.values[frozenset()]

    @property
    def full_value(self) -> float:
        return self.values[frozenset(self.members)]


def _validate_members(members: Iterable[Member]) -> tuple[Member, ...]:
    result = tuple(members)
    if not result:
        raise ValueError("at least one member is required")
    if len(result) != len(set(result)):
        raise ValueError("member IDs must be unique")
    if len(result) > 16:
        raise ValueError("exact coalition enumeration is bounded to at most 16 members")
    return result


def _coalitions(members: tuple[Member, ...]) -> tuple[frozenset[Member], ...]:
    return tuple(
        frozenset(subset)
        for size in range(len(members) + 1)
        for subset in combinations(members, size)
    )


def evaluate_all_coalitions(
    members: Iterable[Member], value_function: CoalitionValue[Member]
) -> CoalitionEvaluation[Member]:
    """Evaluate every member subset exactly once in deterministic order."""

    ordered = _validate_members(members)
    values: dict[frozenset[Member], float] = {}
    for coalition in _coalitions(ordered):
        value = float(value_function(coalition))
        if not isfinite(value):
            raise ValueError(f"non-finite value for coalition {coalition!r}")
        values[coalition] = value
    return CoalitionEvaluation(ordered, values)


def exact_shapley_values(
    evaluation: CoalitionEvaluation[Member],
) -> dict[Member, float]:
    """Compute exact Shapley values from a complete coalition table."""

    members = evaluation.members
    member_count = len(members)
    denominator = factorial(member_count)
    result: dict[Member, float] = {}

    for member in members:
        others = tuple(candidate for candidate in members if candidate != member)
        contribution = 0.0
        for subset_size in range(len(others) + 1):
            weight = (
                factorial(subset_size)
                * factorial(member_count - subset_size - 1)
                / denominator
            )
            for subset_tuple in combinations(others, subset_size):
                subset = frozenset(subset_tuple)
                with_member = subset | {member}
                contribution += weight * (
                    evaluation.values[with_member] - evaluation.values[subset]
                )
        result[member] = contribution

    return result


def leave_one_out_contributions(
    evaluation: CoalitionEvaluation[Member],
) -> dict[Member, float]:
    """Return the full-coalition score drop caused by removing each member."""

    full = frozenset(evaluation.members)
    full_value = evaluation.values[full]
    return {
        member: full_value - evaluation.values[full - {member}]
        for member in evaluation.members
    }
