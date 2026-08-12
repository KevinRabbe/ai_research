"""Corrected target-machine load qualification with explicit offload-log visibility."""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from .local_model_load_preflight import (
    DEFAULT_CONTEXT_TOKENS,
    DEFAULT_PREDICT_TOKENS,
    DEFAULT_TIMEOUT_SECONDS,
    _atomic_write,
    _canonical_json_bytes,
    _download_model,
    _git_revision,
    _run_load,
    _runtime_observation,
    _verify_runtime_archives,
)
from .local_models import LOCAL_MODEL_SOURCE_FREEZE_V2

REPORT_SCHEMA = "plural-cognition-local-model-load-preflight-v2"
LOG_VERBOSITY = 4


def _load_command(
    cli: Path,
    model_path: Path,
    *,
    context_tokens: int,
    predict_tokens: int,
) -> tuple[str, ...]:
    return (
        str(cli),
        "-m",
        str(model_path),
        "-c",
        str(context_tokens),
        "-n",
        str(predict_tokens),
        "-ngl",
        "all",
        "-dev",
        "CUDA0",
        "-fit",
        "off",
        "-sm",
        "none",
        "-mg",
        "0",
        "-ctk",
        "f16",
        "-ctv",
        "f16",
        "-lm",
        "mmap",
        "--offline",
        "--temp",
        "0",
        "--seed",
        "1",
        "--no-display-prompt",
        "--log-colors",
        "off",
        "--no-log-timestamps",
        "--log-verbosity",
        str(LOG_VERBOSITY),
        "--perf",
        "-st",
        "-p",
        "Respond with one short sentence confirming that local inference is running.",
    )


def run(
    *,
    candidate_id: str,
    runtime_root: Path,
    model_root: Path,
    artifact_root: Path,
    context_tokens: int,
    predict_tokens: int,
    timeout_seconds: int,
) -> dict[str, object]:
    if artifact_root.exists():
        raise RuntimeError(f"evidence path already exists: {artifact_root}")
    if context_tokens < 1 or predict_tokens < 1 or timeout_seconds < 1:
        raise ValueError("context, predict, and timeout values must be positive")

    freeze = LOCAL_MODEL_SOURCE_FREEZE_V2
    candidate = freeze.candidate(candidate_id)
    revision = _git_revision()

    print("verifying_runtime_archives=true", flush=True)
    _verify_runtime_archives(runtime_root)
    cli = runtime_root / "bin" / "llama-cli.exe"
    runtime_observation = _runtime_observation(cli)

    model_path = model_root / candidate.candidate_id / candidate.filename
    print(
        f"model_artifact={candidate.candidate_id} bytes={candidate.size_bytes}",
        flush=True,
    )
    download_status = _download_model(candidate, model_path)
    print(f"model_artifact_verified={candidate.artifact_sha256}", flush=True)

    command = _load_command(
        cli,
        model_path,
        context_tokens=context_tokens,
        predict_tokens=predict_tokens,
    )
    load, stdout, stderr = _run_load(command, timeout_seconds=timeout_seconds)

    payload: dict[str, object] = {
        "schema": REPORT_SCHEMA,
        "status": "LOCAL_MODEL_LOAD_PASS",
        "software_revision": revision,
        "model_source_freeze_sha256": freeze.sha256,
        "model_source_observed_manifest_sha256": freeze.observed_manifest_sha256,
        "runtime_sha256": freeze.runtime.sha256,
        "candidate": candidate.canonical_payload(),
        "candidate_source_sha256": candidate.sha256,
        "download_status": download_status,
        "model_file_sha256": candidate.artifact_sha256,
        "model_file_size_bytes": candidate.size_bytes,
        "protocol": {
            "context_tokens": context_tokens,
            "predict_tokens": predict_tokens,
            "gpu_layers": "all",
            "device": "CUDA0",
            "fit": "off",
            "split_mode": "none",
            "main_gpu": 0,
            "cache_type_k": "f16",
            "cache_type_v": "f16",
            "load_mode": "mmap",
            "offline": True,
            "temperature": 0,
            "seed": 1,
            "single_turn": True,
            "log_verbosity": LOG_VERBOSITY,
        },
        "runtime_observation": asdict(runtime_observation),
        "load_observation": asdict(load),
    }
    report_sha = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    payload["report_sha256"] = report_sha

    artifact_root.mkdir(parents=True)
    (artifact_root / "stdout.bin").write_bytes(stdout)
    (artifact_root / "stderr.bin").write_bytes(stderr)
    _atomic_write(artifact_root / "load-preflight.json", payload)
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run corrected frozen local capable-model load preflight v2."
    )
    parser.add_argument("--candidate", default="qwen3-8b-q8")
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--context-tokens", type=int, default=DEFAULT_CONTEXT_TOKENS)
    parser.add_argument("--predict-tokens", type=int, default=DEFAULT_PREDICT_TOKENS)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = run(
            candidate_id=args.candidate,
            runtime_root=args.runtime_root,
            model_root=args.model_root,
            artifact_root=args.artifact_root,
            context_tokens=args.context_tokens,
            predict_tokens=args.predict_tokens,
            timeout_seconds=args.timeout_seconds,
        )
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"status=LOCAL_MODEL_LOAD_FAIL\nerror={exc}", file=sys.stderr)
        return 2

    load = payload["load_observation"]
    assert isinstance(load, dict)
    candidate = payload["candidate"]
    assert isinstance(candidate, dict)
    print("status=LOCAL_MODEL_LOAD_PASS")
    print(f"report_sha256={payload['report_sha256']}")
    print(f"candidate={candidate['candidate_id']}")
    print(f"download_status={payload['download_status']}")
    print(f"model_file_sha256={payload['model_file_sha256']}")
    print(f"log_verbosity={payload['protocol']['log_verbosity']}")
    print(f"offloaded_layers={load['offloaded_layers']}/{load['total_layers']}")
    print(f"baseline_gpu_used_mib={load['baseline_gpu_used_mib']}")
    print(f"peak_gpu_used_mib={load['peak_gpu_used_mib']}")
    print(f"peak_process_rss_bytes={load['peak_process_rss_bytes']}")
    print(f"elapsed_seconds={float(load['elapsed_seconds']):.3f}")
    print(f"output={args.artifact_root / 'load-preflight.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
