"""Target-machine load qualification for frozen local capable models."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import http.client
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from .local_models import LOCAL_MODEL_SOURCE_FREEZE_V2, FrozenModelSource

REPORT_SCHEMA = "plural-cognition-local-model-load-preflight-v1"
DEFAULT_CONTEXT_TOKENS = 4096
DEFAULT_PREDICT_TOKENS = 32
DEFAULT_TIMEOUT_SECONDS = 600
OFFLOAD_PATTERN = re.compile(r"offloaded\s+(\d+)/(\d+)\s+layers to GPU")


@dataclass(frozen=True, slots=True)
class RuntimeObservation:
    version_output: str
    device_output: str


@dataclass(frozen=True, slots=True)
class LoadObservation:
    command: tuple[str, ...]
    exit_code: int
    elapsed_seconds: float
    stdout_sha256: str
    stderr_sha256: str
    stdout_bytes: int
    stderr_bytes: int
    offloaded_layers: int
    total_layers: int
    baseline_gpu_used_mib: int
    peak_gpu_used_mib: int
    peak_process_rss_bytes: int | None


def _canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    revision = completed.stdout.strip()
    if len(revision) != 40:
        raise RuntimeError(f"git returned a non-full revision: {revision!r}")
    return revision


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_exact_file(path: Path, *, size_bytes: int, expected_sha256: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"required artifact is missing: {path}")
    size = path.stat().st_size
    if size != size_bytes:
        raise RuntimeError(f"artifact size mismatch for {path}: {size} != {size_bytes}")
    digest = _sha256_file(path)
    if digest != expected_sha256:
        raise RuntimeError(f"artifact SHA-256 mismatch for {path}: {digest}")


def _verify_model_file(path: Path, candidate: FrozenModelSource) -> None:
    _verify_exact_file(
        path,
        size_bytes=candidate.size_bytes,
        expected_sha256=candidate.artifact_sha256,
    )


def _verify_runtime_archives(runtime_root: Path) -> None:
    runtime = LOCAL_MODEL_SOURCE_FREEZE_V2.runtime
    downloads = runtime_root / "downloads"
    binary = downloads / "llama-b10361-bin-win-cuda-12.4-x64.zip"
    cudart = downloads / "cudart-llama-bin-win-cuda-12.4-x64.zip"
    if _sha256_file(binary) != runtime.binary_archive_sha256:
        raise RuntimeError("frozen llama.cpp binary archive SHA-256 drifted")
    if _sha256_file(cudart) != runtime.cudart_archive_sha256:
        raise RuntimeError("frozen llama.cpp CUDA runtime archive SHA-256 drifted")


def _download_model(candidate: FrozenModelSource, target: Path) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        _verify_model_file(target, candidate)
        return "reused"

    partial = target.with_name(target.name + ".part")
    if partial.exists() and partial.stat().st_size > candidate.size_bytes:
        raise RuntimeError(f"partial download exceeds frozen size: {partial}")

    initial_offset = partial.stat().st_size if partial.exists() else 0
    previous_size = -1
    for _attempt in range(1, 6):
        offset = partial.stat().st_size if partial.exists() else 0
        if offset == candidate.size_bytes:
            _verify_model_file(partial, candidate)
            os.replace(partial, target)
            return "resumed" if initial_offset else "downloaded"
        if offset == previous_size:
            raise RuntimeError("model download made no progress")
        previous_size = offset

        headers = {"User-Agent": "plural-cognition-model-preflight/1"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = urllib.request.Request(candidate.download_url, headers=headers)

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                status = getattr(response, "status", response.getcode())
                append = bool(offset and status == 206)
                mode = "ab" if append else "wb"
                next_progress = time.monotonic() + 5.0
                with partial.open(mode) as handle:
                    while True:
                        chunk = response.read(8 * 1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
                        if handle.tell() > candidate.size_bytes:
                            raise RuntimeError(
                                "download exceeded the frozen model artifact size"
                            )
                        if time.monotonic() >= next_progress:
                            print(
                                f"download_bytes={handle.tell()}/{candidate.size_bytes}",
                                flush=True,
                            )
                            next_progress = time.monotonic() + 5.0
        except (OSError, urllib.error.URLError, http.client.HTTPException) as exc:
            if _attempt == 5:
                raise RuntimeError(
                    f"model download failed after retries: {exc}"
                ) from exc
            print(f"download_retry={_attempt} error={exc}", flush=True)
            time.sleep(min(2**_attempt, 10))
            continue

        current = partial.stat().st_size
        if current == candidate.size_bytes:
            _verify_model_file(partial, candidate)
            os.replace(partial, target)
            return "resumed" if initial_offset else "downloaded"
        if current > candidate.size_bytes:
            raise RuntimeError(
                f"invalid model download size after transfer: {current}"
            )

    raise RuntimeError(
        f"model download remained incomplete after retries: {partial.stat().st_size}"
    )


def _runtime_observation(cli: Path) -> RuntimeObservation:
    if not cli.is_file():
        raise RuntimeError(f"llama-cli is missing: {cli}")
    version = subprocess.run(
        [str(cli), "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    combined_version = (version.stdout + version.stderr).strip()
    if version.returncode != 0:
        raise RuntimeError(f"llama-cli --version failed: {combined_version}")
    runtime = LOCAL_MODEL_SOURCE_FREEZE_V2.runtime
    if (
        "version: 10361" not in combined_version
        or runtime.upstream_commit not in combined_version
    ):
        raise RuntimeError(
            "llama-cli version does not match the frozen b10361 runtime"
        )

    devices = subprocess.run(
        [str(cli), "--list-devices"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    combined_devices = (devices.stdout + devices.stderr).strip()
    if devices.returncode != 0:
        raise RuntimeError(f"llama-cli --list-devices failed: {combined_devices}")
    if "CUDA0:" not in combined_devices:
        raise RuntimeError("frozen runtime did not expose CUDA0")
    return RuntimeObservation(combined_version, combined_devices)


def _gpu_used_mib() -> int:
    completed = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=memory.used",
            "--format=csv,noheader,nounits",
            "-i",
            "0",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"nvidia-smi memory query failed: {completed.stderr.strip()}")
    lines = completed.stdout.strip().splitlines()
    if len(lines) != 1:
        raise RuntimeError(f"unexpected nvidia-smi memory output: {completed.stdout!r}")
    return int(lines[0].strip())


def _windows_peak_rss(process_id: int) -> int | None:
    if os.name != "nt":
        return None

    class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.OpenProcess.argtypes = [
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_ulong,
    ]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX),
        ctypes.c_ulong,
    ]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int

    handle = kernel32.OpenProcess(0x0400 | 0x0010, False, process_id)
    if not handle:
        return None
    try:
        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(counters)
        ok = psapi.GetProcessMemoryInfo(
            handle,
            ctypes.byref(counters),
            ctypes.sizeof(counters),
        )
        return int(counters.PeakWorkingSetSize) if ok else None
    finally:
        kernel32.CloseHandle(handle)


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
        "--perf",
        "-st",
        "-p",
        "Respond with one short sentence confirming that local inference is running.",
    )


def _run_load(
    command: tuple[str, ...],
    *,
    timeout_seconds: int,
) -> tuple[LoadObservation, bytes, bytes]:
    baseline_gpu = _gpu_used_mib()
    started = time.perf_counter()
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
    )

    peak_gpu = baseline_gpu
    peak_rss: int | None = None
    stop = threading.Event()
    monitor_error: list[BaseException] = []

    def monitor() -> None:
        nonlocal peak_gpu, peak_rss
        while not stop.wait(0.2):
            try:
                peak_gpu = max(peak_gpu, _gpu_used_mib())
                rss = _windows_peak_rss(process.pid)
                if rss is not None:
                    peak_rss = max(peak_rss or 0, rss)
            except BaseException as exc:
                monitor_error.append(exc)
                return

    thread = threading.Thread(target=monitor, name="model-load-monitor", daemon=True)
    thread.start()
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise RuntimeError(
            f"llama-cli load/generation exceeded {timeout_seconds} seconds"
        )
    finally:
        stop.set()
        thread.join(timeout=15)

    elapsed = time.perf_counter() - started
    if monitor_error:
        raise RuntimeError(f"resource monitor failed: {monitor_error[0]}")
    peak_gpu = max(peak_gpu, _gpu_used_mib())

    if process.returncode != 0:
        raise RuntimeError(
            "llama-cli load/generation failed with exit "
            f"{process.returncode}: {stderr.decode('utf-8', errors='replace')}"
        )
    if not stdout:
        raise RuntimeError("llama-cli produced no generated stdout")

    stderr_text = stderr.decode("utf-8", errors="replace")
    matches = OFFLOAD_PATTERN.findall(stderr_text)
    if not matches:
        raise RuntimeError("llama-cli log did not prove GPU layer offload")
    offloaded, total = (int(value) for value in matches[-1])
    if offloaded != total:
        raise RuntimeError(
            f"model was not fully offloaded to GPU: {offloaded}/{total} layers"
        )

    observation = LoadObservation(
        command=command,
        exit_code=process.returncode,
        elapsed_seconds=elapsed,
        stdout_sha256=hashlib.sha256(stdout).hexdigest(),
        stderr_sha256=hashlib.sha256(stderr).hexdigest(),
        stdout_bytes=len(stdout),
        stderr_bytes=len(stderr),
        offloaded_layers=offloaded,
        total_layers=total,
        baseline_gpu_used_mib=baseline_gpu,
        peak_gpu_used_mib=peak_gpu,
        peak_process_rss_bytes=peak_rss,
    )
    return observation, stdout, stderr


def _atomic_write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )
    os.replace(temporary, path)


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
        description="Download, verify, and load one frozen local capable model."
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
    print(f"offloaded_layers={load['offloaded_layers']}/{load['total_layers']}")
    print(f"baseline_gpu_used_mib={load['baseline_gpu_used_mib']}")
    print(f"peak_gpu_used_mib={load['peak_gpu_used_mib']}")
    print(f"peak_process_rss_bytes={load['peak_process_rss_bytes']}")
    print(f"elapsed_seconds={float(load['elapsed_seconds']):.3f}")
    print(f"output={args.artifact_root / 'load-preflight.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
