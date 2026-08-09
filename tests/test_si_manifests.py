from plural_cognition.boolean_world import EvidenceCase, PublicTask, Var, canonical_text, encode_public_task
from plural_cognition.self_improvement import (
    CandidatePoolTask,
    FrozenCandidate,
    FrozenCandidatePool,
    GenerationSource,
    PolicyMode,
    ReasoningPolicyGenome,
    SearchConfig,
    build_experiment_manifest,
)


def _pool(identity: str) -> FrozenCandidatePool:
    task = PublicTask(
        f"TASK-{identity}",
        ("V0",),
        (
            EvidenceCase("E0", (False,), False),
            EvidenceCase("E1", (True,), True),
        ),
        (),
    )
    sources = (
        GenerationSource("sample-401", "sampled", 401, 1.0, 8),
        GenerationSource("sample-402", "sampled", 402, 1.0, 8),
    )
    candidates = tuple(
        FrozenCandidate(
            source.source_id,
            True,
            canonical_text(Var("V0")),
            (10 + index, 2),
            None,
        )
        for index, source in enumerate(sources)
    )
    return FrozenCandidatePool(
        "a" * 64,
        "b" * 64,
        (identity * 64,),
        sources,
        (CandidatePoolTask(0, tuple(encode_public_task(task)), candidates),),
    )


def test_experiment_manifest_binds_all_split_pools_and_frozen_gates() -> None:
    manifest = build_experiment_manifest(
        _pool("1"),
        _pool("2"),
        _pool("3"),
        _pool("4"),
        search_config=SearchConfig(
            generations=4,
            max_genome_evaluations=24,
            archive_capacity=12,
            random_seed=7,
        ),
        fixed_policy=ReasoningPolicyGenome(PolicyMode.VERIFIED_SYNTHESIS),
        bootstrap_resamples=200,
    )

    assert len(manifest.splits) == 4
    assert manifest.generation_source_ids == ("sample-401", "sample-402")
    assert manifest.minimum_hidden_gain == 0.05
    assert manifest.immutable_parent.mode is PolicyMode.COMPLETE_SELECTION
    assert manifest.fixed_policy.mode is PolicyMode.VERIFIED_SYNTHESIS
    assert len(manifest.sha256) == 64


def test_experiment_manifest_rejects_different_generation_protocols() -> None:
    shifted = _pool("4")
    changed_sources = (
        GenerationSource("sample-401", "sampled", 401, 0.5, 8),
        GenerationSource("sample-402", "sampled", 402, 1.0, 8),
    )
    shifted = FrozenCandidatePool(
        shifted.checkpoint_sha256,
        shifted.execution_sha256,
        shifted.task_shard_manifest_sha256s,
        changed_sources,
        shifted.tasks,
    )

    try:
        build_experiment_manifest(
            _pool("1"),
            _pool("2"),
            _pool("3"),
            shifted,
            bootstrap_resamples=200,
        )
    except ValueError as exc:
        assert "generation protocols" in str(exc)
    else:
        raise AssertionError("different generation protocols were accepted")
