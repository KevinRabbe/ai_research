"""Immutable manifests for frozen-weight self-improvement experiments."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256

from .candidate_pool import FrozenCandidatePool
from .genome import (
    IMMUTABLE_PARENT_GENOME,
    PolicyMode,
    ReasoningPolicyGenome,
)
from .policy import ReasoningBudget
from .search import SearchConfig, SearchResult


class ExperimentSplit(str, Enum):
    DISCOVERY = "discovery"
    DEVELOPMENT = "development"
    HIDDEN = "hidden"
    SHIFT = "shift"


@dataclass(frozen=True, slots=True, order=True)
class SplitManifest:
    split: ExperimentSplit
    candidate_pool_sha256: str
    task_shard_manifest_sha256s: tuple[str, ...]
    task_count: int

    def __post_init__(self) -> None:
        if len(self.candidate_pool_sha256) != 64:
            raise ValueError("candidate-pool hash must contain 64 characters")
        int(self.candidate_pool_sha256, 16)
        if not self.task_shard_manifest_sha256s:
            raise ValueError("split manifest requires task-shard identities")
        for value in self.task_shard_manifest_sha256s:
            if len(value) != 64:
                raise ValueError("task-shard hash must contain 64 characters")
            int(value, 16)
        if type(self.task_count) is not int or self.task_count < 1:
            raise ValueError("task_count must be positive")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "split": self.split.value,
            "candidate_pool_sha256": self.candidate_pool_sha256,
            "task_shard_manifest_sha256s": list(
                self.task_shard_manifest_sha256s
            ),
            "task_count": self.task_count,
        }


@dataclass(frozen=True, slots=True)
class SelfImprovementExperimentManifest:
    checkpoint_sha256: str
    execution_sha256: str
    generation_source_ids: tuple[str, ...]
    splits: tuple[SplitManifest, ...]
    search_config: SearchConfig
    reasoning_budget: ReasoningBudget
    immutable_parent: ReasoningPolicyGenome
    fixed_policy: ReasoningPolicyGenome
    bootstrap_resamples: int = 10_000
    bootstrap_seed: int = 20260806
    shuffled_label_seed: int = 20260807
    minimum_hidden_gain: float = 0.05

    SCHEMA = "plural-cognition-si-experiment-manifest-v1"

    def __post_init__(self) -> None:
        for field in ("checkpoint_sha256", "execution_sha256"):
            value = getattr(self, field)
            if len(value) != 64:
                raise ValueError(f"{field} must contain 64 characters")
            int(value, 16)
        if not self.generation_source_ids:
            raise ValueError("experiment requires generation sources")
        if self.generation_source_ids != tuple(sorted(self.generation_source_ids)):
            raise ValueError("generation source IDs must be sorted")
        if len(set(self.generation_source_ids)) != len(self.generation_source_ids):
            raise ValueError("generation source IDs must be unique")
        expected_splits = tuple(ExperimentSplit)
        if tuple(item.split for item in self.splits) != expected_splits:
            raise ValueError("experiment must contain all splits in canonical order")
        if self.immutable_parent.normalized() != IMMUTABLE_PARENT_GENOME:
            raise ValueError("immutable parent differs from frozen SI-V1 parent")
        if self.fixed_policy.normalized().mode is not PolicyMode.VERIFIED_SYNTHESIS:
            raise ValueError("fixed comparison policy must use verified synthesis")
        if self.bootstrap_resamples < 100:
            raise ValueError("bootstrap_resamples must be at least 100")
        if type(self.bootstrap_seed) is not int or type(self.shuffled_label_seed) is not int:
            raise ValueError("experiment seeds must be integers")
        if not 0.0 < self.minimum_hidden_gain <= 1.0:
            raise ValueError("minimum_hidden_gain must be in (0, 1]")

    def split(self, value: ExperimentSplit) -> SplitManifest:
        return next(item for item in self.splits if item.split is value)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "schema": self.SCHEMA,
            "checkpoint_sha256": self.checkpoint_sha256,
            "execution_sha256": self.execution_sha256,
            "generation_source_ids": list(self.generation_source_ids),
            "splits": [item.canonical_payload() for item in self.splits],
            "search_config": self.search_config.canonical_payload(),
            "reasoning_budget": {
                "max_candidate_inputs": self.reasoning_budget.max_candidate_inputs,
                "max_packet_extractions": self.reasoning_budget.max_packet_extractions,
                "max_reasoning_operations": self.reasoning_budget.max_reasoning_operations,
            },
            "immutable_parent": self.immutable_parent.canonical_payload(),
            "immutable_parent_sha256": self.immutable_parent.sha256,
            "fixed_policy": self.fixed_policy.canonical_payload(),
            "fixed_policy_sha256": self.fixed_policy.sha256,
            "bootstrap_resamples": self.bootstrap_resamples,
            "bootstrap_seed": self.bootstrap_seed,
            "shuffled_label_seed": self.shuffled_label_seed,
            "minimum_hidden_gain": self.minimum_hidden_gain,
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
    source_protocol_sets = {
        tuple(source.canonical_payload().items() for source in pool.sources)
        for pool in pools
    }
    if len(source_protocol_sets) != 1:
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


class FinalistRole(str, Enum):
    IMMUTABLE_PARENT = "immutable-parent"
    SINGLE_BEST_CHAMPION = "single-best-champion"
    ARCHIVE_CHAMPION = "archive-champion"
    ARCHIVE_EFFICIENCY = "archive-efficiency"
    ARCHIVE_NOVEL = "archive-novel"
    RANDOM_CHAMPION = "random-champion"
    SHUFFLED_LABEL_CHAMPION = "shuffled-label-champion"
    FIXED_POLICY = "fixed-policy"


@dataclass(frozen=True, slots=True, order=True)
class FinalistEntry:
    role: FinalistRole
    genome: ReasoningPolicyGenome
    source_search_sha256: str | None

    def __post_init__(self) -> None:
        if self.source_search_sha256 is not None:
            if len(self.source_search_sha256) != 64:
                raise ValueError("source search hash must contain 64 characters")
            int(self.source_search_sha256, 16)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "role": self.role.value,
            "genome": self.genome.canonical_payload(),
            "genome_sha256": self.genome.sha256,
            "source_search_sha256": self.source_search_sha256,
        }


@dataclass(frozen=True, slots=True)
class FinalistManifest:
    experiment_sha256: str
    search_result_sha256s: tuple[tuple[str, str], ...]
    finalists: tuple[FinalistEntry, ...]

    SCHEMA = "plural-cognition-si-finalist-manifest-v1"

    def __post_init__(self) -> None:
        if len(self.experiment_sha256) != 64:
            raise ValueError("experiment hash must contain 64 characters")
        int(self.experiment_sha256, 16)
        if not self.search_result_sha256s:
            raise ValueError("finalist manifest requires search results")
        if self.search_result_sha256s != tuple(sorted(self.search_result_sha256s)):
            raise ValueError("search-result hashes must be sorted")
        roles = tuple(item.role for item in self.finalists)
        if roles != tuple(FinalistRole):
            raise ValueError("finalist manifest must contain every role in canonical order")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "schema": self.SCHEMA,
            "experiment_sha256": self.experiment_sha256,
            "search_result_sha256s": [
                {"name": name, "sha256": value}
                for name, value in self.search_result_sha256s
            ],
            "finalists": [item.canonical_payload() for item in self.finalists],
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


def _descriptor_distance(
    left: ReasoningPolicyGenome,
    right: ReasoningPolicyGenome,
) -> int:
    return sum(
        first != second
        for first, second in zip(
            left.descriptor.as_tuple(),
            right.descriptor.as_tuple(),
            strict=True,
        )
    )


def freeze_finalists(
    experiment: SelfImprovementExperimentManifest,
    *,
    single_best: SearchResult,
    archive: SearchResult,
    random_search: SearchResult,
    shuffled_labels: SearchResult,
) -> FinalistManifest:
    archive_elites = tuple(archive.record(value) for value in archive.elite_sha256s)
    efficiency = min(
        archive_elites,
        key=lambda item: (
            item.development.mean_reasoning_operations,
            item.ordering_key,
        ),
    )
    novel = min(
        archive_elites,
        key=lambda item: (
            -_descriptor_distance(item.genome, experiment.immutable_parent),
            item.ordering_key,
        ),
    )
    search_hashes = tuple(
        sorted(
            (
                ("archive", archive.sha256),
                ("random", random_search.sha256),
                ("shuffled-labels", shuffled_labels.sha256),
                ("single-best", single_best.sha256),
            )
        )
    )
    finalists = (
        FinalistEntry(
            FinalistRole.IMMUTABLE_PARENT,
            experiment.immutable_parent,
            None,
        ),
        FinalistEntry(
            FinalistRole.SINGLE_BEST_CHAMPION,
            single_best.champion.genome,
            single_best.sha256,
        ),
        FinalistEntry(
            FinalistRole.ARCHIVE_CHAMPION,
            archive.champion.genome,
            archive.sha256,
        ),
        FinalistEntry(
            FinalistRole.ARCHIVE_EFFICIENCY,
            efficiency.genome,
            archive.sha256,
        ),
        FinalistEntry(
            FinalistRole.ARCHIVE_NOVEL,
            novel.genome,
            archive.sha256,
        ),
        FinalistEntry(
            FinalistRole.RANDOM_CHAMPION,
            random_search.champion.genome,
            random_search.sha256,
        ),
        FinalistEntry(
            FinalistRole.SHUFFLED_LABEL_CHAMPION,
            shuffled_labels.champion.genome,
            shuffled_labels.sha256,
        ),
        FinalistEntry(
            FinalistRole.FIXED_POLICY,
            experiment.fixed_policy,
            None,
        ),
    )
    return FinalistManifest(experiment.sha256, search_hashes, finalists)
