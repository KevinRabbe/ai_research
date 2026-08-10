import pytest

from plural_cognition.boolean_world import (
    And,
    Ite,
    Not,
    Or,
    Var,
    evaluate,
    exact_equivalence,
    first_counterexample,
    semantic_distance,
    semantic_key,
    truth_table,
)


def test_evaluate_all_node_types() -> None:
    expr = Ite(Var("C"), And((Var("A"), Var("B"))), Or((Var("A"), Not(Var("B")))))
    assert evaluate(expr, {"A": True, "B": True, "C": True}) is True
    assert evaluate(expr, {"A": False, "B": True, "C": True}) is False
    assert evaluate(expr, {"A": False, "B": False, "C": False}) is True


def test_evaluate_fails_closed_on_missing_or_non_boolean_values() -> None:
    with pytest.raises(KeyError):
        evaluate(Var("A"), {})
    with pytest.raises(TypeError):
        evaluate(Var("A"), {"A": 1})


def test_truth_table_and_semantic_key_are_deterministic() -> None:
    expr = And((Var("A"), Var("B")))
    order, outputs = truth_table(expr)
    assert order == ("A", "B")
    assert outputs == (False, False, False, True)
    assert semantic_key(expr) == (("A", "B"), 0b1000)


def test_exact_equivalence_recognizes_demorgan() -> None:
    left = Not(And((Var("A"), Var("B"))))
    right = Or((Not(Var("A")), Not(Var("B"))))
    result = exact_equivalence(left, right)
    assert result.equivalent is True
    assert result.counterexample is None


def test_counterexample_and_semantic_distance() -> None:
    left = And((Var("A"), Var("B")))
    right = Or((Var("A"), Var("B")))
    assert first_counterexample(left, right) == {"A": False, "B": True}
    assert semantic_distance(left, right) == 2


def test_variable_order_must_cover_referenced_variables() -> None:
    with pytest.raises(ValueError):
        truth_table(Var("A"), ("B",))
