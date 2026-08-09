from pathlib import Path

from plural_cognition.boolean_world import canonical_text, encode_public_task
from plural_cognition.dataset_shard import build_dataset_shard, read_dataset_shard
from plural_cognition.manifest_io import (
    read_canonical_json,
    write_dataset_shard_manifest,
)
from plural_cognition.self_improvement import (
    CandidatePoolTask,
    FrozenCandidate,
    FrozenCandidatePool,
    GenerationSource,
)
from plural_cognition.self_improvement.io import write_candidate_pool
from plural_cognition.self_improvement_open_hidden_cli import main as open_hidden_main
from plural_cognition.self_improvement_prepare_cli import main as prepare_main
from plural_cognition.self_improvement_search_cli import main as search_main
from plural_cognition.training_data import TrainingDataConfig
from plural_cognition.boolean_world.generator import GenerationConfig
from plural_cognition.validation import decode_supervised_causal_example


def _make_split(tmp_path: Path, name: str, seed: int):
    data = tmp_path / f"{name}.jsonl"
    manifest_path = tmp_path / f"{name}.manifest.json"
    config = TrainingDataConfig(
        base_seed=seed,
        catalog_size=16,
        generation=GenerationConfig(
            variable_count=3,
            min_atoms=2,
            max_atoms=3,
            max_depth=3,
        ),
    )
    manifest = build_dataset_shard(
        data,
        split="test",
        start_index=0,
        example_count=2,
        config=config,
    )
    write_dataset_shard_manifest(manifest_path, manifest)
    examples = tuple(read_dataset_shard(data, manifest))
    sources = tuple(
        GenerationSource(f"sample-{seed_value}", "sampled", seed_value, 1.0, 8)
        for seed_value in (401, 402, 403, 404)
    )
    tasks = []
    for case_index, example in enumerate(examples):
        decoded = decode_supervised_causal_example(example)
        expression = canonical_text(decoded.target)
        candidates = tuple(
            FrozenCandidate(
                source.source_id,
                True,
                expression,
                (30 + source_index, 2),
                None,
            )
            for source_index, source in enumerate(sources)
        )
        tasks.append(
            CandidatePoolTask(
                case_index,
                tuple(encode_public_task(decoded.public)),
                candidates,
            )
        )
    pool = FrozenCandidatePool(
        "a" * 64,
        "b" * 64,
        (manifest.sha256,),
        sources,
        tuple(tasks),
    )
    pool_path = tmp_path / f"{name}.pool.json"
    write_candidate_pool(pool_path, pool)
    return data, manifest_path, pool_path


def test_cpu_commands_freeze_search_and_open_hidden(tmp_path) -> None:
    discovery = _make_split(tmp_path, "discovery", 11)
    development = _make_split(tmp_path, "development", 12)
    hidden = _make_split(tmp_path, "hidden", 13)
    shift = _make_split(tmp_path, "shift", 14)
    experiment = tmp_path / "experiment.json"

    assert prepare_main(
        (
            "--discovery-pool",
            str(discovery[2]),
            "--development-pool",
            str(development[2]),
            "--hidden-pool",
            str(hidden[2]),
            "--shift-pool",
            str(shift[2]),
            "--generations",
            "2",
            "--max-genome-evaluations",
            "4",
            "--archive-capacity",
            "4",
            "--bootstrap-resamples",
            "200",
            "--output",
            str(experiment),
        )
    ) == 0

    search_phase = tmp_path / "search.json"
    finalists = tmp_path / "finalists.json"
    assert search_main(
        (
            "--experiment",
            str(experiment),
            "--discovery-pool",
            str(discovery[2]),
            "--development-pool",
            str(development[2]),
            "--discovery-shard",
            str(discovery[0]),
            str(discovery[1]),
            "--development-shard",
            str(development[0]),
            str(development[1]),
            "--output",
            str(search_phase),
            "--finalists-output",
            str(finalists),
        )
    ) == 0

    report = tmp_path / "hidden.json"
    assert open_hidden_main(
        (
            "--experiment",
            str(experiment),
            "--search-phase",
            str(search_phase),
            "--finalists",
            str(finalists),
            "--hidden-pool",
            str(hidden[2]),
            "--shift-pool",
            str(shift[2]),
            "--hidden-shard",
            str(hidden[0]),
            str(hidden[1]),
            "--shift-shard",
            str(shift[0]),
            str(shift[1]),
            "--output",
            str(report),
        )
    ) == 0

    experiment_payload = read_canonical_json(experiment)
    search_payload = read_canonical_json(search_phase)
    finalist_payload = read_canonical_json(finalists)
    hidden_payload = read_canonical_json(report)

    assert experiment_payload["schema"] == "plural-cognition-si-experiment-manifest-v1"
    assert search_payload["schema"] == "plural-cognition-si-search-phase-v1"
    assert finalist_payload["schema"] == "plural-cognition-si-finalist-manifest-v1"
    assert hidden_payload["schema"] == "plural-cognition-si-hidden-opening-v1"
    assert hidden_payload["finalist_manifest_sha256"] == search_payload["finalist_manifest_sha256"]
