import pytest

from plural_cognition.boolean_world import (
    And,
    CanonicalParseError,
    Const,
    Ite,
    Not,
    Or,
    Var,
    canonical_text,
    parse_canonical_text,
)


def test_canonical_parser_round_trips_all_expression_forms() -> None:
    expressions = (
        Const(True),
        Const(False),
        Var("A"),
        Not(Var("A")),
        And((Var("A"), Var("B"))),
        Or((Var("A"), Not(Var("B")))),
        Ite(Var("A"), Var("B"), Not(Var("C"))),
    )

    for expression in expressions:
        text = canonical_text(expression)
        assert parse_canonical_text(text) == parse_canonical_text(canonical_text(expression))
        assert canonical_text(parse_canonical_text(text)) == text


def test_canonical_parser_rejects_noncanonical_equivalents() -> None:
    for text in (
        "AND(B,A)",
        "AND(A,A)",
        "AND(A)",
        "NOT(NOT(A))",
        "ITE(TRUE,A,B)",
        " OR(A,B)",
        "OR(A,B) ",
    ):
        with pytest.raises(CanonicalParseError):
            parse_canonical_text(text)


def test_canonical_parser_rejects_malformed_or_trailing_input() -> None:
    for text in (
        "",
        "AND()",
        "AND(A,)",
        "NOT(A",
        "ITE(A,B)",
        "A,B",
        "A)junk",
        "A B",
    ):
        with pytest.raises(CanonicalParseError):
            parse_canonical_text(text)


def test_canonical_parser_enforces_task_variables_and_resource_limits() -> None:
    with pytest.raises(CanonicalParseError, match="outside task"):
        parse_canonical_text("AND(A,B)", allowed_variables=("A",))
    with pytest.raises(CanonicalParseError, match="node limit"):
        parse_canonical_text("AND(A,B)", max_nodes=2)
    with pytest.raises(CanonicalParseError, match="depth limit"):
        parse_canonical_text("NOT(A)", max_depth=1)
    with pytest.raises(CanonicalParseError, match="length limit"):
        parse_canonical_text("A", max_length=0)


def test_canonical_text_rejects_reserved_or_ambiguous_variable_names() -> None:
    for name in ("TRUE", "FALSE", "AND", "A,B", "A B", "1A"):
        with pytest.raises(ValueError):
            canonical_text(Var(name))
