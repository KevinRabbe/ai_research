"""Checkpoint sidecars binding binary state to one complete execution manifest."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import torch

from .execution import ExecutionManifest
from .manifest_io import read_canonical_json, write_canonical_json
from .model import PluralDecoder
from .training import (
    CheckpointRecord,
    TrainingState,
    load_checkpoint,
    save_checkpoint,
)


@dataclass(frozen=True, slots=True)
class ExecutionCheckpointRecord:
    checkpoint: CheckpointRecord
    sidecar_path: str
    execution_sha256: str


def _file_sha256(path: str | Path) -> str:
    hasher = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _sidecar_path(path: str | Path) -> Path:
    checkpoint = Path(path)
    return checkpoint.with_name(checkpoint.name + ".manifest.json")


def save_execution_checkpoint(
    path: str | Path,
    *,
    model: PluralDecoder,
    optimizer: torch.optim.Optimizer,
    execution: ExecutionManifest,
    state: TrainingState,
    scaler: torch.amp.GradScaler | None = None,
) -> ExecutionCheckpointRecord:
    record = save_checkpoint(
        path,
        model=model,
        optimizer=optimizer,
        manifest=execution.run,
        state=state,
        scaler=scaler,
    )
    sidecar = _sidecar_path(path)
    payload = {
        "schema": "plural-cognition-execution-checkpoint-v1",
        "checkpoint_file": Path(path).name,
        "checkpoint_sha256": record.file_sha256,
        "run_sha256": execution.run.sha256,
        "execution_sha256": execution.sha256,
        "state": {
            "optimizer_steps": state.optimizer_steps,
            "processed_tokens": state.processed_tokens,
            "next_example_index": state.next_example_index,
        },
    }
    write_canonical_json(sidecar, payload)
    return ExecutionCheckpointRecord(record, str(sidecar), execution.sha256)


def load_execution_checkpoint(
    path: str | Path,
    *,
    model: PluralDecoder,
    optimizer: torch.optim.Optimizer,
    execution: ExecutionManifest,
    scaler: torch.amp.GradScaler | None = None,
    map_location: str | torch.device = "cpu",
) -> TrainingState:
    sidecar = _sidecar_path(path)
    payload = read_canonical_json(sidecar)
    expected_fields = {
        "schema",
        "checkpoint_file",
        "checkpoint_sha256",
        "run_sha256",
        "execution_sha256",
        "state",
    }
    if not isinstance(payload, dict) or set(payload) != expected_fields:
        raise ValueError("checkpoint sidecar has wrong fields")
    if payload["schema"] != "plural-cognition-execution-checkpoint-v1":
        raise ValueError("unsupported checkpoint sidecar schema")
    if payload["checkpoint_file"] != Path(path).name:
        raise ValueError("checkpoint sidecar names a different binary file")
    if payload["run_sha256"] != execution.run.sha256:
        raise ValueError("checkpoint sidecar belongs to a different resolved run")
    if payload["execution_sha256"] != execution.sha256:
        raise ValueError("checkpoint sidecar belongs to different dataset shards")
    if payload["checkpoint_sha256"] != _file_sha256(path):
        raise ValueError("checkpoint binary hash does not match sidecar")

    state = load_checkpoint(
        path,
        model=model,
        optimizer=optimizer,
        manifest=execution.run,
        scaler=scaler,
        map_location=map_location,
    )
    expected_state = {
        "optimizer_steps": state.optimizer_steps,
        "processed_tokens": state.processed_tokens,
        "next_example_index": state.next_example_index,
    }
    if payload["state"] != expected_state:
        raise ValueError("checkpoint sidecar state does not match binary state")
    return state
