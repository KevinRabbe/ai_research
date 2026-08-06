"""Deterministic bounded search over immutable reasoning-policy descendants."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from itertools import product
from random import Random
from typing import Callable

from .evaluation import PolicyEvaluation
from .genome import (
    CANDIDATE_EVALUATION_CAPS,
    COMPOSITE_GENERATION_CAPS,
    EXPRESSION_DEPTH_CAPS,
    EXPRESSION_NODE_CAPS,
    IMMUTABLE_PARENT_GENOME,
    POLICY_MODES,
    SYNTHESIS_ROUNDS,
    UNIQUE_CANDIDATE_CAPS,
    BehaviorDescriptor,
    ReasoningPolicyGenome,
)
from .mutation import MutationRecord, propose_neighbor_mutations


class SearchStrategy(str, Enum):
    SINGLE_BEST = "single-best-lineage"
    QUALITY_DIVERSE = "quality-diverse-archive"
    RANDOM = "random-genome-search"


@dataclass(frozen=True, slots=True)
class SplitFitness:
    exact_accuracy: float
    mean_semantic_accuracy: float
    invalid_rate: float
    mean_reasoning_operations: float
    max_reasoning_operations: int
    over_budget_rate: float

    def __post_init__(self) -> None:
        for field in (
            "exact_accuracy",
            "mean_semantic_accuracy",
            "invalid_rate",
            "over_budget_rate",
        ):
            value = getattr(self, field)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field} must be in [0, 1]")
        if self.mean_reasoning_operations < 0.0:
            raise ValueError("mean_reasoning_operations must not be negative")
        if self.max_reasoning_operations < 0:
            raise ValueError("max_reasoning_operations must not be negative")

    @classmethod
    def from_policy_evaluation(cls, evaluation: PolicyEvaluation) -> SplitFitness:
        return cls(
            evaluation.exact_accuracy,
            evaluation.mean_semantic_accuracy,
            evaluation.invalid_rate,
            evaluation.mean_reasoning_operations,
            evaluation.max_reasoning_operations,
            evaluation.over_budget_rate,
        )

    @property
    def eligible(self) -> bool:
        return self.invalid_rate == 0.0 and self.over_budget_rate == 0.0

    @property
    def ordering_key(self) -> tuple[float, float, float, float, int]:
        """Smaller is better."""

        return (
            -self.mean_semantic_accuracy,
            -self.exact_accuracy,
            self.invalid_rate,
            self.mean_reasoning_operations,
            self.max_reasoning_operations,
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "exact_accuracy": self.exact_accuracy,
            "mean_semantic_accuracy": self.mean_semantic_accuracy,
            "invalid_rate": self.invalid_rate,
            "mean_reasoning_operations": self.mean_reasoning_operations,
            "max_reasoning_operations": self.max_reasoning_operations,
            "over_budget_rate": self.over_budget_rate,
        }


@dataclass(frozen=True, slots=True)
class SearchConfig:
    generations: int = 8
    max_genome_evaluations: int = 64
    archive_capacity: int = 24
    random_seed: int = 20260806

    def __post_init__(self) -> None:
        for field in (
            "generations",
            "max_genome_evaluations",
            "archive_capacity",
        ):
            if type(getattr(self, field)) is not int or getattr(self, field) < 1:
                raise ValueError(f"{field} must be a positive integer")
        if type(self.random_seed) is not int:
            raise ValueError("random_seed must be an integer")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "generations": self.generations,
            "max_genome_evaluations": self.max_genome_evaluations,
            "archive_capacity": self.archive_capacity,
            "random_seed": self.random_seed,
        }


@dataclass(frozen=True, slots=True)
class GenomeEvaluationRecord:
    genome: ReasoningPolicyGenome
    generation: int
    parent_sha256: str | None
    mutation: MutationRecord | None
    discovery: SplitFitness
    development: SplitFitness

    def __post_init__(self) -> None:
        if self.generation < 0:
            raise ValueError("record generation must not be negative")
        if self.generation == 0:
            if self.parent_sha256 is not None or self.mutation is not None:
                raise ValueError("root record cannot contain parent mutation metadata")
        else:
            if self.parent_sha256 is None or self.mutation is None:
                raise ValueError("descendant record requires parent and mutation")
            if self.parent_sha256 != self.mutation.parent_sha256:
                raise ValueError("record parent and mutation parent differ")
            if self.genome.sha256 != self.mutation.child_sha256:
                raise ValueError("record genome and mutation child differ")

    @property
    def eligible(self) -> bool:
        return self.discovery.eligible and self.development.eligible

    @property
    def ordering_key(self) -> tuple:
        return (
            *self.development.ordering_key,
            *self.discovery.ordering_key,
            self.genome.complexity,
            self.genome.sha256,
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "genome": self.genome.canonical_payload(),
            "genome_sha256": self.genome.sha256,
            "generation": self.generation,
            "parent_sha256": self.parent_sha256,
            "mutation": None
            if self.mutation is None
            else self.mutation.canonical_payload(),
            "descriptor": list(self.genome.descriptor.as_tuple()),
            "discovery": self.discovery.canonical_payload(),
            "development": self.development.canonical_payload(),
        }


@dataclass(frozen=True, slots=True)
class PromotionEvent:
    generation: int
    child_sha256: str
    replaced_sha256: str | None
    archive_cell: tuple[str, str, str, str] | None
    reason: str

    def __post_init__(self) -> None:
        if self.generation < 1:
            raise ValueError("promotion generation must be positive")
        if not self.child_sha256:
            raise ValueError("promotion child hash must not be empty")
        if not self.reason:
            raise ValueError("promotion reason must not be empty")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "generation": self.generation,
            "child_sha256": self.child_sha256,
            "replaced_sha256": self.replaced_sha256,
            "archive_cell": None
            if self.archive_cell is None
            else list(self.archive_cell),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class SearchResult:
    strategy: SearchStrategy
    config: SearchConfig
    records: tuple[GenomeEvaluationRecord, ...]
    promotions: tuple[PromotionEvent, ...]
    elite_sha256s: tuple[str, ...]
    champion_sha256: str
    stopped_reason: str

    SCHEMA = "plural-cognition-si-search-result-v1"

    def __post_init__(self) -> None:
        if not self.records:
            raise ValueError("search result requires evaluated genomes")
        hashes = tuple(record.genome.sha256 for record in self.records)
        if len(set(hashes)) != len(hashes):
            raise ValueError("search result contains duplicate genome evaluations")
        if self.champion_sha256 not in hashes:
            raise ValueError("search champion was not evaluated")
        if any(value not in hashes for value in self.elite_sha256s):
            raise ValueError("search elite was not evaluated")
        if not self.stopped_reason:
            raise ValueError("search result requires a stop reason")

    @property
    def evaluated_genome_count(self) -> int:
        return len(self.records)

    @property
    def champion(self) -> GenomeEvaluationRecord:
        return next(
            record
            for record in self.records
            if record.genome.sha256 == self.champion_sha256
        )

    def record(self, genome_sha256: str) -> GenomeEvaluationRecord:
        return next(
            record
            for record in self.records
            if record.genome.sha256 == genome_sha256
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "schema": self.SCHEMA,
            "strategy": self.strategy.value,
            "config": self.config.canonical_payload(),
            "evaluated_genome_count": self.evaluated_genome_count,
            "records": [record.canonical_payload() for record in self.records],
            "promotions": [event.canonical_payload() for event in self.promotions],
            "elite_sha256s": list(self.elite_sha256s),
            "champion_sha256": self.champion_sha256,
            "stopped_reason": self.stopped_reason,
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


GenomeEvaluator = Callable[
    [ReasoningPolicyGenome],
    tuple[SplitFitness, SplitFitness],
]


def _evaluate_record(
    genome: ReasoningPolicyGenome,
    *,
    generation: int,
    parent_sha256: str | None,
    mutation: MutationRecord | None,
    evaluator: GenomeEvaluator,
) -> GenomeEvaluationRecord:
    discovery, development = evaluator(genome.normalized())
    return GenomeEvaluationRecord(
        genome.normalized(),
        generation,
        parent_sha256,
        mutation,
        discovery,
        development,
    )


def _better(
    candidate: GenomeEvaluationRecord,
    incumbent: GenomeEvaluationRecord,
) -> bool:
    if not candidate.eligible:
        return False
    if not incumbent.eligible:
        return True
    return candidate.ordering_key < incumbent.ordering_key


def enumerate_normalized_genomes() -> tuple[ReasoningPolicyGenome, ...]:
    genomes: dict[str, ReasoningPolicyGenome] = {}
    for values in product(
        POLICY_MODES,
        SYNTHESIS_ROUNDS,
        UNIQUE_CANDIDATE_CAPS,
        CANDIDATE_EVALUATION_CAPS,
        COMPOSITE_GENERATION_CAPS,
        EXPRESSION_NODE_CAPS,
        EXPRESSION_DEPTH_CAPS,
    ):
        try:
            genome = ReasoningPolicyGenome(*values).normalized()
        except ValueError:
            continue
        genomes.setdefault(genome.sha256, genome)
    return tuple(sorted(genomes.values(), key=lambda item: item.sha256))


def run_single_best_search(
    evaluator: GenomeEvaluator,
    *,
    config: SearchConfig | None = None,
    parent: ReasoningPolicyGenome = IMMUTABLE_PARENT_GENOME,
) -> SearchResult:
    active = config or SearchConfig()
    root = _evaluate_record(
        parent,
        generation=0,
        parent_sha256=None,
        mutation=None,
        evaluator=evaluator,
    )
    records: dict[str, GenomeEvaluationRecord] = {root.genome.sha256: root}
    promotions: list[PromotionEvent] = []
    current = root
    stopped_reason = "generation limit reached"

    for generation in range(1, active.generations + 1):
        children: list[GenomeEvaluationRecord] = []
        for proposal in propose_neighbor_mutations(
            current.genome,
            generation=generation,
        ):
            if len(records) >= active.max_genome_evaluations:
                stopped_reason = "genome evaluation budget reached"
                break
            if proposal.child.sha256 in records:
                continue
            record = _evaluate_record(
                proposal.child,
                generation=generation,
                parent_sha256=current.genome.sha256,
                mutation=proposal.record,
                evaluator=evaluator,
            )
            records[record.genome.sha256] = record
            children.append(record)
        eligible = [child for child in children if _better(child, current)]
        if eligible:
            promoted = min(eligible, key=lambda item: item.ordering_key)
            promotions.append(
                PromotionEvent(
                    generation,
                    promoted.genome.sha256,
                    current.genome.sha256,
                    None,
                    "development-best one-step descendant",
                )
            )
            current = promoted
        elif stopped_reason == "generation limit reached":
            stopped_reason = "local optimum or adaptation valley"
            break
        if len(records) >= active.max_genome_evaluations:
            break

    ordered_records = tuple(
        sorted(records.values(), key=lambda item: (item.generation, item.genome.sha256))
    )
    return SearchResult(
        SearchStrategy.SINGLE_BEST,
        active,
        ordered_records,
        tuple(promotions),
        (current.genome.sha256,),
        current.genome.sha256,
        stopped_reason,
    )


def _archive_cell(genome: ReasoningPolicyGenome) -> tuple[str, str, str, str]:
    return genome.descriptor.as_tuple()


def run_quality_diverse_search(
    evaluator: GenomeEvaluator,
    *,
    config: SearchConfig | None = None,
    parent: ReasoningPolicyGenome = IMMUTABLE_PARENT_GENOME,
) -> SearchResult:
    active = config or SearchConfig()
    root = _evaluate_record(
        parent,
        generation=0,
        parent_sha256=None,
        mutation=None,
        evaluator=evaluator,
    )
    records: dict[str, GenomeEvaluationRecord] = {root.genome.sha256: root}
    archive: dict[tuple[str, str, str, str], str] = {
        _archive_cell(root.genome): root.genome.sha256
    }
    promotions: list[PromotionEvent] = []
    stopped_reason = "generation limit reached"

    for generation in range(1, active.generations + 1):
        parent_hashes = tuple(
            archive[cell]
            for cell in sorted(archive)
        )
        new_evaluations = 0
        for parent_hash in parent_hashes:
            parent_record = records[parent_hash]
            for proposal in propose_neighbor_mutations(
                parent_record.genome,
                generation=generation,
            ):
                if len(records) >= active.max_genome_evaluations:
                    stopped_reason = "genome evaluation budget reached"
                    break
                if proposal.child.sha256 in records:
                    continue
                record = _evaluate_record(
                    proposal.child,
                    generation=generation,
                    parent_sha256=parent_hash,
                    mutation=proposal.record,
                    evaluator=evaluator,
                )
                records[record.genome.sha256] = record
                new_evaluations += 1
                if not record.eligible:
                    continue
                cell = _archive_cell(record.genome)
                incumbent_hash = archive.get(cell)
                if incumbent_hash is not None:
                    incumbent = records[incumbent_hash]
                    if _better(record, incumbent):
                        archive[cell] = record.genome.sha256
                        promotions.append(
                            PromotionEvent(
                                generation,
                                record.genome.sha256,
                                incumbent_hash,
                                cell,
                                "better elite in occupied behavior cell",
                            )
                        )
                    continue
                if len(archive) < active.archive_capacity:
                    archive[cell] = record.genome.sha256
                    promotions.append(
                        PromotionEvent(
                            generation,
                            record.genome.sha256,
                            None,
                            cell,
                            "first eligible elite in behavior cell",
                        )
                    )
                    continue
                worst_cell, worst_hash = max(
                    archive.items(),
                    key=lambda item: records[item[1]].ordering_key,
                )
                worst = records[worst_hash]
                if _better(record, worst):
                    del archive[worst_cell]
                    archive[cell] = record.genome.sha256
                    promotions.append(
                        PromotionEvent(
                            generation,
                            record.genome.sha256,
                            worst_hash,
                            cell,
                            "better elite replaced worst full-archive cell",
                        )
                    )
            if len(records) >= active.max_genome_evaluations:
                break
        if len(records) >= active.max_genome_evaluations:
            break
        if new_evaluations == 0:
            stopped_reason = "archive neighborhood exhausted"
            break

    elite_hashes = tuple(
        archive[cell]
        for cell in sorted(archive)
    )
    champion_hash = min(
        elite_hashes,
        key=lambda value: records[value].ordering_key,
    )
    ordered_records = tuple(
        sorted(records.values(), key=lambda item: (item.generation, item.genome.sha256))
    )
    return SearchResult(
        SearchStrategy.QUALITY_DIVERSE,
        active,
        ordered_records,
        tuple(promotions),
        elite_hashes,
        champion_hash,
        stopped_reason,
    )


def run_random_search(
    evaluator: GenomeEvaluator,
    *,
    config: SearchConfig | None = None,
    parent: ReasoningPolicyGenome = IMMUTABLE_PARENT_GENOME,
) -> SearchResult:
    active = config or SearchConfig()
    root = _evaluate_record(
        parent,
        generation=0,
        parent_sha256=None,
        mutation=None,
        evaluator=evaluator,
    )
    records: dict[str, GenomeEvaluationRecord] = {root.genome.sha256: root}
    candidates = [
        genome
        for genome in enumerate_normalized_genomes()
        if genome.sha256 != root.genome.sha256
    ]
    rng = Random(active.random_seed)
    rng.shuffle(candidates)
    for genome in candidates:
        if len(records) >= active.max_genome_evaluations:
            break
        record = _evaluate_record(
            genome,
            generation=1,
            parent_sha256=root.genome.sha256,
            mutation=MutationRecord(
                root.genome.sha256,
                genome.sha256,
                "mode",
                root.genome.mode.value,
                genome.mode.value,
                1,
                len(records) - 1,
            ),
            evaluator=evaluator,
        )
        records[record.genome.sha256] = record

    eligible = tuple(record for record in records.values() if record.eligible)
    champion = min(
        eligible or tuple(records.values()),
        key=lambda item: item.ordering_key,
    )
    ordered_records = tuple(
        sorted(records.values(), key=lambda item: (item.generation, item.genome.sha256))
    )
    stopped_reason = (
        "genome evaluation budget reached"
        if len(records) >= active.max_genome_evaluations
        else "complete genome space exhausted"
    )
    return SearchResult(
        SearchStrategy.RANDOM,
        active,
        ordered_records,
        (),
        (champion.genome.sha256,),
        champion.genome.sha256,
        stopped_reason,
    )
