"""Deterministic structural normalization for Boolean mechanism ASTs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Collection

from .ast import And, Const, Expr, Ite, Not, Or, Var

_CANONICAL_RESERVED = frozenset({"TRUE", "FALSE", "NOT", "AND", "OR", "ITE"})


class CanonicalParseError(ValueError):
    """Raised when canonical Boolean text violates the exact grammar."""


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


def _validate_canonical_variable_name(name: str) -> None:
    if not name:
        raise ValueError("canonical variable name must not be empty")
    if name in _CANONICAL_RESERVED:
        raise ValueError(f"canonical variable name is reserved: {name!r}")
    if not (name[0].isascii() and (name[0].isalpha() or name[0] == "_")):
        raise ValueError(f"invalid canonical variable name: {name!r}")
    if any(
        not (character.isascii() and (character.isalnum() or character == "_"))
        for character in name[1:]
    ):
        raise ValueError(f"invalid canonical variable name: {name!r}")


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
                _validate_canonical_variable_name(name)
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


@dataclass(slots=True)
class _CanonicalReader:
    text: str
    max_nodes: int
    max_depth: int
    position: int = 0
    nodes: int = 0

    def _consume(self, literal: str) -> bool:
        if self.text.startswith(literal, self.position):
            self.position += len(literal)
            return True
        return False

    def _expect(self, literal: str) -> None:
        if not self._consume(literal):
            found = self.text[self.position : self.position + max(1, len(literal))]
            raise CanonicalParseError(
                f"expected {literal!r} at position {self.position}, found {found!r}"
            )

    def _identifier(self) -> str:
        start = self.position
        if start >= len(self.text):
            raise CanonicalParseError("unexpected end while reading variable")
        first = self.text[start]
        if not (first.isascii() and (first.isalpha() or first == "_")):
            raise CanonicalParseError(
                f"invalid variable start {first!r} at position {start}"
            )
        self.position += 1
        while self.position < len(self.text):
            character = self.text[self.position]
            if not (
                character.isascii() and (character.isalnum() or character == "_")
            ):
                break
            self.position += 1
        name = self.text[start : self.position]
        try:
            _validate_canonical_variable_name(name)
        except ValueError as exc:
            raise CanonicalParseError(str(exc)) from exc
        return name

    def parse(self, depth: int = 1) -> Expr:
        self.nodes += 1
        if self.nodes > self.max_nodes:
            raise CanonicalParseError("canonical expression exceeds node limit")
        if depth > self.max_depth:
            raise CanonicalParseError("canonical expression exceeds depth limit")

        if self._consume("TRUE"):
            return Const(True)
        if self._consume("FALSE"):
            return Const(False)
        if self._consume("NOT("):
            child = self.parse(depth + 1)
            self._expect(")")
            return Not(child)
        if self._consume("AND("):
            children = self._parse_list(depth + 1)
            return And(children)
        if self._consume("OR("):
            children = self._parse_list(depth + 1)
            return Or(children)
        if self._consume("ITE("):
            condition = self.parse(depth + 1)
            self._expect(",")
            when_true = self.parse(depth + 1)
            self._expect(",")
            when_false = self.parse(depth + 1)
            self._expect(")")
            return Ite(condition, when_true, when_false)
        return Var(self._identifier())

    def _parse_list(self, depth: int) -> tuple[Expr, ...]:
        if self.position >= len(self.text) or self.text[self.position] == ")":
            raise CanonicalParseError("AND/OR requires at least one child")
        children = [self.parse(depth)]
        while self._consume(","):
            children.append(self.parse(depth))
        self._expect(")")
        return tuple(children)


def parse_canonical_text(
    text: str,
    *,
    allowed_variables: Collection[str] | None = None,
    max_nodes: int = 128,
    max_depth: int = 16,
    max_length: int = 4096,
) -> Expr:
    """Parse canonical text and reject every non-canonical equivalent spelling.

    The round-trip check enforces normalization, stable child ordering, exact
    punctuation, and the absence of trailing data.
    """

    if type(text) is not str:
        raise TypeError("canonical expression must be a plain string")
    if not text:
        raise CanonicalParseError("canonical expression must not be empty")
    if len(text) > max_length:
        raise CanonicalParseError("canonical expression exceeds length limit")
    if max_nodes < 1 or max_depth < 1:
        raise ValueError("parser limits must be positive")

    reader = _CanonicalReader(text, max_nodes, max_depth)
    raw = reader.parse()
    if reader.position != len(text):
        raise CanonicalParseError(
            f"trailing data at position {reader.position}: {text[reader.position:]!r}"
        )

    normalized = normalize(raw)
    if allowed_variables is not None:
        allowed = set(allowed_variables)
        referenced: set[str] = set()

        def collect(node: Expr) -> None:
            match node:
                case Var(name=name):
                    referenced.add(name)
                case Not(child=child):
                    collect(child)
                case And(children=children) | Or(children=children):
                    for child in children:
                        collect(child)
                case Ite(condition=condition, when_true=when_true, when_false=when_false):
                    collect(condition)
                    collect(when_true)
                    collect(when_false)
                case Const():
                    return

        collect(normalized)
        unknown = referenced.difference(allowed)
        if unknown:
            raise CanonicalParseError(
                f"canonical expression uses variables outside task: {sorted(unknown)!r}"
            )

    if canonical_text(normalized) != text:
        raise CanonicalParseError("expression is valid but not in canonical form")
    return normalized
