import pytest

from plural_cognition.boolean_world import And, Const, Ite, Not, Or, Var, depth, node_count, variables


def test_ast_is_immutable_and_validated() -> None:
    with pytest.raises(ValueError):
        Var("")
    with pytest.raises(ValueError):
        And(())
    with pytest.raises(ValueError):
        Or(())

    expr = Ite(Var("C"), And((Var("A"), Var("B"))), Not(Var("D")))
    assert variables(expr) == ("A", "B", "C", "D")
    assert node_count(expr) == 7
    assert depth(expr) == 3


def test_constants_have_no_variables() -> None:
    assert variables(Const(True)) == ()
