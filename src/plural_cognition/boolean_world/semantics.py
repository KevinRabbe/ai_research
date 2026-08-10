"""Exact evaluation and exhaustive semantic comparison for Boolean mechanisms."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Mapping, Sequence

from .ast import And, Const, Expr, Ite, Not, Or, Var, variables


@dataclass(frozen=True, slots=True)
class EquivalenceResult:
    equivalent: bool
    variable_order: tuple[str, ...]
    counterexample: dict[str, bool] | None


def evaluate(expr: Expr, assignment: Mapping[str, bool]) -> bool:
    """Evaluate an expression under one complete assignment.

    Missing variables fail closed with ``KeyError``. Values must be actual booleans;
    integers such as 0 and 1 are rejected to keep experiment contracts exact.
    """

    match expr:
        case Const(value=value):
            return value
        case Var(name=name):
            value = assignment[name]
            if type(value) is not bool:
                raise TypeError(f"assignment for {name!r} must be bool, got {type(value).__name__}")
            return value
        case Not(child=child):
            return not evaluate(child, assignment)
        case And(children=children):
            return all(evaluate(child, assignment) for child in children)
        case Or(children=children):
            return any(evaluate(child, assignment) for child in children)
        case Ite(condition=condition, when_true=when_true, when_false=when_false):
            branch = when_true if evaluate(condition, assignment) else when_false
            return evaluate(branch, assignment)
        case _:
            raise TypeError(f"unsupported expression type: {type(expr)!r}")


def _resolve_variable_order(
    expressions: Sequence[Expr], variable_order: Sequence[str] | None
) -> tuple[str, ...]:
    referenced = set().union(*(set(variables(expr)) for expr in expressions))
    if variable_order is None:
        return tuple(sorted(referenced))

    order = tuple(variable_order)
    if len(order) != len(set(order)):
        raise ValueError("variable_order must not contain duplicates")

    missing = referenced.difference(order)
    if missing:
        raise ValueError(f"variable_order is missing referenced variables: {sorted(missing)!r}")
    return order


def assignments(variable_order: Sequence[str]) -> tuple[dict[str, bool], ...]:
    """Enumerate assignments in deterministic lexicographic bit order."""

    order = tuple(variable_order)
    return tuple(dict(zip(order, values, strict=True)) for values in product((False, True), repeat=len(order)))


def truth_table(
    expr: Expr, variable_order: Sequence[str] | None = None
) -> tuple[tuple[str, ...], tuple[bool, ...]]:
    """Return a deterministic exhaustive truth table."""

    order = _resolve_variable_order((expr,), variable_order)
    outputs = tuple(evaluate(expr, assignment) for assignment in assignments(order))
    return order, outputs


def semantic_key(expr: Expr, variable_order: Sequence[str] | None = None) -> tuple[tuple[str, ...], int]:
    """Return an exact canonical semantic key as ``(variable_order, output_bitset)``."""

    order, outputs = truth_table(expr, variable_order)
    bitset = 0
    for index, output in enumerate(outputs):
        if output:
            bitset |= 1 << index
    return order, bitset


def first_counterexample(
    left: Expr, right: Expr, variable_order: Sequence[str] | None = None
) -> dict[str, bool] | None:
    """Return the first assignment on which two expressions disagree."""

    order = _resolve_variable_order((left, right), variable_order)
    for assignment in assignments(order):
        if evaluate(left, assignment) != evaluate(right, assignment):
            return assignment
    return None


def exact_equivalence(
    left: Expr, right: Expr, variable_order: Sequence[str] | None = None
) -> EquivalenceResult:
    """Compare two expressions exhaustively."""

    order = _resolve_variable_order((left, right), variable_order)
    counterexample = first_counterexample(left, right, order)
    return EquivalenceResult(counterexample is None, order, counterexample)


def semantic_distance(
    left: Expr, right: Expr, variable_order: Sequence[str] | None = None
) -> int:
    """Count truth-table assignments on which two expressions disagree."""

    order = _resolve_variable_order((left, right), variable_order)
    return sum(
        evaluate(left, assignment) != evaluate(right, assignment)
        for assignment in assignments(order)
    )
