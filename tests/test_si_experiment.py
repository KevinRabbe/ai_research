from plural_cognition.boolean_world import (
    And,
    EvidenceCase,
    Or,
    PublicTask,
    Var,
    canonical_text,
    encode_causal_example,
    encode_public_task,
)
from plural_cognition.self_improvement import (
    CandidatePoolTask,
    ExperimentSplit,
    FinalistRole,
    FrozenCandidate,
    FrozenCandidatePool,
    GenerationSource,
    SearchConfig,
    build_experiment_manifest,
    open_hidden_phase,
    run_search_phase,
)
from plural_cognition.self_improvement.io import (
    experiment_manifest_from_payload,
    search_phase_from_payload,
)


def _evidence(operator: str):
    values = []
    for value in range(8):
        assignment = tuple(bool((value >> shift) & 1) for shift in (2, 1, 0))
        output = (
            assignment[0] and assignment[1]
            if operator == "AND"
            else assignment[0] or assignment[1]
        )
        values.append(EvidenceCase(f"E{value:03b}", assignment, output))
    return tuple(values)


def _tasks_and_examples(identity: str):
    and_task = PublicTask(
        f"TASK-{identity}-AND",
        ("V0", "V1", "V2"),
        _evidence("AND"),
        (),
    )
    or_task = PublicTask(
        f"TASK-{identity}-OR",
        ("V0", "V1", "V2"),
        _evidence("OR"),
        (),
    )
    examples = (
        encode_causal_example(and_task, And((Var("V0"), Var("V1")))),
        encode_causal_example(or_task, Or((Var("V0"), Var("V1")))),
    )
    return (and_task, or_task), examples


def _pool(identity: str):
    tasks, examples = _tasks_and_examples(identity)
    sources = tuple(
        GenerationSource(f"sample-{seed}", "sampled", seed, 1.0, 8)
        for seed in (401, 402, 403, 404)
    )
    expressions = (
        (
            And((Var("V0"), Var("V2"))),
            Var("V1"),
            Var("V2"),
            Var("V0"),
        ),
        (
            Or((Var("V0"), Var("V2"))),
            Var("V1"),
            Var("V2"),
            Var("V0"),
        ),
    )
    pool_tasks = tuple(
        CandidatePoolTask(
            case_index,
            tuple(encode_public_task(task)),
            tuple(
                FrozenCandidate(
                    source.source_id,
                    True,
                    canonical_text(expression),
                    (20 + source_index, 2),
                    None,
                )
                for source_index, (source, expression) in enumerate(
                    zip(sources, task_expressions, strict=True)
                )
            ),
        )
        for case_index, (task, task_expressions) in enumerate(
            zip(tasks, expressions, strict=True)
        )
    )
    pool = FrozenCandidatePool(
        "a" * 64,
        "b" * 64,
        (identity * 64,),
        sources,
        pool_tasks,
    )
    return pool, examples


def test_search_freeze_and_hidden_opening_are_separate_and_replayable() -> None:
    discovery_pool, discovery_examples = _pool("1")
    development_pool, development_examples = _pool("2")
    hidden_pool, hidden_examples = _pool("3")
    shift_pool, shift_examples = _pool("4")
    experiment = build_experiment_manifest(
        discovery_pool,
        development_pool,
        hidden_pool,
        shift_pool,
        search_config=SearchConfig(
            generations=3,
            max_genome_evaluations=8,
            archive_capacity=8,
            random_seed=17,
        ),
        bootstrap_resamples=200,
    )

    restored_experiment = experiment_manifest_from_payload(
        experiment.canonical_payload()
    )
    assert restored_experiment == experiment
    assert experiment.split(ExperimentSplit.HIDDEN).candidate_pool_sha256 == hidden_pool.sha256

    phase = run_search_phase(
        experiment,
        discovery_pool=discovery_pool,
        discovery_examples=discovery_examples,
        development_pool=development_pool,
        development_examples=development_examples,
    )
    restored_phase = search_phase_from_payload(phase.canonical_payload())

    assert restored_phase.sha256 == phase.sha256
    assert phase.finalist_manifest.experiment_sha256 == experiment.sha256
    assert phase.archive.champion.development.mean_semantic_accuracy == 1.0
    assert phase.single_best.champion.development.mean_semantic_accuracy == 0.75

    report = open_hidden_phase(
        experiment,
        restored_phase,
        hidden_pool=hidden_pool,
        hidden_examples=hidden_examples,
        shift_pool=shift_pool,
        shift_examples=shift_examples,
    )
    primary = report.comparison(FinalistRole.ARCHIVE_CHAMPION)

    assert primary.hidden_semantic_gain == 0.25
    assert primary.shift_semantic_gain == 0.25
    assert primary.hidden_semantic_gain_ci.lower == 0.25
    assert report.evaluation(FinalistRole.ARCHIVE_CHAMPION).hidden.exact_accuracy == 1.0
    assert report.evaluation(FinalistRole.IMMUTABLE_PARENT).hidden.exact_accuracy == 0.0
    assert report.finalist_manifest_sha256 == phase.finalist_manifest.sha256
    assert len(report.sha256) == 64
