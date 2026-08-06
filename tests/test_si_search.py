from plural_cognition.self_improvement import (
    PolicyMode,
    SearchConfig,
    SplitFitness,
    enumerate_normalized_genomes,
    run_quality_diverse_search,
    run_random_search,
    run_single_best_search,
)


def _score(semantic: float, operations: int) -> SplitFitness:
    return SplitFitness(
        exact_accuracy=max(0.0, semantic - 0.1),
        mean_semantic_accuracy=semantic,
        invalid_rate=0.0,
        mean_reasoning_operations=float(operations),
        max_reasoning_operations=operations,
        over_budget_rate=0.0,
    )


def _adaptation_valley_evaluator(genome):
    values = {
        PolicyMode.COMPLETE_SELECTION: (0.60, 10),
        PolicyMode.VERIFIED_FRAGMENT_SELECTION: (0.55, 12),
        PolicyMode.VERIFIED_SYNTHESIS: (0.90, 20),
        PolicyMode.UNVERIFIED_SYNTHESIS: (0.70, 18),
    }
    semantic, operations = values[genome.mode]
    fitness = _score(semantic, operations)
    return fitness, fitness


def test_quality_archive_crosses_adaptation_valley_single_best_rejects() -> None:
    config = SearchConfig(
        generations=3,
        max_genome_evaluations=20,
        archive_capacity=8,
        random_seed=7,
    )

    lineage = run_single_best_search(_adaptation_valley_evaluator, config=config)
    archive = run_quality_diverse_search(_adaptation_valley_evaluator, config=config)

    assert lineage.champion.genome.mode is PolicyMode.COMPLETE_SELECTION
    assert lineage.stopped_reason == "local optimum or adaptation valley"
    assert archive.champion.genome.mode is PolicyMode.VERIFIED_SYNTHESIS
    assert archive.champion.development.mean_semantic_accuracy == 0.90
    assert any(
        record.genome.mode is PolicyMode.VERIFIED_FRAGMENT_SELECTION
        for record in archive.records
    )
    assert any(
        event.reason == "first eligible elite in behavior cell"
        for event in archive.promotions
    )


def test_random_search_is_deterministic_under_fixed_seed_and_budget() -> None:
    config = SearchConfig(
        generations=2,
        max_genome_evaluations=12,
        archive_capacity=8,
        random_seed=123,
    )

    first = run_random_search(_adaptation_valley_evaluator, config=config)
    second = run_random_search(_adaptation_valley_evaluator, config=config)

    assert first.canonical_payload() == second.canonical_payload()
    assert first.sha256 == second.sha256
    assert first.evaluated_genome_count == 12


def test_normalized_genome_space_contains_unique_identities() -> None:
    genomes = enumerate_normalized_genomes()

    assert genomes
    assert len({genome.sha256 for genome in genomes}) == len(genomes)
    assert any(genome.mode is PolicyMode.COMPLETE_SELECTION for genome in genomes)
    assert any(genome.mode is PolicyMode.VERIFIED_SYNTHESIS for genome in genomes)
