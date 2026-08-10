from dataclasses import replace

import pytest

from plural_cognition.dataset_shard import (
    DatasetShardError,
    build_dataset_shard,
    read_dataset_shard,
    training_data_config_sha256,
)
from plural_cognition.training_data import TrainingDataConfig


def test_dataset_shard_round_trip_is_content_addressed(tmp_path) -> None:
    path = tmp_path / "train-000.jsonl"
    config = TrainingDataConfig(base_seed=17)
    manifest = build_dataset_shard(
        path,
        split="train",
        start_index=0,
        example_count=2,
        config=config,
    )
    examples = tuple(read_dataset_shard(path, manifest))

    assert len(examples) == 2
    assert manifest.config_sha256 == training_data_config_sha256(config)
    assert manifest.total_unpadded_tokens == sum(len(item.token_ids) for item in examples)
    assert len(manifest.sha256) == 64
    assert not (tmp_path / "train-000.jsonl.tmp").exists()


def test_dataset_shard_is_reproducible(tmp_path) -> None:
    config = TrainingDataConfig(base_seed=31)
    first_path = tmp_path / "first.jsonl"
    second_path = tmp_path / "second.jsonl"

    first = build_dataset_shard(
        first_path,
        split="validation",
        start_index=5,
        example_count=1,
        config=config,
    )
    second = build_dataset_shard(
        second_path,
        split="validation",
        start_index=5,
        example_count=1,
        config=config,
    )

    assert first == second
    assert first_path.read_bytes() == second_path.read_bytes()


def test_dataset_reader_rejects_tampering(tmp_path) -> None:
    path = tmp_path / "train.jsonl"
    manifest = build_dataset_shard(
        path,
        split="train",
        start_index=0,
        example_count=1,
    )
    contents = bytearray(path.read_bytes())
    contents[-2] = ord("0") if contents[-2] != ord("0") else ord("1")
    path.write_bytes(contents)

    with pytest.raises(DatasetShardError):
        tuple(read_dataset_shard(path, manifest))


def test_dataset_reader_rejects_wrong_manifest_count(tmp_path) -> None:
    path = tmp_path / "train.jsonl"
    manifest = build_dataset_shard(
        path,
        split="train",
        start_index=0,
        example_count=1,
    )

    with pytest.raises(DatasetShardError, match="record count"):
        tuple(read_dataset_shard(path, replace(manifest, example_count=2)))
