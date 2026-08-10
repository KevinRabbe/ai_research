"""Content-addressed byte storage for solver-visible and immutable artifacts."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Protocol, runtime_checkable


class ContentStoreError(RuntimeError):
    """Base error for content-addressed storage failures."""


class ContentIntegrityError(ContentStoreError):
    """Raised when stored bytes do not match their requested SHA-256 identity."""


def validate_sha256(digest: str) -> None:
    if type(digest) is not str or len(digest) != 64:
        raise ValueError("digest must contain 64 lowercase hexadecimal characters")
    try:
        int(digest, 16)
    except ValueError as exc:
        raise ValueError("digest must be hexadecimal") from exc
    if digest != digest.lower():
        raise ValueError("digest must use lowercase hexadecimal")


def content_sha256(data: bytes) -> str:
    if type(data) is not bytes:
        raise TypeError("content must be bytes")
    return sha256(data).hexdigest()


@runtime_checkable
class ContentStore(Protocol):
    """Minimal storage boundary used by model backends and task materializers."""

    def put_bytes(self, data: bytes) -> str:
        ...

    def get_bytes(self, digest: str) -> bytes:
        ...

    def contains(self, digest: str) -> bool:
        ...


@dataclass(slots=True)
class FileContentStore:
    """Filesystem-backed SHA-256 store with atomic writes and read verification."""

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir():
            raise ContentStoreError("content-store root is not a directory")

    def _path(self, digest: str) -> Path:
        validate_sha256(digest)
        return self.root / "sha256" / digest[:2] / digest[2:]

    def put_bytes(self, data: bytes) -> str:
        digest = content_sha256(data)
        destination = self._path(digest)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.exists():
            existing = destination.read_bytes()
            if content_sha256(existing) != digest:
                raise ContentIntegrityError(
                    f"existing content is corrupt for digest {digest}"
                )
            if existing != data:
                raise AssertionError("SHA-256 identity collision detected")
            return digest

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{digest[:12]}-",
                suffix=".tmp",
                dir=destination.parent,
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, destination)
            temporary_path = None
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

        stored = destination.read_bytes()
        if content_sha256(stored) != digest:
            raise ContentIntegrityError(
                f"stored content failed post-write verification for digest {digest}"
            )
        return digest

    def get_bytes(self, digest: str) -> bytes:
        path = self._path(digest)
        try:
            data = path.read_bytes()
        except FileNotFoundError as exc:
            raise ContentStoreError(f"content not found: {digest}") from exc
        if content_sha256(data) != digest:
            raise ContentIntegrityError(f"content is corrupt for digest {digest}")
        return data

    def contains(self, digest: str) -> bool:
        path = self._path(digest)
        if not path.exists():
            return False
        if not path.is_file():
            raise ContentIntegrityError(f"content path is not a file for digest {digest}")
        data = path.read_bytes()
        if content_sha256(data) != digest:
            raise ContentIntegrityError(f"content is corrupt for digest {digest}")
        return True
