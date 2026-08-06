import pytest

from plural_cognition.dataset_shard import DatasetShardManifest
from plural_cognition.manifest_io import (
    ManifestIOError,
    read_dataset_shard_manifest,
    write_dataset_shard_manifest,
)


def _manifest() -> DatasetShardManifest:
    return DatasetShardManifest(
        "train",
        0,
        10,
        "a" * 64,
        "b" * 64,
        1000,
    )


def test_dataset_manifest_round_trip_is_canonical(tmp_path) -> None:
    path = tmp_path / "shard.manifest.json"
    write_dataset_shard_manifest(path, _manifest())

    assert read_dataset_shard_manifest(path) == _manifest()
    assert path.read_bytes().endswith(b"\n")
    assert not (tmp_path / "shard.manifest.json.tmp").exists()


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
