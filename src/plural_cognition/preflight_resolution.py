"""Resolve immutable screening runs from one measured CUDA preflight report."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from .experiment import (
    ResolvedRunManifest,
    default_screening_plan,
    resolve_run_intent,
)


class PreflightResolutionError(ValueError):
    pass


def _file_sha256(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _load_report(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreflightResolutionError("invalid CUDA preflight JSON") from exc
    if not isinstance(payload, dict):
        raise PreflightResolutionError("CUDA preflight report must be an object")
    required = {
        "schema_version",
        "mode",
        "git_commit",
        "precision",
        "hardware",
        "results",
    }
    if not required.issubset(payload):
        raise PreflightResolutionError("CUDA preflight report is missing required fields")
    if payload["schema_version"] != 1 or payload["mode"] != "cuda_training_preflight":
        raise PreflightResolutionError("unsupported CUDA preflight schema or mode")
    git_commit = payload["git_commit"]
    if not isinstance(git_commit, str) or len(git_commit) != 40:
        raise PreflightResolutionError("CUDA preflight must contain a full Git commit")
    try:
        int(git_commit, 16)
    except ValueError as exc:
        raise PreflightResolutionError("CUDA preflight Git commit is not hexadecimal") from exc
    if payload["precision"] not in ("bf16", "fp16"):
        raise PreflightResolutionError("CUDA preflight precision is unsupported")
    hardware = payload["hardware"]
    if not isinstance(hardware, dict) or not isinstance(hardware.get("gpu_name"), str):
        raise PreflightResolutionError("CUDA preflight hardware metadata is invalid")
    if not isinstance(payload["results"], list):
        raise PreflightResolutionError("CUDA preflight results must be a list")
    return payload


def _selected_case(
    report: dict[str, Any],
    *,
    model_name: str,
    sequence_length: int,
    target_tokens_per_step: int,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for raw in report["results"]:
        if not isinstance(raw, dict):
            continue
        if raw.get("model_name") != model_name:
            continue
        if raw.get("sequence_length") != sequence_length:
            continue
        if raw.get("status") != "ok" or raw.get("within_vram_limit") is not True:
            continue
        microbatch = raw.get("microbatch")
        throughput = raw.get("tokens_per_second")
        if type(microbatch) is not int or microbatch < 1:
            continue
        if type(throughput) not in (int, float) or float(throughput) <= 0:
            continue
        tokens_per_microbatch = microbatch * sequence_length
        if tokens_per_microbatch > target_tokens_per_step:
            continue
        if target_tokens_per_step % tokens_per_microbatch:
            continue
        candidates.append(raw)
    if not candidates:
        raise PreflightResolutionError(
            f"no valid measured configuration for {model_name} at sequence {sequence_length}"
        )
    return max(
        candidates,
        key=lambda item: (
            float(item["tokens_per_second"]),
            int(item["microbatch"]),
        ),
    )


def resolve_screening_plan_from_preflight(
    path: str | Path,
    *,
    initialization_seeds: tuple[int, ...] = (101, 102),
    data_seed: int = 20260806,
) -> tuple[ResolvedRunManifest, ...]:
    """Resolve all six screening runs from measured, matched-compute cases."""

    source = Path(path)
    report = _load_report(source)
    digest = _file_sha256(source)
    intents = default_screening_plan(
        initialization_seeds=initialization_seeds,
        data_seed=data_seed,
    )
    selected_by_model: dict[str, dict[str, Any]] = {}
    for intent in intents:
        selected_by_model.setdefault(
            intent.model_name,
            _selected_case(
                report,
                model_name=intent.model_name,
                sequence_length=intent.sequence_length,
                target_tokens_per_step=intent.target_tokens_per_optimizer_step,
            ),
        )
    return tuple(
        resolve_run_intent(
            intent,
            git_commit=report["git_commit"],
            precision=report["precision"],
            microbatch_examples=int(selected_by_model[intent.model_name]["microbatch"]),
            device_name=report["hardware"]["gpu_name"],
            preflight_sha256=digest,
        )
        for intent in intents
    )
