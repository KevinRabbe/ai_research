import pytest

from plural_cognition.condition_comparison import (
    ConditionComparisonError,
    ConditionMetrics,
    compare_population_conditions,
)


def _metrics(
    population_type: str,
    accuracies: tuple[float, ...],
    gains: tuple[float, ...],
    *,
    qualified: bool,
    coverage: float = 1.0,
) -> ConditionMetrics:
    return ConditionMetrics(
        population_type,
        len(accuracies),
        coverage,
        sum(accuracies) / len(accuracies),
        sum(gains) / len(gains),
        qualified,
        accuracies,
        gains,
        ("a" * 64,),
    )


def test_different_weight_condition_passes_paired_control_gate() -> None:
    primary = _metrics(
        "different-checkpoint-greedy",
        (1.0, 0.9, 1.0, 0.8),
        (0.25, 0.20, 0.25, 0.15),
        qualified=True,
    )
    control = _metrics(
        "same-checkpoint-sampled",
        (0.6, 0.5, 0.7, 0.4),
        (0.05, 0.00, 0.10, 0.00),
        qualified=False,
    )

    comparison = compare_population_conditions(
        primary,
        control,
        bootstrap_resamples=500,
        bootstrap_seed=7,
    )

    assert comparison.passed is True
    assert comparison.paired_accuracy_advantage > 0
    assert comparison.paired_accuracy_advantage_ci.lower > 0
    assert comparison.paired_gain_advantage > 0
    assert comparison.paired_gain_advantage_ci.lower > 0


def test_gate_fails_when_primary_advantage_is_not_paired_positive() -> None:
    primary = _metrics(
        "different-checkpoint-greedy",
        (0.7, 0.5, 0.7, 0.5),
        (0.10, 0.00, 0.10, 0.00),
        qualified=True,
    )
    control = _metrics(
        "same-checkpoint-sampled",
        (0.6, 0.6, 0.6, 0.6),
        (0.05, 0.05, 0.05, 0.05),
        qualified=False,
    )

    comparison = compare_population_conditions(
        primary,
        control,
        bootstrap_resamples=500,
        bootstrap_seed=7,
    )

    assert comparison.passed is False
    assert any("accuracy advantage" in reason for reason in comparison.reasons)
    assert any("gain advantage" in reason for reason in comparison.reasons)


def test_condition_types_and_validation_rows_must_match() -> None:
    primary = _metrics(
        "same-checkpoint-sampled",
        (1.0, 1.0),
        (0.2, 0.2),
        qualified=True,
    )
    control = _metrics(
        "same-checkpoint-sampled",
        (0.5, 0.5),
        (0.0, 0.0),
        qualified=False,
    )
    with pytest.raises(ConditionComparisonError, match="primary condition"):
        compare_population_conditions(primary, control, bootstrap_resamples=200)

    proper_primary = _metrics(
        "different-checkpoint-greedy",
        (1.0, 1.0),
        (0.2, 0.2),
        qualified=True,
    )
    changed_control = ConditionMetrics(
        control.population_type,
        control.case_count,
        control.analysis_coverage,
        control.mean_synthesis_accuracy,
        control.mean_synthesis_gain,
        control.internal_qualification_passed,
        control.full_synthesis_semantic_accuracies,
        control.synthesis_gains,
        ("9" * 64,),
    )
    with pytest.raises(ConditionComparisonError, match="different validation shards"):
        compare_population_conditions(
            proper_primary,
            changed_control,
            bootstrap_resamples=200,
        )
