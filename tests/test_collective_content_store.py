from __future__ import annotations

from pathlib import Path

import pytest

from plural_cognition.collective.content_store import (
    ContentIntegrityError,
    ContentStoreError,
    FileContentStore,
    content_sha256,
)


def test_file_content_store_round_trip(tmp_path: Path) -> None:
    store = FileContentStore(tmp_path / "store")
    data = b"immutable bytes\n"
    digest = store.put_bytes(data)
    assert digest == content_sha256(data)
    assert store.contains(digest)
    assert store.get_bytes(digest) == data
    assert store.put_bytes(data) == digest


def test_file_content_store_rejects_corruption(tmp_path: Path) -> None:
    store = FileContentStore(tmp_path / "store")
    digest = store.put_bytes(b"good")
    path = store.root / "sha256" / digest[:2] / digest[2:]
    path.write_bytes(b"bad")
    with pytest.raises(ContentIntegrityError, match="corrupt"):
        store.get_bytes(digest)
    with pytest.raises(ContentIntegrityError, match="corrupt"):
        store.contains(digest)


def test_file_content_store_reports_missing_content(tmp_path: Path) -> None:
    store = FileContentStore(tmp_path / "store")
    digest = content_sha256(b"missing")
    assert not store.contains(digest)
    with pytest.raises(ContentStoreError, match="not found"):
        store.get_bytes(digest)


def test_content_sha256_requires_exact_bytes() -> None:
    with pytest.raises(TypeError, match="bytes"):
        content_sha256(bytearray(b"no"))  # type: ignore[arg-type]
