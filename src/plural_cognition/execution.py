"""Content-addressed execution bundles binding runs to exact dataset shards."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from math import ceil

from .dataset_shard import DatasetShardManifest
from .experiment import ResolvedRunManifest


@dataclass(frozen=True, slots=True)
class ExecutionManifest:
    run: ResolvedRunManifest
    training_shards: tuple[DatasetShardManifest, ...]
    validation_shards: tuple[DatasetShardManifest, ...]

    def __post_init__(self) -> None:
        if not self.training_shards or not self.validation_shards:
            raise ValueError("execution requires training and validation shards")
        self._validate_shards(self.training_shards, "train")
        self._validate_shards(self.validation_shards, "validation")
        config_hashes = {
            shard.config_sha256
            for shard in (*self.training_shards, *self.validation_shards)
        }
        if len(config_hashes) != 1:
            raise ValueError("all execution shards must share one data configuration")
        if self.training_example_count < self.required_training_examples:
            raise ValueError(
                "training shards do not cover the complete matched-compute run"
            )
        if self.validation_example_count < self.run.intent.validation_examples:
            raise ValueError("validation shards do not cover the frozen evaluation set")

    @staticmethod
    def _validate_shards(
        shards: tuple[DatasetShardManifest, ...], expected_split: str
    ) -> None:
        if tuple(sorted(shards, key=lambda item: item.start_index)) != shards:
            raise ValueError("dataset shards must be sorted by start_index")
        expected_start = shards[0].start_index
        for shard in shards:
            if shard.split != expected_split:
                raise ValueError(f"expected {expected_split} dataset shard")
            if shard.start_index != expected_start:
                raise ValueError("dataset shard ranges must be contiguous")
            expected_start += shard.example_count

    @property
    def optimizer_steps(self) -> int:
        return ceil(
            self.run.intent.token_budget
            / self.run.intent.target_tokens_per_optimizer_step
        )

    @property
    def effective_training_tokens(self) -> int:
        return self.optimizer_steps * self.run.intent.target_tokens_per_optimizer_step

    @property
    def examples_per_optimizer_step(self) -> int:
        return (
            self.run.intent.target_tokens_per_optimizer_step
            // self.run.intent.sequence_length
        )

    @property
    def required_training_examples(self) -> int:
        return self.optimizer_steps * self.examples_per_optimizer_step

    @property
    def training_example_count(self) -> int:
        return sum(shard.example_count for shard in self.training_shards)

    @property
    def validation_example_count(self) -> int:
        return sum(shard.example_count for shard in self.validation_shards)

    @property
    def data_config_sha256(self) -> str:
        return self.training_shards[0].config_sha256

    def canonical_payload(self) -> dict:
        return {
            "schema": "plural-cognition-execution-manifest-v1",
            "run": self.run.canonical_payload(),
            "run_sha256": self.run.sha256,
            "data_config_sha256": self.data_config_sha256,
            "optimizer_steps": self.optimizer_steps,
            "effective_training_tokens": self.effective_training_tokens,
            "examples_per_optimizer_step": self.examples_per_optimizer_step,
            "required_training_examples": self.required_training_examples,
            "training_shards": [
                {
                    **shard.canonical_payload(),
                    "manifest_sha256": shard.sha256,
                }
                for shard in self.training_shards
            ],
            "validation_shards": [
                {
                    **shard.canonical_payload(),
                    "manifest_sha256": shard.sha256,
                }
                for shard in self.validation_shards
            ],
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
