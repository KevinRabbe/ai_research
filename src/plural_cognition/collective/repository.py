"""Deterministic content-addressed repository snapshots for capable coding tasks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any

from .content_store import ContentStore, content_sha256, validate_sha256

REPOSITORY_SNAPSHOT_SCHEMA = "plural-cognition-repository-snapshot-v1"


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _validate_relative_path(value: str) -> None:
    if type(value) is not str or not value:
        raise ValueError("repository path must be a non-empty string")
    if "\\" in value:
        raise ValueError("repository paths must use POSIX separators")
    path = PurePosixPath(value)
    if path.is_absolute() or value != path.as_posix():
        raise ValueError("repository path must be normalized and relative")
    if any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("repository path contains unsafe components")
    if any(":" in part for part in path.parts):
        raise ValueError("repository path contains a platform-unsafe colon")


@dataclass(frozen=True, slots=True)
class RepositoryFile:
    path: str
    content_sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        _validate_relative_path(self.path)
        validate_sha256(self.content_sha256)
        if type(self.size_bytes) is not int or self.size_bytes < 0:
            raise ValueError("size_bytes must be a non-negative integer")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "content_sha256": self.content_sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    files: tuple[RepositoryFile, ...]

    def __post_init__(self) -> None:
        paths = tuple(item.path for item in self.files)
        if paths != tuple(sorted(paths)):
            raise ValueError("repository files must be sorted by path")
        if len(paths) != len(set(paths)):
            raise ValueError("repository snapshot contains duplicate paths")

    @property
    def total_bytes(self) -> int:
        return sum(item.size_bytes for item in self.files)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": REPOSITORY_SNAPSHOT_SCHEMA,
            "files": [item.canonical_payload() for item in self.files],
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class StoredRepositorySnapshot:
    snapshot: RepositorySnapshot
    manifest_sha256: str

    def __post_init__(self) -> None:
        validate_sha256(self.manifest_sha256)
        if self.manifest_sha256 != self.snapshot.sha256:
            raise ValueError("manifest_sha256 does not match repository snapshot")


def snapshot_directory(root: str | Path, store: ContentStore) -> StoredRepositorySnapshot:
    """Store every regular file beneath ``root`` and return a canonical tree manifest.

    Symlinks are rejected so a task snapshot cannot escape its declared repository
    root or depend on host-specific link targets.
    """

    root_path = Path(root)
    if not root_path.is_dir():
        raise ValueError("repository root must be an existing directory")
    if root_path.is_symlink():
        raise ValueError("repository root must not be a symlink")

    files: list[RepositoryFile] = []
    for path in sorted(root_path.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise ValueError(f"repository snapshot rejects symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"repository snapshot requires regular files: {path}")
        relative = path.relative_to(root_path).as_posix()
        _validate_relative_path(relative)
        data = path.read_bytes()
        digest = store.put_bytes(data)
        files.append(RepositoryFile(relative, digest, len(data)))

    snapshot = RepositorySnapshot(tuple(files))
    manifest_digest = store.put_bytes(snapshot.canonical_bytes())
    if manifest_digest != snapshot.sha256:
        raise AssertionError("repository snapshot manifest hash is inconsistent")
    return StoredRepositorySnapshot(snapshot, manifest_digest)


def load_repository_snapshot(
    manifest_sha256: str,
    store: ContentStore,
) -> RepositorySnapshot:
    """Decode and verify a repository snapshot from its content-addressed manifest."""

    validate_sha256(manifest_sha256)
    raw = store.get_bytes(manifest_sha256)
    if content_sha256(raw) != manifest_sha256:
        raise AssertionError("content store returned bytes under the wrong digest")
    try:
        payload = json.loads(raw.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid repository snapshot JSON") from exc
    if type(payload) is not dict or set(payload) != {"schema", "files"}:
        raise ValueError("repository snapshot has wrong fields")
    if payload["schema"] != REPOSITORY_SNAPSHOT_SCHEMA:
        raise ValueError("unsupported repository snapshot schema")
    if type(payload["files"]) is not list:
        raise ValueError("repository snapshot files must be a list")

    files: list[RepositoryFile] = []
    for index, raw_item in enumerate(payload["files"]):
        if type(raw_item) is not dict or set(raw_item) != {
            "path",
            "content_sha256",
            "size_bytes",
        }:
            raise ValueError(f"repository file entry {index} has wrong fields")
        files.append(
            RepositoryFile(
                raw_item["path"],
                raw_item["content_sha256"],
                raw_item["size_bytes"],
            )
        )
    snapshot = RepositorySnapshot(tuple(files))
    if snapshot.canonical_bytes() != raw or snapshot.sha256 != manifest_sha256:
        raise ValueError("repository snapshot is not canonical")
    return snapshot


def materialize_repository_snapshot(
    snapshot: RepositorySnapshot,
    destination: str | Path,
    store: ContentStore,
) -> None:
    """Materialize a verified snapshot into a new empty directory."""

    destination_path = Path(destination)
    if destination_path.exists():
        if not destination_path.is_dir():
            raise ValueError("snapshot destination exists and is not a directory")
        if any(destination_path.iterdir()):
            raise ValueError("snapshot destination must be empty")
    else:
        destination_path.mkdir(parents=True)

    resolved_root = destination_path.resolve()
    for item in snapshot.files:
        data = store.get_bytes(item.content_sha256)
        if len(data) != item.size_bytes:
            raise ValueError(f"stored file size mismatch for {item.path}")
        path = destination_path.joinpath(*PurePosixPath(item.path).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        resolved_path = path.resolve()
        if resolved_root not in resolved_path.parents:
            raise ValueError(f"repository path escapes destination: {item.path}")
        path.write_bytes(data)
