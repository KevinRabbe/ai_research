import pytest

from plural_cognition.population import (
    exact_shapley_values,
    evaluate_all_coalitions,
    leave_one_out_contributions,
)


def test_four_member_population_evaluates_exactly_sixteen_coalitions() -> None:
    evaluation = evaluate_all_coalitions(
        ("A", "B", "C", "D"), lambda coalition: float(len(coalition))
    )

    assert len(evaluation.values) == 16
    assert evaluation.empty_value == 0.0
    assert evaluation.full_value == 4.0


def test_exact_shapley_recovers_additive_member_values() -> None:
    weights = {"A": 1.0, "B": 2.0, "C": -0.5, "D": 0.25}
    evaluation = evaluate_all_coalitions(
        weights,
        lambda coalition: sum(weights[member] for member in coalition),
    )

    shapley = exact_shapley_values(evaluation)

    assert shapley == pytest.approx(weights)
    assert sum(shapley.values()) == pytest.approx(
        evaluation.full_value - evaluation.empty_value
    )


def test_shapley_splits_pure_synergy_equally() -> None:
    evaluation = evaluate_all_coalitions(
        ("A", "B"),
        lambda coalition: 1.0 if {"A", "B"}.issubset(coalition) else 0.0,
    )

    shapley = exact_shapley_values(evaluation)
    leave_one_out = leave_one_out_contributions(evaluation)

    assert shapley == pytest.approx({"A": 0.5, "B": 0.5})
    assert leave_one_out == pytest.approx({"A": 1.0, "B": 1.0})


def test_shapley_splits_redundant_capability_and_loo_detects_no_necessity() -> None:
    evaluation = evaluate_all_coalitions(
        ("A", "B"),
        lambda coalition: 1.0 if coalition else 0.0,
    )

    shapley = exact_shapley_values(evaluation)
    leave_one_out = leave_one_out_contributions(evaluation)

    assert shapley == pytest.approx({"A": 0.5, "B": 0.5})
    assert leave_one_out == pytest.approx({"A": 0.0, "B": 0.0})


def test_exact_coalition_evaluation_rejects_invalid_contracts() -> None:
    with pytest.raises(ValueError):
        evaluate_all_coalitions((), lambda coalition: 0.0)
    with pytest.raises(ValueError):
        evaluate_all_coalitions(("A", "A"), lambda coalition: 0.0)
    with pytest.raises(ValueError):
        evaluate_all_coalitions(("A",), lambda coalition: float("nan"))
