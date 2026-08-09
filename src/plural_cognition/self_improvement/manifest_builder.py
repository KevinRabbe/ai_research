"""Correct canonical construction of SI experiment manifests."""

from __future__ import annotations

import json

from .candidate_pool import FrozenCandidatePool
from .genome import IMMUTABLE_PARENT_GENOME, PolicyMode, ReasoningPolicyGenome
from .manifests import (
    ExperimentSplit,
    SelfImprovementExperimentManifest,
    SplitManifest,
)
from .policy import ReasoningBudget
from .search import SearchConfig


def _source_protocol_fingerprint(pool: FrozenCandidatePool) -> str:
    return json.dumps(
        [source.canonical_payload() for source in pool.sources],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def build_experiment_manifest(
    discovery: FrozenCandidatePool,
    development: FrozenCandidatePool,
    hidden: FrozenCandidatePool,
    shift: FrozenCandidatePool,
    *,
    search_config: SearchConfig | None = None,
    reasoning_budget: ReasoningBudget | None = None,
    fixed_policy: ReasoningPolicyGenome | None = None,
    bootstrap_resamples: int = 10_000,
    bootstrap_seed: int = 20260806,
    shuffled_label_seed: int = 20260807,
    minimum_hidden_gain: float = 0.05,
) -> SelfImprovementExperimentManifest:
    pools = (discovery, development, hidden, shift)
    if len({pool.checkpoint_sha256 for pool in pools}) != 1:
        raise ValueError("experiment pools use different checkpoints")
    if len({pool.execution_sha256 for pool in pools}) != 1:
        raise ValueError("experiment pools use different executions")
    source_sets = {
        tuple(source.source_id for source in pool.sources) for pool in pools
    }
    if len(source_sets) != 1:
        raise ValueError("experiment pools use different generation sources")
    protocol_fingerprints = {
        _source_protocol_fingerprint(pool) for pool in pools
    }
    if len(protocol_fingerprints) != 1:
        raise ValueError("experiment pools use different generation protocols")

    split_manifests = tuple(
        SplitManifest(
            split,
            pool.sha256,
            pool.task_shard_manifest_sha256s,
            len(pool.tasks),
        )
        for split, pool in zip(ExperimentSplit, pools, strict=True)
    )
    return SelfImprovementExperimentManifest(
        discovery.checkpoint_sha256,
        discovery.execution_sha256,
        source_sets.pop(),
        split_manifests,
        search_config or SearchConfig(),
        reasoning_budget or ReasoningBudget(),
        IMMUTABLE_PARENT_GENOME,
        fixed_policy or ReasoningPolicyGenome(PolicyMode.VERIFIED_SYNTHESIS),
        bootstrap_resamples,
        bootstrap_seed,
        shuffled_label_seed,
        minimum_hidden_gain,
    )
