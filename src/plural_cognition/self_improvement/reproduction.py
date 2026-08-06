"""Qualification across independent SI-V1 candidate-pool and task seeds."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from statistics import mean
from typing import Any, Sequence

from plural_cognition.population.statistics import (
    ConfidenceInterval,
    paired_bootstrap_mean_interval,
)

from .manifests import ExperimentSplit, SelfImprovementExperimentManifest


class ReproductionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ReproductionRun:
    experiment_sha256: str
    split_pool_sha256s: tuple[str, ...]
    passed_single_run_gate: bool
    hidden_semantic_gain: float
    hidden_ci_lower: float
    shift_semantic_gain: float
    hidden_task_differences: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.experiment_sha256) != 64:
            raise ValueError("experiment SHA must contain 64 characters")
        int(self.experiment_sha256, 16)
        if len(self.split_pool_sha256s) != len(ExperimentSplit):
            raise ValueError("run must bind every split pool")
        if not self.hidden_task_differences:
            raise ValueError("run must contain hidden task differences")


@dataclass(frozen=True, slots=True)
class ReproductionQualification:
    runs: tuple[ReproductionRun, ...]
    mean_hidden_gain: float
    run_mean_gain_ci: ConfidenceInterval
    pooled_task_gain: float
    pooled_task_gain_ci: ConfidenceInterval
    minimum_shift_gain: float
    passed: bool
    reasons: tuple[str, ...]

    SCHEMA = "plural-cognition-si-reproduction-qualification-v1"

    def canonical_payload(self) -> dict[str, object]:
        def interval_payload(interval: ConfidenceInterval) -> dict[str, float]:
            return {
                "lower": interval.lower,
                "estimate": interval.estimate,
                "upper": interval.upper,
                "confidence": interval.confidence,
            }

        return {
            "schema": self.SCHEMA,
            "run_count": len(self.runs),
            "runs": [
                {
                    "experiment_sha256": run.experiment_sha256,
                    "split_pool_sha256s": list(run.split_pool_sha256s),
                    "passed_single_run_gate": run.passed_single_run_gate,
                    "hidden_semantic_gain": run.hidden_semantic_gain,
                    "hidden_ci_lower": run.hidden_ci_lower,
                    "shift_semantic_gain": run.shift_semantic_gain,
                    "hidden_task_count": len(run.hidden_task_differences),
                }
                for run in self.runs
            ],
            "mean_hidden_gain": self.mean_hidden_gain,
            "run_mean_gain_ci": interval_payload(self.run_mean_gain_ci),
            "pooled_task_gain": self.pooled_task_gain,
            "pooled_task_gain_ci": interval_payload(self.pooled_task_gain_ci),
            "minimum_shift_gain": self.minimum_shift_gain,
            "passed": self.passed,
            "reasons": list(self.reasons),
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


def _number(value: Any, field: str) -> float:
    if type(value) not in (int, float):
        raise ReproductionError(f"{field} must be numeric")
    return float(value)


def _archive_cases(report: dict[str, Any], role: str) -> list[dict[str, Any]]:
    evaluations = report.get("evaluations")
    if not isinstance(evaluations, list):
        raise ReproductionError("hidden report evaluations must be a list")
    matches = [item for item in evaluations if item.get("role") == role]
    if len(matches) != 1:
        raise ReproductionError(f"hidden report has {len(matches)} {role} evaluations")
    hidden = matches[0].get("hidden")
    if not isinstance(hidden, dict) or not isinstance(hidden.get("cases"), list):
        raise ReproductionError(f"{role} hidden evaluation is invalid")
    return hidden["cases"]


def reproduction_run_from_payload(
    experiment: SelfImprovementExperimentManifest,
    hidden_report: Any,
) -> ReproductionRun:
    if not isinstance(hidden_report, dict):
        raise ReproductionError("hidden report must be an object")
    required = {
        "schema",
        "experiment_sha256",
        "search_phase_sha256",
        "finalist_manifest_sha256",
        "evaluations",
        "comparisons",
        "archive_parent_reversion",
        "passed_single_run_gate",
        "reasons",
    }
    if set(hidden_report) != required:
        raise ReproductionError("hidden report has wrong fields")
    if hidden_report["schema"] != "plural-cognition-si-hidden-opening-v1":
        raise ReproductionError("unsupported hidden report schema")
    if hidden_report["experiment_sha256"] != experiment.sha256:
        raise ReproductionError("hidden report belongs to a different experiment")
    if type(hidden_report["passed_single_run_gate"]) is not bool:
        raise ReproductionError("hidden report pass flag is invalid")

    comparisons = hidden_report["comparisons"]
    if not isinstance(comparisons, list):
        raise ReproductionError("hidden report comparisons must be a list")
    primary = [item for item in comparisons if item.get("role") == "archive-champion"]
    if len(primary) != 1:
        raise ReproductionError("hidden report requires one archive comparison")
    primary_item = primary[0]
    hidden_ci = primary_item.get("hidden_semantic_gain_ci")
    if not isinstance(hidden_ci, dict):
        raise ReproductionError("archive hidden interval is invalid")

    parent_cases = _archive_cases(hidden_report, "immutable-parent")
    archive_cases = _archive_cases(hidden_report, "archive-champion")
    if len(parent_cases) != len(archive_cases) or not parent_cases:
        raise ReproductionError("hidden finalist task counts differ")
    differences = []
    for expected_index, (parent, archive) in enumerate(
        zip(parent_cases, archive_cases, strict=True)
    ):
        if parent.get("case_index") != expected_index or archive.get("case_index") != expected_index:
            raise ReproductionError("hidden task identities are inconsistent")
        differences.append(
            _number(archive.get("semantic_accuracy"), "archive semantic accuracy")
            - _number(parent.get("semantic_accuracy"), "parent semantic accuracy")
        )

    split_hashes = tuple(
        experiment.split(split).candidate_pool_sha256
        for split in ExperimentSplit
    )
    return ReproductionRun(
        experiment.sha256,
        split_hashes,
        hidden_report["passed_single_run_gate"],
        _number(primary_item.get("hidden_semantic_gain"), "hidden semantic gain"),
        _number(hidden_ci.get("lower"), "hidden interval lower"),
        _number(primary_item.get("shift_semantic_gain"), "shift semantic gain"),
        tuple(differences),
    )


def qualify_reproductions(
    runs: Sequence[ReproductionRun],
    *,
    minimum_runs: int = 3,
    minimum_mean_gain: float = 0.05,
    bootstrap_resamples: int = 10_000,
    bootstrap_seed: int = 20260806,
) -> ReproductionQualification:
    if len(runs) < 1:
        raise ValueError("reproduction qualification requires runs")
    if minimum_runs < 1:
        raise ValueError("minimum_runs must be positive")
    if not 0.0 < minimum_mean_gain <= 1.0:
        raise ValueError("minimum_mean_gain must be in (0, 1]")
    ordered = tuple(sorted(runs, key=lambda item: item.experiment_sha256))
    if len({run.experiment_sha256 for run in ordered}) != len(ordered):
        raise ReproductionError("duplicate experiment manifests were supplied")
    if len({run.split_pool_sha256s for run in ordered}) != len(ordered):
        raise ReproductionError(
            "reproduction runs do not use independent split candidate pools"
        )

    run_gains = tuple(run.hidden_semantic_gain for run in ordered)
    pooled = tuple(
        difference
        for run in ordered
        for difference in run.hidden_task_differences
    )
    run_ci = paired_bootstrap_mean_interval(
        run_gains,
        resamples=bootstrap_resamples,
        seed=bootstrap_seed,
    )
    pooled_ci = paired_bootstrap_mean_interval(
        pooled,
        resamples=bootstrap_resamples,
        seed=bootstrap_seed ^ 0x5E1F,
    )
    reasons: list[str] = []
    if len(ordered) < minimum_runs:
        reasons.append(
            f"independent runs {len(ordered)} are below required {minimum_runs}"
        )
    failed = sum(not run.passed_single_run_gate for run in ordered)
    if failed:
        reasons.append(f"{failed} run(s) failed the frozen single-run gate")
    mean_gain = mean(run_gains)
    if mean_gain < minimum_mean_gain:
        reasons.append(
            f"mean hidden gain {mean_gain:.4f} is below {minimum_mean_gain:.4f}"
        )
    if any(run.hidden_ci_lower <= 0.0 for run in ordered):
        reasons.append("at least one run has a nonpositive hidden lower bound")
    if run_ci.lower <= 0.0:
        reasons.append("run-level paired bootstrap lower bound is not above zero")
    if pooled_ci.lower <= 0.0:
        reasons.append("pooled-task paired bootstrap lower bound is not above zero")
    minimum_shift = min(run.shift_semantic_gain for run in ordered)
    if minimum_shift <= 0.0:
        reasons.append("at least one run has no positive shift gain")

    return ReproductionQualification(
        ordered,
        mean_gain,
        run_ci,
        mean(pooled),
        pooled_ci,
        minimum_shift,
        not reasons,
        tuple(reasons),
    )
