"""Atomic, content-addressed dataset shards for repeatable model comparisons."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterator

from .boolean_world.codec import CausalExample, VOCAB_SIZE
from .training_data import (
    DataSplit,
    TrainingDataConfig,
    example_at,
)


class DatasetShardError(ValueError):
    pass


def training_data_config_payload(config: TrainingDataConfig) -> dict:
    return {
        "base_seed": config.base_seed,
        "catalog_size": config.catalog_size,
        "generation": asdict(config.generation),
        "evidence": asdict(config.evidence),
        "max_tokens": config.max_tokens,
    }


def training_data_config_sha256(config: TrainingDataConfig) -> str:
    encoded = json.dumps(
        training_data_config_payload(config),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class DatasetShardManifest:
    split: DataSplit
    start_index: int
    example_count: int
    config_sha256: str
    records_sha256: str
    total_unpadded_tokens: int

    def __post_init__(self) -> None:
        if self.split not in ("train", "validation", "test"):
            raise ValueError("invalid dataset split")
        if self.start_index < 0 or self.example_count < 1:
            raise ValueError("dataset index and count are invalid")
        for name in ("config_sha256", "records_sha256"):
            value = getattr(self, name)
            if len(value) != 64:
                raise ValueError(f"{name} must contain 64 hexadecimal characters")
            try:
                int(value, 16)
            except ValueError as exc:
                raise ValueError(f"{name} must be hexadecimal") from exc
        if self.total_unpadded_tokens < self.example_count:
            raise ValueError("total_unpadded_tokens is inconsistent")

    def canonical_payload(self) -> dict:
        return {
            "schema": "plural-cognition-dataset-shard-v1",
            "split": self.split,
            "start_index": self.start_index,
            "example_count": self.example_count,
            "config_sha256": self.config_sha256,
            "records_sha256": self.records_sha256,
            "total_unpadded_tokens": self.total_unpadded_tokens,
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


def _record_bytes(index: int, seed: int, example: CausalExample) -> bytes:
    payload = {
        "index": index,
        "seed": seed,
        "token_ids": list(example.token_ids),
        "label_mask": list(example.label_mask),
        "answer_start": example.answer_start,
    }
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def build_dataset_shard(
    path: str | Path,
    *,
    split: DataSplit,
    start_index: int,
    example_count: int,
    config: TrainingDataConfig | None = None,
) -> DatasetShardManifest:
    """Build one shard atomically and return its content-addressed manifest."""

    if start_index < 0 or example_count < 1:
        raise ValueError("start_index must be non-negative and example_count positive")
    effective = config or TrainingDataConfig()
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    hasher = sha256()
    total_tokens = 0

    try:
        with temporary.open("wb") as handle:
            for index in range(start_index, start_index + example_count):
                supervised = example_at(split, index, effective)
                causal = supervised.causal(max_tokens=effective.max_tokens)
                line = _record_bytes(index, supervised.seed, causal)
                handle.write(line)
                handle.write(b"\n")
                hasher.update(line)
                hasher.update(b"\n")
                total_tokens += len(causal.token_ids)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()

    return DatasetShardManifest(
        split,
        start_index,
        example_count,
        training_data_config_sha256(effective),
        hasher.hexdigest(),
        total_tokens,
    )


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DatasetShardError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_dataset_shard(
    path: str | Path,
    manifest: DatasetShardManifest,
) -> Iterator[CausalExample]:
    """Read and verify every record before yielding it."""

    hasher = sha256()
    expected_index = manifest.start_index
    total_tokens = 0
    seen = 0
    with Path(path).open("rb") as handle:
        for raw_line in handle:
            hasher.update(raw_line)
            if not raw_line.endswith(b"\n"):
                raise DatasetShardError("dataset record is not newline terminated")
            line = raw_line[:-1]
            try:
                payload = json.loads(
                    line.decode("ascii"),
                    object_pairs_hook=_strict_object,
                )
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise DatasetShardError("invalid canonical dataset record") from exc
            if json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("ascii") != line:
                raise DatasetShardError("dataset record is not canonical JSON")
            if set(payload) != {
                "index",
                "seed",
                "token_ids",
                "label_mask",
                "answer_start",
            }:
                raise DatasetShardError("dataset record has wrong fields")
            if payload["index"] != expected_index:
                raise DatasetShardError("dataset record index is not contiguous")
            token_ids = payload["token_ids"]
            label_mask = payload["label_mask"]
            if (
                not isinstance(token_ids, list)
                or not token_ids
                or any(type(token) is not int or not 0 <= token < VOCAB_SIZE for token in token_ids)
            ):
                raise DatasetShardError("dataset token_ids are invalid")
            if (
                not isinstance(label_mask, list)
                or len(label_mask) != len(token_ids)
                or any(type(value) is not bool for value in label_mask)
            ):
                raise DatasetShardError("dataset label_mask is invalid")
            try:
                example = CausalExample(
                    tuple(token_ids),
                    tuple(label_mask),
                    payload["answer_start"],
                )
            except (TypeError, ValueError) as exc:
                raise DatasetShardError("dataset causal example is invalid") from exc
            yield example
            total_tokens += len(example.token_ids)
            seen += 1
            expected_index += 1

    if seen != manifest.example_count:
        raise DatasetShardError("dataset record count does not match manifest")
    if total_tokens != manifest.total_unpadded_tokens:
        raise DatasetShardError("dataset token count does not match manifest")
    if hasher.hexdigest() != manifest.records_sha256:
        raise DatasetShardError("dataset content hash does not match manifest")
