"""Immutable abstract syntax tree for exact Boolean mechanisms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True, slots=True)
class Const:
    value: bool


@dataclass(frozen=True, slots=True)
class Var:
    name: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("variable name must not be empty")


@dataclass(frozen=True, slots=True)
class Not:
    child: "Expr"


@dataclass(frozen=True, slots=True)
class And:
    children: tuple["Expr", ...]

    def __post_init__(self) -> None:
        if not self.children:
            raise ValueError("And requires at least one child")


@dataclass(frozen=True, slots=True)
class Or:
    children: tuple["Expr", ...]

    def __post_init__(self) -> None:
        if not self.children:
            raise ValueError("Or requires at least one child")


@dataclass(frozen=True, slots=True)
class Ite:
    condition: "Expr"
    when_true: "Expr"
    when_false: "Expr"


Expr: TypeAlias = Const | Var | Not | And | Or | Ite


def variables(expr: Expr) -> tuple[str, ...]:
    """Return all syntactically referenced variables in stable sorted order."""

    found: set[str] = set()

    def visit(node: Expr) -> None:
        match node:
            case Const():
                return
            case Var(name=name):
                found.add(name)
            case Not(child=child):
                visit(child)
            case And(children=children) | Or(children=children):
                for child in children:
                    visit(child)
            case Ite(condition=condition, when_true=when_true, when_false=when_false):
                visit(condition)
                visit(when_true)
                visit(when_false)
            case _:
                raise TypeError(f"unsupported expression type: {type(node)!r}")

    visit(expr)
    return tuple(sorted(found))


def node_count(expr: Expr) -> int:
    """Count all AST nodes."""

    match expr:
        case Const() | Var():
            return 1
        case Not(child=child):
            return 1 + node_count(child)
        case And(children=children) | Or(children=children):
            return 1 + sum(node_count(child) for child in children)
        case Ite(condition=condition, when_true=when_true, when_false=when_false):
            return 1 + node_count(condition) + node_count(when_true) + node_count(when_false)
        case _:
            raise TypeError(f"unsupported expression type: {type(expr)!r}")


def depth(expr: Expr) -> int:
    """Return AST depth, counting a leaf as depth 1."""

    match expr:
        case Const() | Var():
            return 1
        case Not(child=child):
            return 1 + depth(child)
        case And(children=children) | Or(children=children):
            return 1 + max(depth(child) for child in children)
        case Ite(condition=condition, when_true=when_true, when_false=when_false):
            return 1 + max(depth(condition), depth(when_true), depth(when_false))
        case _:
            raise TypeError(f"unsupported expression type: {type(expr)!r}")
