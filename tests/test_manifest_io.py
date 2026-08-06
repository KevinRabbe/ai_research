import pytest

from plural_cognition.dataset_shard import (
    DatasetShardManifest,
    training_data_config_sha256,
)
from plural_cognition.execution import ExecutionManifest
from plural_cognition.experiment import RunIntent, resolve_run_intent
from plural_cognition.manifest_io import (
    ManifestIOError,
    read_dataset_shard_manifest,
    read_execution_manifest,
    read_screening_plan,
    write_dataset_shard_manifest,
    write_execution_manifest,
    write_screening_plan,
)
from plural_cognition.training_data import TrainingDataConfig


def _config_hash() -> str:
    return training_data_config_sha256(TrainingDataConfig(base_seed=2))


def _manifest(split: str = "train", count: int = 10) -> DatasetShardManifest:
    return DatasetShardManifest(
        split,
        0,
        count,
        _config_hash(),
        ("b" if split == "train" else "c") * 64,
        count * 100,
    )


def _run():
    return resolve_run_intent(
        RunIntent("screen", "PC-4M", 1, 2),
        git_commit="d" * 40,
        precision="bf16",
        microbatch_examples=64,
        device_name="RTX 4060 Ti",
        preflight_sha256="e" * 64,
    )


def test_dataset_manifest_round_trip_is_canonical(tmp_path) -> None:
    path = tmp_path / "shard.manifest.json"
    write_dataset_shard_manifest(path, _manifest())

    assert read_dataset_shard_manifest(path) == _manifest()
    assert path.read_bytes().endswith(b"\n")
    assert not (tmp_path / "shard.manifest.json.tmp").exists()


def test_screening_plan_round_trip_reconstructs_exact_run(tmp_path) -> None:
    path = tmp_path / "screening-plan.json"
    write_screening_plan(path, (_run(),))

    assert read_screening_plan(path) == (_run(),)


def test_execution_manifest_round_trip_recomputes_derived_fields(tmp_path) -> None:
    run = _run()
    execution = ExecutionManifest(
        run,
        (
            DatasetShardManifest(
                "train", 0, 39_168, _config_hash(), "b" * 64, 8_000_000
            ),
        ),
        (
            DatasetShardManifest(
                "validation", 0, 512, _config_hash(), "c" * 64, 100_000
            ),
        ),
    )
    path = tmp_path / "execution.json"
    write_execution_manifest(path, execution)

    assert read_execution_manifest(path) == execution


def test_manifest_reader_rejects_noncanonical_whitespace(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"schema": "plural-cognition-dataset-shard-v1"}\n', encoding="ascii")

    with pytest.raises(ManifestIOError):
        read_dataset_shard_manifest(path)


def test_manifest_reader_rejects_duplicate_keys(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"a":1,"a":2}\n', encoding="ascii")

    with pytest.raises(ManifestIOError, match="duplicate"):
        read_dataset_shard_manifest(path)


def test_screening_plan_rejects_changed_manifest_hash(tmp_path) -> None:
    path = tmp_path / "screening-plan.json"
    write_screening_plan(path, (_run(),))
    raw = path.read_text(encoding="ascii")
    path.write_text(raw.replace(_run().sha256, "0" * 64), encoding="ascii")

    with pytest.raises(ManifestIOError):
        read_screening_plan(path)
