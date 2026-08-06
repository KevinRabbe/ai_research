from plural_cognition.dataset_shard import read_dataset_shard
from plural_cognition.manifest_io import read_dataset_shard_manifest
from plural_cognition.self_improvement_tasks_cli import (
    SHIFT_PROFILE,
    STANDARD_PROFILE,
    main,
)


def test_shift_profile_is_structurally_harder_than_standard() -> None:
    assert SHIFT_PROFILE.min_atoms > STANDARD_PROFILE.min_atoms
    assert SHIFT_PROFILE.max_atoms > STANDARD_PROFILE.max_atoms
    assert SHIFT_PROFILE.max_depth > STANDARD_PROFILE.max_depth
    assert SHIFT_PROFILE.ite_probability > STANDARD_PROFILE.ite_probability
    assert SHIFT_PROFILE.negation_probability > STANDARD_PROFILE.negation_probability


def test_shift_task_command_builds_replayable_bounded_shard(tmp_path) -> None:
    data = tmp_path / "shift.jsonl"
    manifest_path = tmp_path / "shift.manifest.json"

    assert main(
        (
            "--split",
            "test",
            "--profile",
            "shift-v1",
            "--start-index",
            "0",
            "--example-count",
            "1",
            "--base-seed",
            "20260816",
            "--output",
            str(data),
            "--manifest",
            str(manifest_path),
        )
    ) == 0
    manifest = read_dataset_shard_manifest(manifest_path)
    examples = tuple(read_dataset_shard(data, manifest))

    assert manifest.example_count == 1
    assert manifest.split == "test"
    assert len(examples) == 1
    assert len(examples[0].token_ids) <= 256
