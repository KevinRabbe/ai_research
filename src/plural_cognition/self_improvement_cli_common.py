"""Shared fail-closed utilities for SI-V1 command-line execution."""

from __future__ import annotations

import subprocess
from hashlib import sha256
from pathlib import Path
from typing import Iterator, Sequence

import torch

from .boolean_world.codec import EOS_ID, CausalExample, decode_public_task
from .checkpoint_bundle import load_execution_checkpoint
from .dataset_shard import DatasetShardManifest, read_dataset_shard
from .execution import ExecutionManifest
from .manifest_io import read_dataset_shard_manifest
from .model import PluralDecoder
from .training import build_optimizer


class SelfImprovementCommandError(RuntimeError):
    pass


def file_sha256(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def current_git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        raise SelfImprovementCommandError(
            "cannot determine current Git commit"
        ) from exc
    commit = completed.stdout.strip()
    if len(commit) != 40:
        raise SelfImprovementCommandError("current Git commit is not a full SHA")
    try:
        int(commit, 16)
    except ValueError as exc:
        raise SelfImprovementCommandError("current Git commit is not hexadecimal") from exc
    return commit


def read_shard_bindings(
    values: Sequence[Sequence[str]],
) -> tuple[tuple[Path, DatasetShardManifest], ...]:
    bindings: list[tuple[Path, DatasetShardManifest]] = []
    for pair in values:
        if len(pair) != 2:
            raise SelfImprovementCommandError(
                "each shard binding requires DATA and MANIFEST"
            )
        data_path, manifest_path = map(Path, pair)
        if not data_path.is_file():
            raise SelfImprovementCommandError(
                f"dataset shard does not exist: {data_path}"
            )
        bindings.append((data_path, read_dataset_shard_manifest(manifest_path)))
    if not bindings:
        raise SelfImprovementCommandError("at least one shard binding is required")
    manifests = tuple(manifest for _, manifest in bindings)
    if manifests != tuple(sorted(manifests, key=lambda item: item.start_index)):
        raise SelfImprovementCommandError("shard bindings must be sorted by start_index")
    expected_start = manifests[0].start_index
    config_hash = manifests[0].config_sha256
    split = manifests[0].split
    for manifest in manifests:
        if manifest.start_index != expected_start:
            raise SelfImprovementCommandError("shard ranges must be contiguous")
        if manifest.config_sha256 != config_hash:
            raise SelfImprovementCommandError(
                "all bound shards must share one data configuration"
            )
        if manifest.split != split:
            raise SelfImprovementCommandError("all bound shards must share one split")
        expected_start += manifest.example_count
    return tuple(bindings)


def verify_shard_contents(
    bindings: tuple[tuple[Path, DatasetShardManifest], ...],
) -> None:
    for path, manifest in bindings:
        count = sum(1 for _ in read_dataset_shard(path, manifest))
        if count != manifest.example_count:
            raise AssertionError("verified shard count differs from manifest")


def iter_examples(
    bindings: tuple[tuple[Path, DatasetShardManifest], ...],
) -> Iterator[CausalExample]:
    for path, manifest in bindings:
        yield from read_dataset_shard(path, manifest)


def shard_manifest_sha256s(
    bindings: tuple[tuple[Path, DatasetShardManifest], ...],
) -> tuple[str, ...]:
    return tuple(manifest.sha256 for _, manifest in bindings)


def public_task_from_causal(example: CausalExample):
    """Decode only the model-visible prefix; never parse the answer target."""

    task_ids = (*example.token_ids[: example.answer_start], EOS_ID)
    return decode_public_task(task_ids)


def validate_generation_environment(
    execution: ExecutionManifest,
    preflight: Path,
) -> torch.device:
    """Validate the frozen training environment without requiring its Git checkout.

    The checkpoint remains bound to its original execution and preflight hashes.
    SI candidate generation may run from a later qualified tooling commit, which
    is recorded independently in every target-free generation artifact.
    """

    if file_sha256(preflight) != execution.run.preflight_sha256:
        raise SelfImprovementCommandError(
            "CUDA preflight file hash differs from the execution manifest"
        )
    if not torch.cuda.is_available():
        raise SelfImprovementCommandError(
            "CUDA is unavailable; target candidate generation requires the measured GPU"
        )
    device = torch.device("cuda")
    device_name = torch.cuda.get_device_properties(0).name
    if device_name != execution.run.device_name:
        raise SelfImprovementCommandError(
            f"CUDA device differs from the measured device: {device_name!r}"
        )
    if execution.run.precision == "bf16" and not torch.cuda.is_bf16_supported():
        raise SelfImprovementCommandError(
            "resolved BF16 execution is unsupported by the current CUDA device"
        )
    return device


def load_frozen_checkpoint(
    execution: ExecutionManifest,
    checkpoint: Path,
    *,
    device: torch.device,
) -> PluralDecoder:
    model = PluralDecoder(execution.run.intent.model_config).to(device)
    optimizer = build_optimizer(model, execution.run.intent.optimizer)
    scaler = (
        torch.amp.GradScaler("cuda", enabled=True)
        if execution.run.precision == "fp16"
        else None
    )
    load_execution_checkpoint(
        checkpoint,
        model=model,
        optimizer=optimizer,
        execution=execution,
        scaler=scaler,
        map_location=device,
    )
    model.eval()
    return model
