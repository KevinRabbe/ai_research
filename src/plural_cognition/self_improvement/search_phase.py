"""Public SI search phase using unparented equal-budget random proposals."""

from __future__ import annotations

from typing import Sequence

from plural_cognition.boolean_world import CausalExample

from .candidate_pool import FrozenCandidatePool
from .evaluation import evaluate_policy_on_split
from .experiment import (
    SearchPhaseResult,
    _validate_split,
    deterministic_target_permutation,
)
from .manifests import ExperimentSplit, SelfImprovementExperimentManifest, freeze_finalists
from .search import (
    SplitFitness,
    run_quality_diverse_search,
    run_single_best_search,
)
from .search_random import run_random_search


def run_search_phase(
    experiment: SelfImprovementExperimentManifest,
    *,
    discovery_pool: FrozenCandidatePool,
    discovery_examples: Sequence[CausalExample],
    development_pool: FrozenCandidatePool,
    development_examples: Sequence[CausalExample],
) -> SearchPhaseResult:
    """Run search using only discovery/development targets and freeze finalists."""

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
