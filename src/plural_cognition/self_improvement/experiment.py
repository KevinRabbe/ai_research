"""Two-phase search, finalist freeze, and hidden opening for SI-V1."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from random import Random
from statistics import mean
from typing import Sequence

from plural_cognition.boolean_world import CausalExample
from plural_cognition.population.statistics import (
    ConfidenceInterval,
    paired_bootstrap_mean_interval,
)

from .candidate_pool import FrozenCandidatePool
from .evaluation import PolicyEvaluation, evaluate_policy_on_split
from .manifests import (
    ExperimentSplit,
    FinalistManifest,
    FinalistRole,
    SelfImprovementExperimentManifest,
    freeze_finalists,
)
from .search import (
    SearchResult,
    SplitFitness,
    run_quality_diverse_search,
    run_random_search,
    run_single_best_search,
)


def deterministic_target_permutation(count: int, seed: int) -> tuple[int, ...]:
    if type(count) is not int or count < 2:
        raise ValueError("target permutation requires at least two tasks")
    if type(seed) is not int:
        raise ValueError("target permutation seed must be an integer")
    values = list(range(count))
    Random(seed).shuffle(values)
    if all(index == value for index, value in enumerate(values)):
        values = values[1:] + values[:1]
    return tuple(values)


@dataclass(frozen=True, slots=True)
class SearchPhaseResult:
    experiment_sha256: str
    single_best: SearchResult
    archive: SearchResult
    random_search: SearchResult
    shuffled_labels: SearchResult
    finalist_manifest: FinalistManifest

    SCHEMA = "plural-cognition-si-search-phase-v1"

    def __post_init__(self) -> None:
        if len(self.experiment_sha256) != 64:
            raise ValueError("experiment hash must contain 64 characters")
        int(self.experiment_sha256, 16)
        expected = {
            "single-best": self.single_best.sha256,
            "archive": self.archive.sha256,
            "random": self.random_search.sha256,
            "shuffled-labels": self.shuffled_labels.sha256,
        }
        if dict(self.finalist_manifest.search_result_sha256s) != expected:
            raise ValueError("finalist manifest does not match search results")
        if self.finalist_manifest.experiment_sha256 != self.experiment_sha256:
            raise ValueError("finalist manifest belongs to a different experiment")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "schema": self.SCHEMA,
            "experiment_sha256": self.experiment_sha256,
            "single_best": self.single_best.canonical_payload(),
            "archive": self.archive.canonical_payload(),
            "random_search": self.random_search.canonical_payload(),
            "shuffled_labels": self.shuffled_labels.canonical_payload(),
            "finalist_manifest": self.finalist_manifest.canonical_payload(),
            "finalist_manifest_sha256": self.finalist_manifest.sha256,
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


def _validate_split(
    experiment: SelfImprovementExperimentManifest,
    split: ExperimentSplit,
    pool: FrozenCandidatePool,
    examples: Sequence[CausalExample],
) -> None:
    manifest = experiment.split(split)
    if pool.sha256 != manifest.candidate_pool_sha256:
        raise ValueError(f"{split.value} candidate pool differs from experiment")
    if pool.task_shard_manifest_sha256s != manifest.task_shard_manifest_sha256s:
        raise ValueError(f"{split.value} task-shard identities differ from experiment")
    if len(pool.tasks) != manifest.task_count or len(examples) != manifest.task_count:
        raise ValueError(f"{split.value} task count differs from experiment")
    if pool.checkpoint_sha256 != experiment.checkpoint_sha256:
        raise ValueError(f"{split.value} pool uses a different checkpoint")
    if pool.execution_sha256 != experiment.execution_sha256:
        raise ValueError(f"{split.value} pool uses a different execution")


def run_search_phase(
    experiment: SelfImprovementExperimentManifest,
    *,
    discovery_pool: FrozenCandidatePool,
    discovery_examples: Sequence[CausalExample],
    development_pool: FrozenCandidatePool,
    development_examples: Sequence[CausalExample],
) -> SearchPhaseResult:
    """Run all search strategies without accepting hidden or shift targets."""

    _validate_split(
        experiment,
        ExperimentSplit.DISCOVERY,
        discovery_pool,
        discovery_examples,
    )
    _validate_split(
        experiment,
        ExperimentSplit.DEVELOPMENT,
        development_pool,
        development_examples,
    )

    def evaluator(genome):
        discovery = evaluate_policy_on_split(
            genome,
            discovery_pool,
            discovery_examples,
            budget=experiment.reasoning_budget,
        )
        development = evaluate_policy_on_split(
            genome,
            development_pool,
            development_examples,
            budget=experiment.reasoning_budget,
        )
        return (
            SplitFitness.from_policy_evaluation(discovery),
            SplitFitness.from_policy_evaluation(development),
        )

    discovery_permutation = deterministic_target_permutation(
        len(discovery_examples),
        experiment.shuffled_label_seed,
    )
    development_permutation = deterministic_target_permutation(
        len(development_examples),
        experiment.shuffled_label_seed ^ 0xD3E1,
    )

    def shuffled_evaluator(genome):
        discovery = evaluate_policy_on_split(
            genome,
            discovery_pool,
            discovery_examples,
            budget=experiment.reasoning_budget,
            target_source_indices=discovery_permutation,
        )
        development = evaluate_policy_on_split(
            genome,
            development_pool,
            development_examples,
            budget=experiment.reasoning_budget,
            target_source_indices=development_permutation,
        )
        return (
            SplitFitness.from_policy_evaluation(discovery),
            SplitFitness.from_policy_evaluation(development),
        )

    single_best = run_single_best_search(
        evaluator,
        config=experiment.search_config,
        parent=experiment.immutable_parent,
    )
    archive = run_quality_diverse_search(
        evaluator,
        config=experiment.search_config,
        parent=experiment.immutable_parent,
    )
    random_search = run_random_search(
        evaluator,
        config=experiment.search_config,
        parent=experiment.immutable_parent,
    )
    shuffled_labels = run_quality_diverse_search(
        shuffled_evaluator,
        config=experiment.search_config,
        parent=experiment.immutable_parent,
    )
    finalists = freeze_finalists(
        experiment,
        single_best=single_best,
        archive=archive,
        random_search=random_search,
        shuffled_labels=shuffled_labels,
    )
    return SearchPhaseResult(
        experiment.sha256,
        single_best,
        archive,
        random_search,
        shuffled_labels,
        finalists,
    )


@dataclass(frozen=True, slots=True)
class FinalistEvaluation:
    role: FinalistRole
    genome_sha256: str
    hidden: PolicyEvaluation
    shift: PolicyEvaluation

    def __post_init__(self) -> None:
        if self.hidden.genome_sha256 != self.genome_sha256:
            raise ValueError("hidden evaluation uses a different genome")
        if self.shift.genome_sha256 != self.genome_sha256:
            raise ValueError("shift evaluation uses a different genome")


@dataclass(frozen=True, slots=True)
class PairedImprovement:
    role: FinalistRole
    hidden_semantic_gain: float
    hidden_semantic_gain_ci: ConfidenceInterval
    hidden_exact_gain: float
    shift_semantic_gain: float
    shift_semantic_gain_ci: ConfidenceInterval
    wins: int
    ties: int
    losses: int


@dataclass(frozen=True, slots=True)
class HiddenOpeningReport:
    experiment_sha256: str
    search_phase_sha256: str
    finalist_manifest_sha256: str
    evaluations: tuple[FinalistEvaluation, ...]
    comparisons: tuple[PairedImprovement, ...]
    archive_parent_reversion: FinalistEvaluation | None
    passed_single_run_gate: bool
    reasons: tuple[str, ...]

    SCHEMA = "plural-cognition-si-hidden-opening-v1"

    def evaluation(self, role: FinalistRole) -> FinalistEvaluation:
        return next(item for item in self.evaluations if item.role is role)

    def comparison(self, role: FinalistRole) -> PairedImprovement:
        return next(item for item in self.comparisons if item.role is role)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "schema": self.SCHEMA,
            "experiment_sha256": self.experiment_sha256,
            "search_phase_sha256": self.search_phase_sha256,
            "finalist_manifest_sha256": self.finalist_manifest_sha256,
            "evaluations": [
                {
                    "role": item.role.value,
                    "genome_sha256": item.genome_sha256,
                    "hidden": _evaluation_payload(item.hidden),
                    "shift": _evaluation_payload(item.shift),
                }
                for item in self.evaluations
            ],
            "comparisons": [
                {
                    "role": item.role.value,
                    "hidden_semantic_gain": item.hidden_semantic_gain,
                    "hidden_semantic_gain_ci": _interval_payload(
                        item.hidden_semantic_gain_ci
                    ),
                    "hidden_exact_gain": item.hidden_exact_gain,
                    "shift_semantic_gain": item.shift_semantic_gain,
                    "shift_semantic_gain_ci": _interval_payload(
                        item.shift_semantic_gain_ci
                    ),
                    "wins": item.wins,
                    "ties": item.ties,
                    "losses": item.losses,
                }
                for item in self.comparisons
            ],
            "archive_parent_reversion": None
            if self.archive_parent_reversion is None
            else {
                "role": self.archive_parent_reversion.role.value,
                "genome_sha256": self.archive_parent_reversion.genome_sha256,
                "hidden": _evaluation_payload(self.archive_parent_reversion.hidden),
                "shift": _evaluation_payload(self.archive_parent_reversion.shift),
            },
            "passed_single_run_gate": self.passed_single_run_gate,
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


def _interval_payload(interval: ConfidenceInterval) -> dict[str, float]:
    return {
        "lower": interval.lower,
        "estimate": interval.estimate,
        "upper": interval.upper,
        "confidence": interval.confidence,
    }


def _evaluation_payload(evaluation: PolicyEvaluation) -> dict[str, object]:
    return {
        "genome_sha256": evaluation.genome_sha256,
        "task_indices": list(evaluation.task_indices),
        "exact_accuracy": evaluation.exact_accuracy,
        "mean_semantic_accuracy": evaluation.mean_semantic_accuracy,
        "visible_consistency_rate": evaluation.visible_consistency_rate,
        "invalid_rate": evaluation.invalid_rate,
        "mean_reasoning_operations": evaluation.mean_reasoning_operations,
        "max_reasoning_operations": evaluation.max_reasoning_operations,
        "over_budget_rate": evaluation.over_budget_rate,
        "cases": [
            {
                "case_index": case.case_index,
                "valid": case.execution.valid,
                "expression": case.execution.canonical_expression,
                "error": case.execution.error,
                "semantic_accuracy": case.semantic_accuracy,
                "exact": case.exact,
                "reasoning_operations": (
                    case.execution.resources.reasoning_operations
                ),
            }
            for case in evaluation.cases
        ],
    }


def _paired_improvement(
    role: FinalistRole,
    parent: FinalistEvaluation,
    candidate: FinalistEvaluation,
    *,
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> PairedImprovement:
    hidden_differences = tuple(
        child.semantic_accuracy - root.semantic_accuracy
        for root, child in zip(
            parent.hidden.cases,
            candidate.hidden.cases,
            strict=True,
        )
    )
    shift_differences = tuple(
        child.semantic_accuracy - root.semantic_accuracy
        for root, child in zip(
            parent.shift.cases,
            candidate.shift.cases,
            strict=True,
        )
    )
    wins = sum(value > 0.0 for value in hidden_differences)
    losses = sum(value < 0.0 for value in hidden_differences)
    ties = len(hidden_differences) - wins - losses
    return PairedImprovement(
        role,
        mean(hidden_differences),
        paired_bootstrap_mean_interval(
            hidden_differences,
            resamples=bootstrap_resamples,
            seed=bootstrap_seed ^ sum(role.value.encode("ascii")),
        ),
        candidate.hidden.exact_accuracy - parent.hidden.exact_accuracy,
        mean(shift_differences),
        paired_bootstrap_mean_interval(
            shift_differences,
            resamples=bootstrap_resamples,
            seed=bootstrap_seed ^ 0x51F7 ^ sum(role.value.encode("ascii")),
        ),
        wins,
        ties,
        losses,
    )


def open_hidden_phase(
    experiment: SelfImprovementExperimentManifest,
    search_phase: SearchPhaseResult,
    *,
    hidden_pool: FrozenCandidatePool,
    hidden_examples: Sequence[CausalExample],
    shift_pool: FrozenCandidatePool,
    shift_examples: Sequence[CausalExample],
) -> HiddenOpeningReport:
    """Open hidden and shift targets only for the already-frozen finalists."""

    if search_phase.experiment_sha256 != experiment.sha256:
        raise ValueError("search phase belongs to a different experiment")
    if search_phase.finalist_manifest.experiment_sha256 != experiment.sha256:
        raise ValueError("finalist manifest belongs to a different experiment")
    _validate_split(
        experiment,
        ExperimentSplit.HIDDEN,
        hidden_pool,
        hidden_examples,
    )
    _validate_split(
        experiment,
        ExperimentSplit.SHIFT,
        shift_pool,
        shift_examples,
    )

    evaluations: list[FinalistEvaluation] = []
    for finalist in search_phase.finalist_manifest.finalists:
        hidden = evaluate_policy_on_split(
            finalist.genome,
            hidden_pool,
            hidden_examples,
            budget=experiment.reasoning_budget,
        )
        shift = evaluate_policy_on_split(
            finalist.genome,
            shift_pool,
            shift_examples,
            budget=experiment.reasoning_budget,
        )
        evaluations.append(
            FinalistEvaluation(
                finalist.role,
                finalist.genome.sha256,
                hidden,
                shift,
            )
        )

    parent = next(
        item
        for item in evaluations
        if item.role is FinalistRole.IMMUTABLE_PARENT
    )
    comparisons = tuple(
        _paired_improvement(
            item.role,
            parent,
            item,
            bootstrap_resamples=experiment.bootstrap_resamples,
            bootstrap_seed=experiment.bootstrap_seed,
        )
        for item in evaluations
        if item.role is not FinalistRole.IMMUTABLE_PARENT
    )

    archive_champion_record = search_phase.archive.champion
    reversion: FinalistEvaluation | None = None
    if archive_champion_record.parent_sha256 is not None:
        parent_record = search_phase.archive.record(
            archive_champion_record.parent_sha256
        )
        hidden = evaluate_policy_on_split(
            parent_record.genome,
            hidden_pool,
            hidden_examples,
            budget=experiment.reasoning_budget,
        )
        shift = evaluate_policy_on_split(
            parent_record.genome,
            shift_pool,
            shift_examples,
            budget=experiment.reasoning_budget,
        )
        reversion = FinalistEvaluation(
            FinalistRole.ARCHIVE_CHAMPION,
            parent_record.genome.sha256,
            hidden,
            shift,
        )

    primary = next(
        item
        for item in comparisons
        if item.role is FinalistRole.ARCHIVE_CHAMPION
    )
    primary_evaluation = next(
        item
        for item in evaluations
        if item.role is FinalistRole.ARCHIVE_CHAMPION
    )
    random_evaluation = next(
        item
        for item in evaluations
        if item.role is FinalistRole.RANDOM_CHAMPION
    )
    shuffled_evaluation = next(
        item
        for item in evaluations
        if item.role is FinalistRole.SHUFFLED_LABEL_CHAMPION
    )
    reasons: list[str] = []
    if primary.hidden_semantic_gain < experiment.minimum_hidden_gain:
        reasons.append(
            f"archive hidden semantic gain {primary.hidden_semantic_gain:.4f} is below "
            f"{experiment.minimum_hidden_gain:.4f}"
        )
    if primary.hidden_semantic_gain_ci.lower <= 0.0:
        reasons.append("archive hidden paired bootstrap lower bound is not above zero")
    if primary.shift_semantic_gain <= 0.0:
        reasons.append("archive champion does not improve the shift split")
    if (
        primary_evaluation.hidden.mean_semantic_accuracy
        <= random_evaluation.hidden.mean_semantic_accuracy
    ):
        reasons.append("archive champion does not beat matched random search")
    if (
        primary_evaluation.hidden.max_reasoning_operations
        > experiment.reasoning_budget.max_reasoning_operations
    ):
        reasons.append("archive champion exceeds the frozen reasoning ceiling")
    if (
        shuffled_evaluation.hidden.mean_semantic_accuracy
        >= primary_evaluation.hidden.mean_semantic_accuracy
    ):
        reasons.append("shuffled-label control matches or exceeds archive champion")

    return HiddenOpeningReport(
        experiment.sha256,
        search_phase.sha256,
        search_phase.finalist_manifest.sha256,
        tuple(evaluations),
        comparisons,
        reversion,
        not reasons,
        tuple(reasons),
    )
