import pytest

from plural_cognition.collective import (
    OutcomeTable,
    compare_stages,
    error_correlation_matrix,
    evaluate_four_mind_credit,
    pairwise_error_correlation,
    summarize_collective,
)


def table() -> OutcomeTable:
    return OutcomeTable(
        task_ids=("t1", "t2", "t3", "t4", "t5"),
        member_ids=("a", "b", "c", "d"),
        outcomes=(
            (True, True, False, False),
            (True, False, True, False),
            (False, True, False, False),
            (False, False, True, False),
            (False, False, False, False),
        ),
    )


def test_outcome_table_reports_capability_and_complementarity() -> None:
    outcomes = table()
    assert outcomes.member_scores() == {
        "a": pytest.approx(0.4),
        "b": pytest.approx(0.4),
        "c": pytest.approx(0.4),
        "d": pytest.approx(0.0),
    }
    assert outcomes.strongest_member_ids == ("a", "b", "c")
    assert outcomes.best_constituent_score == pytest.approx(0.4)
    assert outcomes.oracle_union_score == pytest.approx(0.8)
    assert outcomes.complementarity_headroom == pytest.approx(0.4)
    assert outcomes.unique_solve_counts() == {"a": 0, "b": 1, "c": 1, "d": 0}


def test_collective_summary_tracks_uplift_and_novel_collective_solves() -> None:
    summary = summarize_collective(
        table(),
        (True, True, True, True, True),
    )
    assert summary.best_constituent_score == pytest.approx(0.4)
    assert summary.oracle_union_score == pytest.approx(0.8)
    assert summary.complementarity_headroom == pytest.approx(0.4)
    assert summary.collective_score == pytest.approx(1.0)
    assert summary.plural_uplift == pytest.approx(0.6)
    assert summary.selection_headroom_utilization == pytest.approx(1.5)
    assert summary.novel_collective_solve_count == 1
    assert summary.novel_collective_solve_rate == pytest.approx(0.2)


def test_selection_headroom_utilization_is_none_without_headroom() -> None:
    outcomes = OutcomeTable(
        task_ids=("t1", "t2"),
        member_ids=("a", "b"),
        outcomes=((True, True), (False, False)),
    )
    summary = summarize_collective(outcomes, (True, False))
    assert summary.complementarity_headroom == 0.0
    assert summary.selection_headroom_utilization is None


def test_compare_stages_preserves_rescue_and_damage_separately() -> None:
    delta = compare_stages(
        ("t1", "t2", "t3", "t4"),
        (True, False, True, False),
        (True, True, False, False),
    )
    assert delta.before_score == pytest.approx(0.5)
    assert delta.after_score == pytest.approx(0.5)
    assert delta.rescue_count == 1
    assert delta.damage_count == 1
    assert delta.unchanged_pass_count == 1
    assert delta.unchanged_fail_count == 1
    assert delta.net_uplift == pytest.approx(0.0)


def test_pairwise_error_correlation_uses_binary_error_vectors() -> None:
    result = pairwise_error_correlation(
        (True, True, False, False),
        (True, False, True, False),
    )
    assert result.task_count == 4
    assert result.left_error_count == 2
    assert result.right_error_count == 2
    assert result.shared_error_count == 1
    assert result.correlation == pytest.approx(0.0)

    constant = pairwise_error_correlation(
        (True, True, True, True),
        (True, False, True, False),
    )
    assert constant.correlation is None


def test_error_correlation_matrix_is_symmetric() -> None:
    matrix = error_correlation_matrix(table())
    assert len(matrix) == 4
    for left in range(4):
        for right in range(4):
            assert matrix[left][right] == matrix[right][left]
    assert matrix[3][3] is None


def test_exact_four_mind_credit_reuses_all_sixteen_coalitions() -> None:
    weights = {"a": 0.1, "b": 0.2, "c": 0.3, "d": 0.4}
    credit = evaluate_four_mind_credit(
        ("a", "b", "c", "d"),
        lambda coalition: sum(weights[member] for member in coalition),
    )
    assert len(credit.evaluation.values) == 16
    for member, weight in weights.items():
        assert credit.shapley_values[member] == pytest.approx(weight)
        assert credit.leave_one_out[member] == pytest.approx(weight)

    with pytest.raises(ValueError, match="requires four minds"):
        evaluate_four_mind_credit(("a", "b"), lambda _: 0.0)


def test_outcome_table_rejects_non_boolean_and_wrong_geometry() -> None:
    with pytest.raises(TypeError, match="outcomes must be bool"):
        OutcomeTable(("t1",), ("a",), ((1,),))  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="row count"):
        OutcomeTable(("t1", "t2"), ("a",), ((True,),))

    with pytest.raises(ValueError, match="match member_ids"):
        OutcomeTable(("t1",), ("a", "b"), ((True,),))
