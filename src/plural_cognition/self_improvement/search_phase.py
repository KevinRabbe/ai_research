"""Public SI search phase using cached target-free packet preparation."""

from __future__ import annotations

from typing import Sequence

from plural_cognition.boolean_world import CausalExample

from .candidate_pool import FrozenCandidatePool
from .experiment import (
    SearchPhaseResult,
    _validate_split,
    deterministic_target_permutation,
)
from .manifests import ExperimentSplit, SelfImprovementExperimentManifest, freeze_finalists
from .prepared import (
    evaluate_prepared_policy_on_split,
    prepare_candidate_pool,
)
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
    prepared_discovery = prepare_candidate_pool(discovery_pool)
    prepared_development = prepare_candidate_pool(development_pool)
    normal_cache: dict[str, tuple[SplitFitness, SplitFitness]] = {}
    shuffled_cache: dict[str, tuple[SplitFitness, SplitFitness]] = {}

    def evaluator(genome):
        normalized = genome.normalized()
        cached = normal_cache.get(normalized.sha256)
        if cached is not None:
            return cached
        discovery = evaluate_prepared_policy_on_split(
            normalized,
            prepared_discovery,
            discovery_examples,
            budget=experiment.reasoning_budget,
        )
        development = evaluate_prepared_policy_on_split(
            normalized,
            prepared_development,
            development_examples,
            budget=experiment.reasoning_budget,
        )
        result = (
            SplitFitness.from_policy_evaluation(discovery),
            SplitFitness.from_policy_evaluation(development),
        )
        normal_cache[normalized.sha256] = result
        return result

    discovery_permutation = deterministic_target_permutation(
        len(discovery_examples),
        experiment.shuffled_label_seed,
    )
    development_permutation = deterministic_target_permutation(
        len(development_examples),
        experiment.shuffled_label_seed ^ 0xD3E1,
    )

    def shuffled_evaluator(genome):
        normalized = genome.normalized()
        cached = shuffled_cache.get(normalized.sha256)
        if cached is not None:
            return cached
        discovery = evaluate_prepared_policy_on_split(
            normalized,
            prepared_discovery,
            discovery_examples,
            budget=experiment.reasoning_budget,
            target_source_indices=discovery_permutation,
        )
        development = evaluate_prepared_policy_on_split(
            normalized,
            prepared_development,
            development_examples,
            budget=experiment.reasoning_budget,
            target_source_indices=development_permutation,
        )
        result = (
            SplitFitness.from_policy_evaluation(discovery),
            SplitFitness.from_policy_evaluation(development),
        )
        shuffled_cache[normalized.sha256] = result
        return result

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
