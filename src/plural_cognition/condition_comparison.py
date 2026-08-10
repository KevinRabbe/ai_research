"""Paired comparison between primary and same-weight population conditions."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any

from .population.statistics import ConfidenceInterval, paired_bootstrap_mean_interval


class ConditionComparisonError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ConditionMetrics:
    population_type: str
    case_count: int
    analysis_coverage: float
    mean_synthesis_accuracy: float
    mean_synthesis_gain: float
    internal_qualification_passed: bool
    full_synthesis_semantic_accuracies: tuple[float, ...]
    synthesis_gains: tuple[float, ...]
    validation_shard_manifest_sha256s: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConditionComparison:
    primary: ConditionMetrics
    same_weight: ConditionMetrics
    paired_accuracy_advantage: float
    paired_accuracy_advantage_ci: ConfidenceInterval
    paired_gain_advantage: float
    paired_gain_advantage_ci: ConfidenceInterval
    passed: bool
    reasons: tuple[str, ...]


def condition_metrics_from_payload(payload: Any) -> ConditionMetrics:
    if not isinstance(payload, dict):
        raise ConditionComparisonError("population evaluation must be an object")
    required = {
        "schema",
        "population_type",
        "members",
        "validation_shard_manifest_sha256s",
        "case_count",
        "summary",
        "qualification",
        "tasks",
    }
    if set(payload) != required:
        raise ConditionComparisonError("population evaluation has wrong fields")
    if payload["schema"] != "plural-cognition-population-evaluation-v1":
        raise ConditionComparisonError("unsupported population evaluation schema")
    summary = payload["summary"]
    qualification = payload["qualification"]
    tasks = payload["tasks"]
    if not isinstance(summary, dict):
        raise ConditionComparisonError("population evaluation has no analyzable summary")
    if not isinstance(qualification, dict) or type(qualification.get("passed")) is not bool:
        raise ConditionComparisonError("population qualification is invalid")
    if not isinstance(tasks, list) or payload["case_count"] != len(tasks):
        raise ConditionComparisonError("population task count is inconsistent")
    accuracies: list[float] = []
    gains: list[float] = []
    for expected_index, task in enumerate(tasks):
        if not isinstance(task, dict) or task.get("case_index") != expected_index:
            raise ConditionComparisonError("population task identity is inconsistent")
        accuracy = task.get("full_synthesis_semantic_accuracy")
        gain = task.get("synthesis_gain")
        if type(accuracy) not in (int, float) or type(gain) not in (int, float):
            raise ConditionComparisonError(
                "condition comparison requires analyzable synthesis scores for every task"
            )
        accuracies.append(float(accuracy))
        gains.append(float(gain))
    shard_values = payload["validation_shard_manifest_sha256s"]
    if not isinstance(shard_values, list) or not shard_values:
        raise ConditionComparisonError("population evaluation has no validation shard identity")
    return ConditionMetrics(
        payload["population_type"],
        payload["case_count"],
        float(summary["analysis_coverage"]),
        float(summary["mean_synthesis_accuracy"]),
        float(summary["mean_synthesis_gain"]),
        qualification["passed"],
        tuple(accuracies),
        tuple(gains),
        tuple(shard_values),
    )


def compare_population_conditions(
    primary: ConditionMetrics,
    same_weight: ConditionMetrics,
    *,
    minimum_control_coverage: float = 0.95,
    bootstrap_resamples: int = 10_000,
    bootstrap_seed: int = 20260806,
) -> ConditionComparison:
    """Apply the primary different-weight versus same-weight paired gate."""

    if primary.population_type != "different-checkpoint-greedy":
        raise ConditionComparisonError(
            "primary condition must be different-checkpoint-greedy"
        )
    if same_weight.population_type != "same-checkpoint-sampled":
        raise ConditionComparisonError(
            "control condition must be same-checkpoint-sampled"
        )
    if primary.case_count != same_weight.case_count:
        raise ConditionComparisonError("condition case counts differ")
    if (
        primary.validation_shard_manifest_sha256s
        != same_weight.validation_shard_manifest_sha256s
    ):
        raise ConditionComparisonError("conditions used different validation shards")
    accuracy_differences = tuple(
        primary_value - control_value
        for primary_value, control_value in zip(
            primary.full_synthesis_semantic_accuracies,
            same_weight.full_synthesis_semantic_accuracies,
            strict=True,
        )
    )
    gain_differences = tuple(
        primary_value - control_value
        for primary_value, control_value in zip(
            primary.synthesis_gains,
            same_weight.synthesis_gains,
            strict=True,
        )
    )
    accuracy_ci = paired_bootstrap_mean_interval(
        accuracy_differences,
        resamples=bootstrap_resamples,
        seed=bootstrap_seed,
    )
    gain_ci = paired_bootstrap_mean_interval(
        gain_differences,
        resamples=bootstrap_resamples,
        seed=bootstrap_seed ^ 0x51A7E,
    )
    reasons: list[str] = []
    if not primary.internal_qualification_passed:
        reasons.append("primary population failed its internal synthesis qualification")
    if same_weight.analysis_coverage < minimum_control_coverage:
        reasons.append(
            f"same-weight control coverage {same_weight.analysis_coverage:.4f} is below {minimum_control_coverage:.4f}"
        )
    if accuracy_ci.lower <= 0.0:
        reasons.append(
            "paired different-weight synthesis-accuracy advantage is not above zero"
        )
    if gain_ci.lower <= 0.0:
        reasons.append(
            "paired different-weight synthesis-gain advantage is not above zero"
        )
    return ConditionComparison(
        primary,
        same_weight,
        mean(accuracy_differences),
        accuracy_ci,
        mean(gain_differences),
        gain_ci,
        not reasons,
        tuple(reasons),
    )


def compare_population_payloads(
    primary_payload: Any,
    same_weight_payload: Any,
    *,
    minimum_control_coverage: float = 0.95,
    bootstrap_resamples: int = 10_000,
    bootstrap_seed: int = 20260806,
) -> ConditionComparison:
    return compare_population_conditions(
        condition_metrics_from_payload(primary_payload),
        condition_metrics_from_payload(same_weight_payload),
        minimum_control_coverage=minimum_control_coverage,
        bootstrap_resamples=bootstrap_resamples,
        bootstrap_seed=bootstrap_seed,
    )


def condition_comparison_payload(comparison: ConditionComparison) -> dict:
    def interval_payload(interval: ConfidenceInterval) -> dict:
        return {
            "lower": interval.lower,
            "estimate": interval.estimate,
            "upper": interval.upper,
            "confidence": interval.confidence,
        }

    return {
        "schema": "plural-cognition-condition-comparison-v1",
        "passed": comparison.passed,
        "reasons": list(comparison.reasons),
        "primary_population_type": comparison.primary.population_type,
        "control_population_type": comparison.same_weight.population_type,
        "case_count": comparison.primary.case_count,
        "validation_shard_manifest_sha256s": list(
            comparison.primary.validation_shard_manifest_sha256s
        ),
        "primary_mean_synthesis_accuracy": comparison.primary.mean_synthesis_accuracy,
        "control_mean_synthesis_accuracy": comparison.same_weight.mean_synthesis_accuracy,
        "paired_accuracy_advantage": comparison.paired_accuracy_advantage,
        "paired_accuracy_advantage_ci": interval_payload(
            comparison.paired_accuracy_advantage_ci
        ),
        "primary_mean_synthesis_gain": comparison.primary.mean_synthesis_gain,
        "control_mean_synthesis_gain": comparison.same_weight.mean_synthesis_gain,
        "paired_gain_advantage": comparison.paired_gain_advantage,
        "paired_gain_advantage_ci": interval_payload(
            comparison.paired_gain_advantage_ci
        ),
    }
