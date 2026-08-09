"""Efficient hidden opening for already-frozen SI finalists."""

from __future__ import annotations

from typing import Sequence

from plural_cognition.boolean_world import CausalExample

from .candidate_pool import FrozenCandidatePool
from .experiment import (
    FinalistEvaluation,
    HiddenOpeningReport,
    SearchPhaseResult,
    _paired_improvement,
    _validate_split,
)
from .manifests import (
    ExperimentSplit,
    FinalistRole,
    SelfImprovementExperimentManifest,
)
from .prepared import (
    evaluate_prepared_policy_on_split,
    prepare_candidate_pool,
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
    """Open hidden and shift targets only for the frozen finalist manifest."""

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
    prepared_hidden = prepare_candidate_pool(hidden_pool)
    prepared_shift = prepare_candidate_pool(shift_pool)
    hidden_cache = {}
    shift_cache = {}

    def evaluate_genome(genome):
        normalized = genome.normalized()
        hidden = hidden_cache.get(normalized.sha256)
        if hidden is None:
            hidden = evaluate_prepared_policy_on_split(
                normalized,
                prepared_hidden,
                hidden_examples,
                budget=experiment.reasoning_budget,
            )
            hidden_cache[normalized.sha256] = hidden
        shift = shift_cache.get(normalized.sha256)
        if shift is None:
            shift = evaluate_prepared_policy_on_split(
                normalized,
                prepared_shift,
                shift_examples,
                budget=experiment.reasoning_budget,
            )
            shift_cache[normalized.sha256] = shift
        return hidden, shift

    evaluations = []
    for finalist in search_phase.finalist_manifest.finalists:
        hidden, shift = evaluate_genome(finalist.genome)
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
    reversion = None
    if archive_champion_record.parent_sha256 is not None:
        parent_record = search_phase.archive.record(
            archive_champion_record.parent_sha256
        )
        hidden, shift = evaluate_genome(parent_record.genome)
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
    reasons = []
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
