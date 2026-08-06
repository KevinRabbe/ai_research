"""Strict canonical JSON IO for experiment, dataset, and execution manifests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Sequence

from .dataset_shard import DatasetShardManifest
from .execution import ExecutionManifest
from .experiment import (
    OptimizerIntent,
    ResolvedRunManifest,
    RunIntent,
    resolve_run_intent,
)


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
        manifest = DatasetShardManifest(
            payload["split"],
            payload["start_index"],
            payload["example_count"],
            payload["config_sha256"],
            payload["records_sha256"],
            payload["total_unpadded_tokens"],
        )
    except (TypeError, ValueError) as exc:
        raise ManifestIOError("invalid dataset manifest") from exc
    if manifest.canonical_payload() != payload:
        raise ManifestIOError("dataset manifest is not canonical")
    return manifest


def _optimizer_from_payload(payload: Any) -> OptimizerIntent:
    if not isinstance(payload, dict):
        raise ManifestIOError("optimizer intent must be an object")
    expected = {
        "learning_rate",
        "beta1",
        "beta2",
        "weight_decay",
        "gradient_clip_norm",
        "warmup_tokens",
        "minimum_lr_ratio",
    }
    if set(payload) != expected:
        raise ManifestIOError("optimizer intent has wrong fields")
    try:
        optimizer = OptimizerIntent(**payload)
    except (TypeError, ValueError) as exc:
        raise ManifestIOError("invalid optimizer intent") from exc
    if optimizer.__dict__ if hasattr(optimizer, "__dict__") else False:
        raise AssertionError("slotted optimizer intent unexpectedly has __dict__")
    return optimizer


def run_intent_from_payload(payload: Any) -> RunIntent:
    if not isinstance(payload, dict):
        raise ManifestIOError("run intent must be an object")
    expected = {
        "schema",
        "experiment_name",
        "model",
        "initialization_seed",
        "data_seed",
        "token_budget",
        "sequence_length",
        "target_tokens_per_optimizer_step",
        "validation_examples",
        "checkpoint_tokens",
        "optimizer",
    }
    if set(payload) != expected or payload.get("schema") != "plural-cognition-run-intent-v1":
        raise ManifestIOError("run intent has wrong fields or schema")
    try:
        intent = RunIntent(
            payload["experiment_name"],
            payload["model"]["name"],
            payload["initialization_seed"],
            payload["data_seed"],
            payload["token_budget"],
            payload["sequence_length"],
            payload["target_tokens_per_optimizer_step"],
            payload["validation_examples"],
            tuple(payload["checkpoint_tokens"]),
            _optimizer_from_payload(payload["optimizer"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ManifestIOError("invalid run intent") from exc
    if intent.canonical_payload() != payload:
        raise ManifestIOError("run intent model contract or canonical payload differs")
    return intent


def resolved_run_manifest_from_payload(payload: Any) -> ResolvedRunManifest:
    if not isinstance(payload, dict):
        raise ManifestIOError("resolved run manifest must be an object")
    expected = {
        "schema",
        "intent",
        "intent_sha256",
        "run_id",
        "git_commit",
        "precision",
        "microbatch_examples",
        "gradient_accumulation_steps",
        "effective_tokens_per_optimizer_step",
        "device_name",
        "preflight_sha256",
    }
    if set(payload) != expected or payload.get("schema") != "plural-cognition-resolved-run-v1":
        raise ManifestIOError("resolved run manifest has wrong fields or schema")
    intent = run_intent_from_payload(payload["intent"])
    if payload["intent_sha256"] != intent.sha256 or payload["run_id"] != intent.run_id:
        raise ManifestIOError("resolved run intent identity is inconsistent")
    try:
        manifest = resolve_run_intent(
            intent,
            git_commit=payload["git_commit"],
            precision=payload["precision"],
            microbatch_examples=payload["microbatch_examples"],
            device_name=payload["device_name"],
            preflight_sha256=payload["preflight_sha256"],
        )
    except (TypeError, ValueError) as exc:
        raise ManifestIOError("invalid resolved run manifest") from exc
    if manifest.canonical_payload() != payload:
        raise ManifestIOError("resolved run geometry or canonical payload differs")
    return manifest


def screening_plan_payload(
    runs: Sequence[ResolvedRunManifest],
) -> dict[str, Any]:
    if not runs:
        raise ValueError("screening plan requires at least one run")
    if len({run.intent.sha256 for run in runs}) != len(runs):
        raise ValueError("screening plan contains duplicate run intents")
    return {
        "schema": "plural-cognition-screening-plan-v1",
        "runs": [
            {
                "manifest": run.canonical_payload(),
                "manifest_sha256": run.sha256,
            }
            for run in runs
        ],
    }


def screening_plan_from_payload(payload: Any) -> tuple[ResolvedRunManifest, ...]:
    if not isinstance(payload, dict) or set(payload) != {"schema", "runs"}:
        raise ManifestIOError("screening plan has wrong fields")
    if payload["schema"] != "plural-cognition-screening-plan-v1":
        raise ManifestIOError("unsupported screening plan schema")
    if not isinstance(payload["runs"], list) or not payload["runs"]:
        raise ManifestIOError("screening plan must contain runs")
    runs: list[ResolvedRunManifest] = []
    for item in payload["runs"]:
        if not isinstance(item, dict) or set(item) != {"manifest", "manifest_sha256"}:
            raise ManifestIOError("screening plan run entry has wrong fields")
        run = resolved_run_manifest_from_payload(item["manifest"])
        if item["manifest_sha256"] != run.sha256:
            raise ManifestIOError("screening plan run hash is inconsistent")
        runs.append(run)
    if len({run.intent.sha256 for run in runs}) != len(runs):
        raise ManifestIOError("screening plan contains duplicate run intents")
    return tuple(runs)


def _execution_shard_from_payload(payload: Any) -> DatasetShardManifest:
    if not isinstance(payload, dict) or "manifest_sha256" not in payload:
        raise ManifestIOError("execution shard entry is malformed")
    core = {key: value for key, value in payload.items() if key != "manifest_sha256"}
    shard = dataset_shard_manifest_from_payload(core)
    if payload["manifest_sha256"] != shard.sha256:
        raise ManifestIOError("execution shard manifest hash is inconsistent")
    return shard


def execution_manifest_from_payload(payload: Any) -> ExecutionManifest:
    if not isinstance(payload, dict):
        raise ManifestIOError("execution manifest must be an object")
    expected = {
        "schema",
        "run",
        "run_sha256",
        "data_config_sha256",
        "optimizer_steps",
        "effective_training_tokens",
        "examples_per_optimizer_step",
        "required_training_examples",
        "training_shards",
        "validation_shards",
    }
    if set(payload) != expected or payload.get("schema") != "plural-cognition-execution-manifest-v1":
        raise ManifestIOError("execution manifest has wrong fields or schema")
    run = resolved_run_manifest_from_payload(payload["run"])
    if payload["run_sha256"] != run.sha256:
        raise ManifestIOError("execution run hash is inconsistent")
    try:
        training = tuple(_execution_shard_from_payload(item) for item in payload["training_shards"])
        validation = tuple(_execution_shard_from_payload(item) for item in payload["validation_shards"])
        execution = ExecutionManifest(run, training, validation)
    except (TypeError, ValueError) as exc:
        raise ManifestIOError("invalid execution manifest") from exc
    if execution.canonical_payload() != payload:
        raise ManifestIOError("execution manifest derived fields are inconsistent")
    return execution


def write_dataset_shard_manifest(
    path: str | Path, manifest: DatasetShardManifest
) -> None:
    write_canonical_json(path, manifest.canonical_payload())


def read_dataset_shard_manifest(path: str | Path) -> DatasetShardManifest:
    return dataset_shard_manifest_from_payload(read_canonical_json(path))


def write_screening_plan(
    path: str | Path, runs: Sequence[ResolvedRunManifest]
) -> None:
    write_canonical_json(path, screening_plan_payload(runs))


def read_screening_plan(path: str | Path) -> tuple[ResolvedRunManifest, ...]:
    return screening_plan_from_payload(read_canonical_json(path))


def write_execution_manifest(path: str | Path, execution: ExecutionManifest) -> None:
    write_canonical_json(path, execution.canonical_payload())


def read_execution_manifest(path: str | Path) -> ExecutionManifest:
    return execution_manifest_from_payload(read_canonical_json(path))
