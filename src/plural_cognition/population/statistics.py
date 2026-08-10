"""Deterministic aggregate statistics for the Version 1 population experiment."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from statistics import mean
from typing import Sequence

from .ablation import AblationMode
from .experiment import PopulationTaskReport


@dataclass(frozen=True, slots=True)
class ConfidenceInterval:
    lower: float
    estimate: float
    upper: float
    confidence: float

    def __post_init__(self) -> None:
        if not 0.0 < self.confidence < 1.0:
            raise ValueError("confidence must be in (0, 1)")
        if not self.lower <= self.estimate <= self.upper:
            raise ValueError("confidence interval ordering is invalid")


@dataclass(frozen=True, slots=True)
class PopulationExperimentSummary:
    task_count: int
    analyzable_task_count: int
    analysis_coverage: float
    mean_best_individual_accuracy: float
    mean_synthesis_accuracy: float
    mean_synthesis_gain: float
    synthesis_gain_ci: ConfidenceInterval
    exact_synthesis_rate: float
    novel_composition_rate: float
    multi_source_rate: float
    strong_synthesis_event_count: int
    strong_synthesis_event_rate: float
    mean_ablation_scores: tuple[tuple[AblationMode, float], ...]

    def ablation_score(self, mode: AblationMode) -> float:
        for candidate_mode, score in self.mean_ablation_scores:
            if candidate_mode is mode:
                return score
        raise KeyError(mode)


@dataclass(frozen=True, slots=True)
class QualificationDecision:
    passed: bool
    reasons: tuple[str, ...]


def paired_bootstrap_mean_interval(
    values: Sequence[float],
    *,
    confidence: float = 0.95,
    resamples: int = 10_000,
    seed: int = 20260806,
) -> ConfidenceInterval:
    """Return a deterministic percentile bootstrap interval for a paired mean."""

    if not values:
        raise ValueError("bootstrap requires at least one paired value")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be in (0, 1)")
    if resamples < 100:
        raise ValueError("bootstrap requires at least 100 resamples")
    numeric = tuple(float(value) for value in values)
    estimate = mean(numeric)
    rng = Random(seed)
    count = len(numeric)
    samples = sorted(
        mean(numeric[rng.randrange(count)] for _ in range(count))
        for _ in range(resamples)
    )
    alpha = 1.0 - confidence
    lower_index = max(0, int((alpha / 2.0) * resamples))
    upper_index = min(
        resamples - 1,
        int((1.0 - alpha / 2.0) * resamples) - 1,
    )
    lower = min(samples[lower_index], estimate)
    upper = max(samples[upper_index], estimate)
    return ConfidenceInterval(lower, estimate, upper, confidence)


def summarize_population_experiment(
    reports: Sequence[PopulationTaskReport],
    *,
    bootstrap_resamples: int = 10_000,
    bootstrap_seed: int = 20260806,
) -> PopulationExperimentSummary:
    if not reports:
        raise ValueError("at least one population task report is required")
    analyzable = tuple(report for report in reports if report.analysis_available)
    if not analyzable:
        raise ValueError("no population tasks are analyzable")

    gains = tuple(report.synthesis_gain for report in analyzable)
    synthesis_accuracies = tuple(
        report.full_synthesis_hidden.semantic_accuracy
        for report in analyzable
        if report.full_synthesis_hidden is not None
    )
    if len(synthesis_accuracies) != len(analyzable):
        raise ValueError("analyzable report is missing hidden synthesis evaluation")

    ablation_scores: list[tuple[AblationMode, float]] = []
    for mode in AblationMode:
        values = []
        for report in analyzable:
            if report.ablations is None:
                raise ValueError("analyzable report is missing ablation outcomes")
            outcome = next(item for item in report.ablations if item.mode is mode)
            if outcome.external_score is None:
                raise ValueError("ablation outcome is missing external score")
            values.append(outcome.external_score)
        ablation_scores.append((mode, mean(values)))

    task_count = len(reports)
    analyzable_count = len(analyzable)
    strong_count = sum(report.strong_synthesis_event for report in analyzable)
    return PopulationExperimentSummary(
        task_count,
        analyzable_count,
        analyzable_count / task_count,
        mean(report.best_individual_semantic_accuracy for report in analyzable),
        mean(synthesis_accuracies),
        mean(gains),
        paired_bootstrap_mean_interval(
            gains,
            resamples=bootstrap_resamples,
            seed=bootstrap_seed,
        ),
        mean(float(report.full_synthesis_exact) for report in analyzable),
        mean(float(report.novel_semantic_composition) for report in analyzable),
        mean(float(report.multi_source_provenance) for report in analyzable),
        strong_count,
        strong_count / analyzable_count,
        tuple(ablation_scores),
    )


def qualify_population_signal(
    summary: PopulationExperimentSummary,
    *,
    minimum_analysis_coverage: float = 0.95,
    minimum_mean_gain: float = 0.05,
    minimum_strong_events: int = 1,
) -> QualificationDecision:
    """Apply the provisional V1 signal gate without changing its measurements."""

    reasons: list[str] = []
    if summary.analysis_coverage < minimum_analysis_coverage:
        reasons.append(
            f"analysis coverage {summary.analysis_coverage:.4f} is below {minimum_analysis_coverage:.4f}"
        )
    if summary.mean_synthesis_gain < minimum_mean_gain:
        reasons.append(
            f"mean synthesis gain {summary.mean_synthesis_gain:.4f} is below {minimum_mean_gain:.4f}"
        )
    if summary.synthesis_gain_ci.lower <= 0.0:
        reasons.append("paired bootstrap lower bound is not above zero")
    if summary.strong_synthesis_event_count < minimum_strong_events:
        reasons.append(
            f"strong synthesis events {summary.strong_synthesis_event_count} are below {minimum_strong_events}"
        )
    verified = summary.ablation_score(AblationMode.VERIFIED_SYNTHESIS)
    for control in (
        AblationMode.COMPLETE_SELECTION,
        AblationMode.VERIFIED_FRAGMENT_SELECTION,
    ):
        score = summary.ablation_score(control)
        if verified <= score:
            reasons.append(
                f"verified synthesis score {verified:.4f} does not exceed {control.value} score {score:.4f}"
            )
    return QualificationDecision(not reasons, tuple(reasons))
