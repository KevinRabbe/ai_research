"""Deterministic model-scale selection from the six frozen screening runs."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Sequence

MODEL_ORDER = ("PC-4M", "PC-10M", "PC-18M")


@dataclass(frozen=True, slots=True)
class ScreeningRunResult:
    model_name: str
    initialization_seed: int
    execution_sha256: str
    checkpoint_sha256: str
    validation_shard_manifest_sha256s: tuple[str, ...]
    parse_rate: float
    exact_accuracy: float
    visible_consistency_rate: float
    mean_semantic_accuracy: float

    def __post_init__(self) -> None:
        if self.model_name not in MODEL_ORDER:
            raise ValueError(f"unknown screening model: {self.model_name!r}")
        if type(self.initialization_seed) is not int:
            raise TypeError("initialization_seed must be int")
        for name in ("execution_sha256", "checkpoint_sha256"):
            value = getattr(self, name)
            if len(value) != 64:
                raise ValueError(f"{name} must contain 64 hexadecimal characters")
            try:
                int(value, 16)
            except ValueError as exc:
                raise ValueError(f"{name} must be hexadecimal") from exc
        if not self.validation_shard_manifest_sha256s:
            raise ValueError("screening result requires validation shard identities")
        for value in self.validation_shard_manifest_sha256s:
            if len(value) != 64:
                raise ValueError("validation shard identity must be a SHA-256")
            try:
                int(value, 16)
            except ValueError as exc:
                raise ValueError("validation shard identity must be hexadecimal") from exc
        for name in (
            "parse_rate",
            "exact_accuracy",
            "visible_consistency_rate",
            "mean_semantic_accuracy",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class ScaleSummary:
    model_name: str
    seeds: tuple[int, ...]
    mean_parse_rate: float
    minimum_parse_rate: float
    mean_exact_accuracy: float
    minimum_exact_accuracy: float
    maximum_exact_accuracy: float
    mean_visible_consistency_rate: float
    mean_semantic_accuracy: float
    qualifies: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScaleSelectionDecision:
    selected_model: str | None
    summaries: tuple[ScaleSummary, ...]
    status: str
    reasons: tuple[str, ...]

    @property
    def selected(self) -> bool:
        return self.selected_model is not None


def select_screening_scale(
    results: Sequence[ScreeningRunResult],
    *,
    expected_seeds: tuple[int, ...] = (101, 102),
    minimum_parse_rate: float = 0.95,
    minimum_exact_accuracy: float = 0.20,
    maximum_exact_accuracy: float = 0.70,
) -> ScaleSelectionDecision:
    """Select the smallest stable model in the predeclared capability band."""

    if len(expected_seeds) < 2 or len(expected_seeds) != len(set(expected_seeds)):
        raise ValueError("expected_seeds must contain at least two unique seeds")
    if not 0.0 <= minimum_parse_rate <= 1.0:
        raise ValueError("minimum_parse_rate must be in [0, 1]")
    if not 0.0 <= minimum_exact_accuracy < maximum_exact_accuracy <= 1.0:
        raise ValueError("exact-accuracy band is invalid")
    expected_count = len(MODEL_ORDER) * len(expected_seeds)
    if len(results) != expected_count:
        raise ValueError(
            f"screening selection requires {expected_count} runs, received {len(results)}"
        )
    identities = {(item.model_name, item.initialization_seed) for item in results}
    expected_identities = {
        (model, seed) for model in MODEL_ORDER for seed in expected_seeds
    }
    if identities != expected_identities:
        missing = expected_identities.difference(identities)
        extra = identities.difference(expected_identities)
        raise ValueError(
            f"screening run matrix mismatch: missing={sorted(missing)!r}, extra={sorted(extra)!r}"
        )
    if len(identities) != len(results):
        raise ValueError("screening results contain duplicate model/seed runs")
    shard_sets = {item.validation_shard_manifest_sha256s for item in results}
    if len(shard_sets) != 1:
        raise ValueError("screening runs used different validation shards")

    summaries: list[ScaleSummary] = []
    for model_name in MODEL_ORDER:
        model_results = tuple(
            sorted(
                (item for item in results if item.model_name == model_name),
                key=lambda item: item.initialization_seed,
            )
        )
        parse_rates = tuple(item.parse_rate for item in model_results)
        exact = tuple(item.exact_accuracy for item in model_results)
        reasons: list[str] = []
        if min(parse_rates) < minimum_parse_rate:
            reasons.append(
                f"minimum parse rate {min(parse_rates):.4f} is below {minimum_parse_rate:.4f}"
            )
        exact_mean = mean(exact)
        if exact_mean < minimum_exact_accuracy:
            reasons.append(
                f"mean exact accuracy {exact_mean:.4f} is below {minimum_exact_accuracy:.4f}"
            )
        if exact_mean > maximum_exact_accuracy:
            reasons.append(
                f"mean exact accuracy {exact_mean:.4f} is above {maximum_exact_accuracy:.4f}"
            )
        summaries.append(
            ScaleSummary(
                model_name,
                tuple(item.initialization_seed for item in model_results),
                mean(parse_rates),
                min(parse_rates),
                exact_mean,
                min(exact),
                max(exact),
                mean(item.visible_consistency_rate for item in model_results),
                mean(item.mean_semantic_accuracy for item in model_results),
                not reasons,
                tuple(reasons),
            )
        )

    selected = next(
        (summary.model_name for summary in summaries if summary.qualifies),
        None,
    )
    if selected is not None:
        return ScaleSelectionDecision(
            selected,
            tuple(summaries),
            "selected",
            (
                f"selected the smallest model satisfying parse and capability-band gates: {selected}",
            ),
        )

    exact_means = tuple(summary.mean_exact_accuracy for summary in summaries)
    if max(exact_means) < minimum_exact_accuracy:
        status = "all-too-weak"
        reasons = (
            "all three scales are below the minimum exact-accuracy boundary; diagnose representation, supervision, curriculum, or task difficulty before scaling further",
        )
    elif min(exact_means) > maximum_exact_accuracy:
        status = "task-too-easy"
        reasons = (
            "even the smallest scale is above the maximum exact-accuracy boundary; make the task harder before testing synthesis",
        )
    else:
        status = "no-stable-band-model"
        reasons = (
            "no scale satisfies the frozen parse and mean exact-accuracy boundaries; inspect seed instability and learning curves rather than choosing post hoc",
        )
    return ScaleSelectionDecision(None, tuple(summaries), status, reasons)
