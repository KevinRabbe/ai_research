"""Strict canonical JSON IO for experiment and dataset manifests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .dataset_shard import DatasetShardManifest


class ManifestIOError(ValueError):
    pass


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ManifestIOError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def write_canonical_json(path: str | Path, payload: Any) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    data = canonical_json_bytes(payload)
    try:
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_canonical_json(path: str | Path) -> Any:
    raw = Path(path).read_bytes()
    if not raw.endswith(b"\n"):
        raise ManifestIOError("canonical JSON file must end with one newline")
    data = raw[:-1]
    try:
        payload = json.loads(data.decode("ascii"), object_pairs_hook=_strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestIOError("invalid canonical JSON file") from exc
    if canonical_json_bytes(payload) != data:
        raise ManifestIOError("JSON file is not in canonical form")
    return payload


def dataset_shard_manifest_from_payload(payload: Any) -> DatasetShardManifest:
    if not isinstance(payload, dict):
        raise ManifestIOError("dataset manifest must be an object")
    expected = {
        "schema",
        "split",
        "start_index",
        "example_count",
        "config_sha256",
        "records_sha256",
        "total_unpadded_tokens",
    }
    if set(payload) != expected:
        raise ManifestIOError("dataset manifest has wrong fields")
    if payload["schema"] != "plural-cognition-dataset-shard-v1":
        raise ManifestIOError("unsupported dataset manifest schema")
    try:
        return DatasetShardManifest(
            payload["split"],
            payload["start_index"],
            payload["example_count"],
            payload["config_sha256"],
            payload["records_sha256"],
            payload["total_unpadded_tokens"],
        )
    except (TypeError, ValueError) as exc:
        raise ManifestIOError("invalid dataset manifest") from exc


def write_dataset_shard_manifest(
    path: str | Path, manifest: DatasetShardManifest
) -> None:
    write_canonical_json(path, manifest.canonical_payload())


def read_dataset_shard_manifest(path: str | Path) -> DatasetShardManifest:
    return dataset_shard_manifest_from_payload(read_canonical_json(path))
