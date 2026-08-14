from __future__ import annotations

from pathlib import Path

import pytest

from plural_cognition.collective.content_store import FileContentStore
from plural_cognition.collective.repository import (
    RepositoryFile,
    RepositorySnapshot,
    load_repository_snapshot,
    materialize_repository_snapshot,
    snapshot_directory,
)


def test_repository_snapshot_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "pkg").mkdir(parents=True)
    (source / "pkg" / "a.py").write_text("VALUE = 1\n", encoding="utf-8")
    (source / "README.md").write_text("hello\n", encoding="utf-8")
    store = FileContentStore(tmp_path / "store")

    stored = snapshot_directory(source, store)
    assert tuple(item.path for item in stored.snapshot.files) == (
        "README.md",
        "pkg/a.py",
    )
    assert stored.snapshot.total_bytes > 0
    assert load_repository_snapshot(stored.manifest_sha256, store) == stored.snapshot

    destination = tmp_path / "materialized"
    materialize_repository_snapshot(stored.snapshot, destination, store)
    assert (destination / "pkg" / "a.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert (destination / "README.md").read_text(encoding="utf-8") == "hello\n"


def test_repository_snapshot_hash_is_independent_of_root_path(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    for root in (left, right):
        (root / "x.txt").write_bytes(b"same")
    store = FileContentStore(tmp_path / "store")
    assert snapshot_directory(left, store).manifest_sha256 == snapshot_directory(
        right, store
    ).manifest_sha256


def test_repository_snapshot_rejects_unsafe_paths() -> None:
    with pytest.raises(ValueError, match="unsafe"):
        RepositoryFile("../escape.py", "a" * 64, 1)
    with pytest.raises(ValueError, match="POSIX"):
        RepositoryFile("pkg\\x.py", "a" * 64, 1)


def test_repository_snapshot_requires_sorted_unique_files() -> None:
    first = RepositoryFile("a.py", "a" * 64, 1)
    second = RepositoryFile("b.py", "b" * 64, 1)
    with pytest.raises(ValueError, match="sorted"):
        RepositorySnapshot((second, first))
    with pytest.raises(ValueError, match="duplicate"):
        RepositorySnapshot((first, first))


def test_materialization_requires_empty_destination(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "x.txt").write_bytes(b"x")
    store = FileContentStore(tmp_path / "store")
    snapshot = snapshot_directory(source, store).snapshot
    destination = tmp_path / "destination"
    destination.mkdir()
    (destination / "existing.txt").write_bytes(b"no")
    with pytest.raises(ValueError, match="empty"):
        materialize_repository_snapshot(snapshot, destination, store)


def test_snapshot_rejects_symlink_when_supported(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = tmp_path / "target.txt"
    target.write_text("outside", encoding="utf-8")
    link = source / "link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")
    store = FileContentStore(tmp_path / "store")
    with pytest.raises(ValueError, match="symlink"):
        snapshot_directory(source, store)
