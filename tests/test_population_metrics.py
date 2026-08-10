import math

import pytest

from plural_cognition.boolean_world import And, Or, Var
from plural_cognition.population import (
    error_correlation_matrix,
    pairwise_error_correlation,
    semantic_distance_matrix,
)


def test_semantic_distance_matrix_is_exact_symmetric_and_normalized() -> None:
    a = Var("A")
    b = Var("B")
    either = Or((a, b))

    matrix = semantic_distance_matrix((a, b, either), ("A", "B"))

    assert matrix[0][0] == 0.0
    assert matrix[1][1] == 0.0
    assert matrix[2][2] == 0.0
    assert matrix[0][1] == matrix[1][0] == 0.5
    assert matrix[0][2] == matrix[2][0] == 0.25
    assert matrix[1][2] == matrix[2][1] == 0.25


def test_pairwise_error_correlation_uses_semantic_errors_not_tokens() -> None:
    a = Var("A")
    b = Var("B")
    target = And((a, b))

    result = pairwise_error_correlation(a, b, target, ("A", "B"))

    assert result.assignment_count == 4
    assert result.left_error_count == 1
    assert result.right_error_count == 1
    assert result.shared_error_count == 0
    assert result.correlation == pytest.approx(-1.0 / 3.0)


def test_error_correlation_is_undefined_for_constant_error_vector() -> None:
    a = Var("A")
    b = Var("B")
    target = And((a, b))

    result = pairwise_error_correlation(target, a, target, ("A", "B"))
    matrix = error_correlation_matrix((target, a, b), target, ("A", "B"))

    assert result.correlation is None
    assert matrix[0][0] is None
    assert matrix[0][1] is None
    assert matrix[1][0] is None
    assert matrix[1][1] == 1.0
    assert math.isclose(matrix[1][2], -1.0 / 3.0)


def test_population_metrics_reject_empty_or_duplicate_orders() -> None:
    with pytest.raises(ValueError):
        semantic_distance_matrix((), ("A",))
    with pytest.raises(ValueError):
        semantic_distance_matrix((Var("A"),), ())
    with pytest.raises(ValueError):
        semantic_distance_matrix((Var("A"),), ("A", "A"))
