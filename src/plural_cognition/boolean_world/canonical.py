"""Deterministic structural normalization for Boolean mechanism ASTs."""

from __future__ import annotations

from .ast import And, Const, Expr, Ite, Not, Or, Var


def structural_key(expr: Expr) -> tuple:
    """Return a fully comparable deterministic key for a normalized or raw AST."""

    match expr:
        case Const(value=value):
            return (0, value)
        case Var(name=name):
            return (1, name)
        case Not(child=child):
            return (2, structural_key(child))
        case And(children=children):
            return (3, tuple(structural_key(child) for child in children))
        case Or(children=children):
            return (4, tuple(structural_key(child) for child in children))
        case Ite(condition=condition, when_true=when_true, when_false=when_false):
            return (
                5,
                structural_key(condition),
                structural_key(when_true),
                structural_key(when_false),
            )
        case _:
            raise TypeError(f"unsupported expression type: {type(expr)!r}")


def _contains_complement(children: tuple[Expr, ...]) -> bool:
    child_set = set(children)
    return any(Not(child) in child_set for child in children if not isinstance(child, Not))


def _absorb(children: tuple[Expr, ...], nested_type: type[And] | type[Or]) -> tuple[Expr, ...]:
    """Apply A OR (A AND B) = A and its dual."""

    direct = set(children)
    retained: list[Expr] = []
    for child in children:
        if isinstance(child, nested_type) and any(grandchild in direct for grandchild in child.children):
            continue
        retained.append(child)
    return tuple(retained)


def normalize(expr: Expr) -> Expr:
    """Return a deterministic, idempotent structural normal form.

    This is intentionally not a complete Boolean minimizer. Exact equivalence is
    established separately through exhaustive semantics.
    """

    match expr:
        case Const() | Var():
            return expr

        case Not(child=raw_child):
            child = normalize(raw_child)
            match child:
                case Const(value=value):
                    return Const(not value)
                case Not(child=grandchild):
                    return grandchild
                case _:
                    return Not(child)

        case And(children=raw_children):
            flattened: list[Expr] = []
            for raw_child in raw_children:
                child = normalize(raw_child)
                if child == Const(False):
                    return Const(False)
                if child == Const(True):
                    continue
                if isinstance(child, And):
                    flattened.extend(child.children)
                else:
                    flattened.append(child)

            unique = tuple(sorted(set(flattened), key=structural_key))
            if _contains_complement(unique):
                return Const(False)
            unique = _absorb(unique, Or)
            if not unique:
                return Const(True)
            if len(unique) == 1:
                return unique[0]
            return And(unique)

        case Or(children=raw_children):
            flattened: list[Expr] = []
            for raw_child in raw_children:
                child = normalize(raw_child)
                if child == Const(True):
                    return Const(True)
                if child == Const(False):
                    continue
                if isinstance(child, Or):
                    flattened.extend(child.children)
                else:
                    flattened.append(child)

            unique = tuple(sorted(set(flattened), key=structural_key))
            if _contains_complement(unique):
                return Const(True)
            unique = _absorb(unique, And)
            if not unique:
                return Const(False)
            if len(unique) == 1:
                return unique[0]
            return Or(unique)

        case Ite(condition=raw_condition, when_true=raw_true, when_false=raw_false):
            condition = normalize(raw_condition)
            when_true = normalize(raw_true)
            when_false = normalize(raw_false)

            if condition == Const(True):
                return when_true
            if condition == Const(False):
                return when_false
            if when_true == when_false:
                return when_true
            if when_true == Const(True) and when_false == Const(False):
                return condition
            if when_true == Const(False) and when_false == Const(True):
                return normalize(Not(condition))
            return Ite(condition, when_true, when_false)

        case _:
            raise TypeError(f"unsupported expression type: {type(expr)!r}")


def canonical_text(expr: Expr) -> str:
    """Serialize the normalized AST to an unambiguous deterministic string."""

    normalized = normalize(expr)

    def render(node: Expr) -> str:
        match node:
            case Const(value=True):
                return "TRUE"
            case Const(value=False):
                return "FALSE"
            case Var(name=name):
                return name
            case Not(child=child):
                return f"NOT({render(child)})"
            case And(children=children):
                return "AND(" + ",".join(render(child) for child in children) + ")"
            case Or(children=children):
                return "OR(" + ",".join(render(child) for child in children) + ")"
            case Ite(condition=condition, when_true=when_true, when_false=when_false):
                return f"ITE({render(condition)},{render(when_true)},{render(when_false)})"
            case _:
                raise TypeError(f"unsupported expression type: {type(node)!r}")

    return render(normalized)
