"""Equal-budget random search without fabricated lineage mutations."""

from __future__ import annotations

from random import Random

from .genome import IMMUTABLE_PARENT_GENOME, ReasoningPolicyGenome
from .search import (
    GenomeEvaluator,
    GenomeEvaluationRecord,
    SearchConfig,
    SearchResult,
    SearchStrategy,
    enumerate_normalized_genomes,
)


def _evaluate_unparented(
    genome: ReasoningPolicyGenome,
    *,
    evaluator: GenomeEvaluator,
) -> GenomeEvaluationRecord:
    discovery, development = evaluator(genome.normalized())
    return GenomeEvaluationRecord(
        genome.normalized(),
        0,
        None,
        None,
        discovery,
        development,
    )


def run_random_search(
    evaluator: GenomeEvaluator,
    *,
    config: SearchConfig | None = None,
    parent: ReasoningPolicyGenome = IMMUTABLE_PARENT_GENOME,
) -> SearchResult:
    """Evaluate unique independent genomes under the same total evaluation cap."""

    active = config or SearchConfig()
    root = _evaluate_unparented(parent, evaluator=evaluator)
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
        record = _evaluate_unparented(genome, evaluator=evaluator)
        records[record.genome.sha256] = record

    eligible = tuple(record for record in records.values() if record.eligible)
    champion = min(
        eligible or tuple(records.values()),
        key=lambda item: item.ordering_key,
    )
    ordered_records = tuple(
        sorted(records.values(), key=lambda item: item.genome.sha256)
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
