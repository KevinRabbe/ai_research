"""Restart-safe observer repair for candidate-pool v2 load qualification.

The original v2 load qualification at revision
c398cc8580302cfe84073207280959d0f1a0d8cd is preserved as immutable evidence.
It produced three terminal FAIL reports because the observer required the
"offloaded N/N layers to GPU" library INFO line while the pinned llama.cpp
runtime only emits library INFO at trace verbosity (4). The original command
used the default verbosity (3), so the required evidence was suppressed.

This recovery stage verifies and binds to that invalidated suite before any
new inference, changes only the logging verbosity needed to expose the frozen
gate evidence, persists raw stdout/stderr before classification, and writes to
a separate artifact root. It remains candidate-development evidence only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

from .candidate_pool_v2_source_freeze import (
    FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256,
    QUALIFICATION_PROTOCOL_SHA256,
    candidate_pool_v2_source_freeze_payload,
)
from .local_candidate_pool_v2_load_qualification import (
    CHALLENGER_IDS_V2,
    FINAL_LOAD_PLAN_SHA256_V2,
    LOAD_CONTEXT_TOKENS_V2,
    LOAD_PREDICT_TOKENS_V2,
)
from .local_model_load_preflight import (
    OFFLOAD_PATTERN,
    _canonical_json_bytes,
    _git_revision,
    _gpu_used_mib,
    _load_command,
    _runtime_observation,
    _sha256_file,
    _verify_runtime_archives,
    _windows_peak_rss,
)

RECOVERY_PLAN_SCHEMA = "plural-cognition-candidate-pool-v2-load-observer-repair-plan-v1"
RECOVERY_REPORT_SCHEMA = "plural-cognition-candidate-pool-v2-load-observer-repair-result-v1"
RECOVERY_SUITE_SCHEMA = "plural-cognition-candidate-pool-v2-load-observer-repair-suite-v1"

ORIGINAL_LOAD_REVISION = "c398cc8580302cfe84073207280959d0f1a0d8cd"
ORIGINAL_SUITE_FILE_SHA256 = "a15af45ddc9c95e779beaa22cc9389be7029b42a623ed7bd989794823074ed60"
ORIGINAL_SUITE_REPORT_SHA256 = "d0e203c0d55bc8b4a0318caff8c5e1161ab936f377fa0f18a00134ee763e66d0"
ORIGINAL_COMMON_FAILURE = "llama-cli log did not prove GPU layer offload"
ORIGINAL_CANDIDATE_REPORT_SHA256 = {
    "gpt-oss-20b-mxfp4": "e588467d66c999bc239c01984cf0968b9f278496138ea2bec2c3885f5cffaf70",
    "phi-4-reasoning-plus-14b-q5km": "73f980020b9b48463012bdda2879c0f2ae10a95de9298037a1eb5327d1e5e81b",
    "devstral-small-2-24b-q4km": "9b381475a33be37b1f25a064abc7e82c351d49df845c18ace9f0f57a341560ac",
}

RECOVERY_LOG_VERBOSITY = 4
DEFAULT_RECOVERY_TIMEOUT_SECONDS = 900
EXPECTED_RECOVERY_PLAN_SHA256 = "c4f5063d596dd8204963277b209768685817f03cbe38403bd79762bd2cb5b942"


@dataclass(frozen=True, slots=True)
class RecoveryAttemptObservation:
    command: tuple[str, ...]
    exit_code: int
    timed_out: bool
    elapsed_seconds: float
    stdout_sha256: str
    stderr_sha256: str
    stdout_bytes: int
    stderr_bytes: int
    baseline_gpu_used_mib: int
    peak_gpu_used_mib: int
    peak_process_rss_bytes: int | None
    monitor_error: str | None


def load_observer_repair_plan_payload_v2() -> dict[str, Any]:
    return {
        "schema": RECOVERY_PLAN_SCHEMA,
        "scientific_status": "candidate-development-v2-load-observer-repair-not-selection-evidence",
        "candidate_pool_v2_protocol_sha256": QUALIFICATION_PROTOCOL_SHA256,
        "candidate_pool_v2_source_freeze_sha256": FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256,
        "invalidated_load_qualification": {
            "software_revision": ORIGINAL_LOAD_REVISION,
            "load_plan_sha256": FINAL_LOAD_PLAN_SHA256_V2,
            "suite_file_sha256": ORIGINAL_SUITE_FILE_SHA256,
            "suite_report_sha256": ORIGINAL_SUITE_REPORT_SHA256,
            "qualified_count": 0,
            "failed_count": 3,
            "common_failure": ORIGINAL_COMMON_FAILURE,
            "observer_defect": (
                "pinned llama.cpp b10361 maps LLAMA library INFO to trace verbosity 4 "
                "while the original command used default verbosity 3, suppressing the "
                "required offload log line"
            ),
        },
        "challenger_ids": list(CHALLENGER_IDS_V2),
        "runtime": {
            "llama_cpp_build": "b10361",
            "llama_cpp_revision": "14e78ddef7a2061e7d5a31dce4eb7ee0bcdbc840",
            "device": "CUDA0",
        },
        "recovery_probe": {
            "context_tokens": LOAD_CONTEXT_TOKENS_V2,
            "predict_tokens": LOAD_PREDICT_TOKENS_V2,
            "temperature": 0.0,
            "seed": 1,
            "full_gpu_offload_required": True,
            "fit_mode": False,
            "split_mode": "none",
            "main_gpu": 0,
            "kv_cache": "f16",
            "mmap": True,
            "offline": True,
            "log_verbosity": RECOVERY_LOG_VERBOSITY,
            "attempts_per_challenger": 1,
            "only_intended_command_change": (
                "add --verbosity 4 so the pinned runtime emits the offload evidence "
                "required by the gate"
            ),
        },
        "evidence_policy": {
            "original_l2_evidence_immutable": True,
            "recovery_artifact_root_must_differ": True,
            "completed_report_reused_without_inference": True,
            "partial_attempt_blocks_rerun": True,
            "raw_stdout_stderr_persisted_before_classification": True,
            "candidate_load_failures_terminal_for_recovery": True,
            "artifact_substitution_after_outcome": False,
            "selection_evidence": False,
        },
    }


FINAL_RECOVERY_PLAN_SHA256 = hashlib.sha256(
    _canonical_json_bytes(load_observer_repair_plan_payload_v2())
).hexdigest()
if FINAL_RECOVERY_PLAN_SHA256 != EXPECTED_RECOVERY_PLAN_SHA256:
    raise AssertionError("candidate-pool v2 load observer-repair plan identity drifted")


def _challengers() -> dict[str, dict[str, Any]]:
    payload = candidate_pool_v2_source_freeze_payload()
    items = {item["candidate_id"]: item for item in payload["challengers"]}
    if tuple(items) != CHALLENGER_IDS_V2:
        raise AssertionError("candidate-pool v2 challenger order drifted")
    return items


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(_canonical_json_bytes(payload) + b"\n")
    os.replace(temporary, path)


def _verify_model_file(path: Path, candidate: dict[str, Any]) -> tuple[str, int]:
    if not path.is_file():
        raise RuntimeError(f"required challenger artifact is missing: {path}")
    observed_size = path.stat().st_size
    expected_size = candidate["artifact_size_bytes"]
    if expected_size is not None and observed_size != expected_size:
        raise RuntimeError(
            f"challenger artifact size mismatch for {candidate['candidate_id']}: "
            f"{observed_size} != {expected_size}"
        )
    observed_sha256 = _sha256_file(path)
    if observed_sha256 != candidate["artifact_sha256"]:
        raise RuntimeError(
            f"challenger artifact SHA-256 mismatch for {candidate['candidate_id']}: "
            f"{observed_sha256}"
        )
    return observed_sha256, observed_size


def _recovery_load_command(
    cli: Path,
    model_path: Path,
    *,
    context_tokens: int = LOAD_CONTEXT_TOKENS_V2,
    predict_tokens: int = LOAD_PREDICT_TOKENS_V2,
) -> tuple[str, ...]:
    base = list(
        _load_command(
            cli,
            model_path,
            context_tokens=context_tokens,
            predict_tokens=predict_tokens,
        )
    )
    if any(
        flag in base
        for flag in (
            "-v",
            "--verbose",
            "--log-verbose",
            "-lv",
            "--verbosity",
            "--log-verbosity",
        )
    ):
        raise AssertionError("formal base command unexpectedly already controls verbosity")
    offline_index = base.index("--offline")
    base[offline_index:offline_index] = ["--verbosity", str(RECOVERY_LOG_VERBOSITY)]
    return tuple(base)


def _verify_invalidated_evidence(invalidated_root: Path) -> None:
    suite_path = invalidated_root / "load-qualification-suite.json"
    if not suite_path.is_file():
        raise RuntimeError(f"invalidated v2 suite is missing: {suite_path}")
    suite_file_sha = _sha256_file(suite_path)
    if suite_file_sha != ORIGINAL_SUITE_FILE_SHA256:
        raise RuntimeError(f"invalidated v2 suite file SHA-256 drifted: {suite_file_sha}")
    suite = json.loads(suite_path.read_text(encoding="ascii"))
    required_suite = {
        "schema": "plural-cognition-candidate-pool-v2-load-qualification-suite-v1",
        "scientific_status": "candidate-development-v2-load-qualification-not-selection-evidence",
        "status": "CANDIDATE_POOL_V2_LOAD_QUALIFICATION_COMPLETE",
        "software_revision": ORIGINAL_LOAD_REVISION,
        "load_plan_sha256": FINAL_LOAD_PLAN_SHA256_V2,
        "source_freeze_sha256": FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256,
        "result_count": 3,
        "qualified_count": 0,
        "failed_count": 3,
        "new_inference_attempt_count_this_invocation": 3,
        "report_sha256": ORIGINAL_SUITE_REPORT_SHA256,
        "selection_evidence": False,
    }
    for key, expected in required_suite.items():
        if suite.get(key) != expected:
            raise RuntimeError(
                f"invalidated v2 suite field drifted: {key}={suite.get(key)!r}"
            )
    if tuple(suite.get("challenger_ids", ())) != CHALLENGER_IDS_V2:
        raise RuntimeError("invalidated v2 suite challenger order drifted")

    verbosity_flags = {
        "-v",
        "--verbose",
        "--log-verbose",
        "-lv",
        "--verbosity",
        "--log-verbosity",
    }
    for candidate_id in CHALLENGER_IDS_V2:
        report_path = invalidated_root / candidate_id / "load-preflight.json"
        if not report_path.is_file():
            raise RuntimeError(f"invalidated candidate report is missing: {report_path}")
        report = json.loads(report_path.read_text(encoding="ascii"))
        expected_report_sha = ORIGINAL_CANDIDATE_REPORT_SHA256[candidate_id]
        if report.get("report_sha256") != expected_report_sha:
            raise RuntimeError(f"invalidated report identity drifted for {candidate_id}")
        unsigned_report = dict(report)
        unsigned_report.pop("report_sha256", None)
        recomputed = hashlib.sha256(_canonical_json_bytes(unsigned_report)).hexdigest()
        if recomputed != expected_report_sha:
            raise RuntimeError(f"invalidated report content drifted for {candidate_id}")
        if report.get("status") != "LOCAL_MODEL_LOAD_FAIL":
            raise RuntimeError(f"invalidated report status drifted for {candidate_id}")
        if report.get("failure") != ORIGINAL_COMMON_FAILURE:
            raise RuntimeError(f"invalidated report failure drifted for {candidate_id}")
        if report.get("software_revision") != ORIGINAL_LOAD_REVISION:
            raise RuntimeError(f"invalidated report revision drifted for {candidate_id}")
        if report.get("load_plan_sha256") != FINAL_LOAD_PLAN_SHA256_V2:
            raise RuntimeError(f"invalidated report plan drifted for {candidate_id}")
        command = tuple(report.get("command", ()))
        if verbosity_flags.intersection(command):
            raise RuntimeError(
                f"invalidated report unexpectedly controlled verbosity for {candidate_id}"
            )


def _run_raw_attempt(
    command: tuple[str, ...],
    *,
    timeout_seconds: int,
) -> tuple[RecoveryAttemptObservation, bytes, bytes]:
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
            except BaseException as exc:  # pragma: no cover - hardware/infrastructure path
                monitor_error.append(exc)
                return

    thread = threading.Thread(target=monitor, name="v2-load-repair-monitor", daemon=True)
    thread.start()
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        stdout, stderr = process.communicate()
    finally:
        stop.set()
        thread.join(timeout=15)

    elapsed = time.perf_counter() - started
    try:
        peak_gpu = max(peak_gpu, _gpu_used_mib())
    except BaseException as exc:  # pragma: no cover - hardware/infrastructure path
        monitor_error.append(exc)

    observation = RecoveryAttemptObservation(
        command=command,
        exit_code=int(process.returncode),
        timed_out=timed_out,
        elapsed_seconds=elapsed,
        stdout_sha256=hashlib.sha256(stdout).hexdigest(),
        stderr_sha256=hashlib.sha256(stderr).hexdigest(),
        stdout_bytes=len(stdout),
        stderr_bytes=len(stderr),
        baseline_gpu_used_mib=baseline_gpu,
        peak_gpu_used_mib=peak_gpu,
        peak_process_rss_bytes=peak_rss,
        monitor_error=str(monitor_error[0]) if monitor_error else None,
    )
    return observation, stdout, stderr


def _classify_attempt(
    observation: RecoveryAttemptObservation,
    *,
    stdout: bytes,
    stderr: bytes,
) -> tuple[str, str | None, int | None, int | None]:
    if observation.timed_out:
        return (
            "LOCAL_MODEL_LOAD_FAIL",
            "llama-cli load/generation exceeded recovery timeout",
            None,
            None,
        )
    if observation.exit_code != 0:
        return (
            "LOCAL_MODEL_LOAD_FAIL",
            f"llama-cli load/generation failed with exit {observation.exit_code}",
            None,
            None,
        )
    if not stdout:
        return (
            "LOCAL_MODEL_LOAD_FAIL",
            "llama-cli produced no generated stdout",
            None,
            None,
        )

    stderr_text = stderr.decode("utf-8", errors="replace")
    matches = OFFLOAD_PATTERN.findall(stderr_text)
    if not matches:
        return (
            "LOCAL_MODEL_LOAD_FAIL",
            "llama-cli trace log did not prove GPU layer offload",
            None,
            None,
        )
    offloaded, total = (int(value) for value in matches[-1])
    if offloaded != total:
        return (
            "LOCAL_MODEL_LOAD_FAIL",
            f"model was not fully offloaded to GPU: {offloaded}/{total} layers",
            offloaded,
            total,
        )
    return ("LOCAL_MODEL_LOAD_PASS", None, offloaded, total)


def _validate_completed_report(
    report: dict[str, Any], *, candidate_id: str, software_revision: str
) -> None:
    if report.get("schema") != RECOVERY_REPORT_SCHEMA:
        raise RuntimeError(f"completed recovery report schema drifted for {candidate_id}")
    if report.get("candidate_id") != candidate_id:
        raise RuntimeError(f"completed recovery report candidate drifted for {candidate_id}")
    if report.get("software_revision") != software_revision:
        raise RuntimeError(f"completed recovery report revision drifted for {candidate_id}")
    if report.get("recovery_plan_sha256") != FINAL_RECOVERY_PLAN_SHA256:
        raise RuntimeError(f"completed recovery report plan drifted for {candidate_id}")
    if report.get("status") not in {"LOCAL_MODEL_LOAD_PASS", "LOCAL_MODEL_LOAD_FAIL"}:
        raise RuntimeError(f"completed recovery report status drifted for {candidate_id}")


def _run_candidate_once(
    *,
    candidate: dict[str, Any],
    cli: Path,
    model_root: Path,
    artifact_root: Path,
    runtime_observation: Any,
    software_revision: str,
    timeout_seconds: int,
) -> tuple[dict[str, Any], bool]:
    candidate_id = candidate["candidate_id"]
    candidate_root = artifact_root / candidate_id
    report_path = candidate_root / "load-preflight-recovery.json"
    attempt_path = candidate_root / "attempt-recovery.json"

    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="ascii"))
        _validate_completed_report(
            report, candidate_id=candidate_id, software_revision=software_revision
        )
        return report, False
    if candidate_root.exists():
        raise RuntimeError(
            "partial v2 observer-repair evidence exists without a final report; "
            f"automatic rerun is forbidden: {candidate_root}"
        )

    model_path = model_root / candidate_id / candidate["filename"]
    model_sha256, model_size_bytes = _verify_model_file(model_path, candidate)
    command = _recovery_load_command(cli, model_path)
    base_command = _load_command(
        cli,
        model_path,
        context_tokens=LOAD_CONTEXT_TOKENS_V2,
        predict_tokens=LOAD_PREDICT_TOKENS_V2,
    )
    stripped = list(command)
    verbosity_index = stripped.index("--verbosity")
    if stripped[verbosity_index : verbosity_index + 2] != [
        "--verbosity",
        str(RECOVERY_LOG_VERBOSITY),
    ]:
        raise AssertionError("recovery command verbosity drifted")
    del stripped[verbosity_index : verbosity_index + 2]
    if tuple(stripped) != base_command:
        raise AssertionError("recovery command changed beyond trace verbosity")

    command_sha256 = hashlib.sha256(_canonical_json_bytes(list(command))).hexdigest()
    attempt = {
        "schema": "plural-cognition-candidate-pool-v2-load-observer-repair-attempt-v1",
        "candidate_id": candidate_id,
        "software_revision": software_revision,
        "recovery_plan_sha256": FINAL_RECOVERY_PLAN_SHA256,
        "invalidated_suite_file_sha256": ORIGINAL_SUITE_FILE_SHA256,
        "source_freeze_sha256": FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256,
        "model_file_sha256": model_sha256,
        "model_file_size_bytes": model_size_bytes,
        "command": list(command),
        "command_sha256": command_sha256,
        "inference_attempt_authorized": True,
        "max_attempts": 1,
    }
    candidate_root.mkdir(parents=True)
    _write_json_atomic(attempt_path, attempt)

    observation, stdout, stderr = _run_raw_attempt(
        command, timeout_seconds=timeout_seconds
    )

    # Persist the raw streams before any semantic classification.
    (candidate_root / "stdout.bin").write_bytes(stdout)
    (candidate_root / "stderr.bin").write_bytes(stderr)
    _write_json_atomic(candidate_root / "attempt-observation.json", asdict(observation))

    if observation.monitor_error is not None:
        raise RuntimeError(f"resource monitor failed: {observation.monitor_error}")

    status, failure, offloaded, total = _classify_attempt(
        observation, stdout=stdout, stderr=stderr
    )
    report: dict[str, Any] = {
        "schema": RECOVERY_REPORT_SCHEMA,
        "scientific_status": "candidate-development-v2-load-observer-repair-not-selection-evidence",
        "status": status,
        "candidate_id": candidate_id,
        "software_revision": software_revision,
        "recovery_plan_sha256": FINAL_RECOVERY_PLAN_SHA256,
        "invalidated_suite_file_sha256": ORIGINAL_SUITE_FILE_SHA256,
        "source_freeze_sha256": FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256,
        "candidate_source": candidate,
        "model_file_sha256": model_sha256,
        "model_file_size_bytes": model_size_bytes,
        "runtime_observation": asdict(runtime_observation),
        "command": list(command),
        "command_sha256": command_sha256,
        "attempt_observation": asdict(observation),
        "offload_observation": (
            {"offloaded_layers": offloaded, "total_layers": total}
            if offloaded is not None and total is not None
            else None
        ),
        "failure": failure,
        "attempt_count": 1,
        "selection_evidence": False,
    }
    report_sha256 = hashlib.sha256(_canonical_json_bytes(report)).hexdigest()
    report["report_sha256"] = report_sha256
    _write_json_atomic(report_path, report)
    return report, True


def run_recovery_suite(
    *,
    runtime_root: Path,
    model_root: Path,
    invalidated_artifact_root: Path,
    artifact_root: Path,
    software_revision: str,
    timeout_seconds: int = DEFAULT_RECOVERY_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    if type(timeout_seconds) is not int or timeout_seconds < 1:
        raise ValueError("timeout_seconds must be a positive integer")
    if invalidated_artifact_root.resolve() == artifact_root.resolve():
        raise RuntimeError("recovery artifact root must differ from immutable original l2 root")
    revision = _git_revision()
    if revision != software_revision:
        raise RuntimeError(
            f"software revision mismatch: checkout={revision} requested={software_revision}"
        )

    _verify_invalidated_evidence(invalidated_artifact_root)
    _verify_runtime_archives(runtime_root)
    cli = runtime_root / "bin" / "llama-cli.exe"
    runtime_observation = _runtime_observation(cli)
    challengers = _challengers()

    for candidate_id in CHALLENGER_IDS_V2:
        candidate = challengers[candidate_id]
        model_path = model_root / candidate_id / candidate["filename"]
        _verify_model_file(model_path, candidate)

    artifact_root.mkdir(parents=True, exist_ok=True)
    plan_path = artifact_root / "load-observer-repair-plan.json"
    if plan_path.exists():
        existing = plan_path.read_bytes().rstrip(b"\r\n")
        if existing != _canonical_json_bytes(load_observer_repair_plan_payload_v2()):
            raise RuntimeError("existing v2 observer-repair plan artifact drifted")
    else:
        _write_json_atomic(plan_path, load_observer_repair_plan_payload_v2())

    results: list[dict[str, Any]] = []
    new_attempts = 0
    for candidate_id in CHALLENGER_IDS_V2:
        report, attempted = _run_candidate_once(
            candidate=challengers[candidate_id],
            cli=cli,
            model_root=model_root,
            artifact_root=artifact_root,
            runtime_observation=runtime_observation,
            software_revision=software_revision,
            timeout_seconds=timeout_seconds,
        )
        results.append(report)
        new_attempts += int(attempted)
        print(
            f"candidate={candidate_id} status={report['status']} "
            f"new_inference_attempt={attempted} report_sha256={report['report_sha256']}",
            flush=True,
        )

    pass_count = sum(item["status"] == "LOCAL_MODEL_LOAD_PASS" for item in results)
    fail_count = len(results) - pass_count
    suite = {
        "schema": RECOVERY_SUITE_SCHEMA,
        "scientific_status": "candidate-development-v2-load-observer-repair-not-selection-evidence",
        "status": "CANDIDATE_POOL_V2_LOAD_OBSERVER_REPAIR_COMPLETE",
        "software_revision": software_revision,
        "recovery_plan_sha256": FINAL_RECOVERY_PLAN_SHA256,
        "invalidated_suite_file_sha256": ORIGINAL_SUITE_FILE_SHA256,
        "source_freeze_sha256": FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256,
        "challenger_ids": list(CHALLENGER_IDS_V2),
        "result_count": len(results),
        "qualified_count": pass_count,
        "failed_count": fail_count,
        "new_inference_attempt_count_this_invocation": new_attempts,
        "results": [
            {
                "candidate_id": item["candidate_id"],
                "status": item["status"],
                "report_sha256": item["report_sha256"],
                "model_file_sha256": item["model_file_sha256"],
                "model_file_size_bytes": item["model_file_size_bytes"],
                "offload_observation": item["offload_observation"],
                "failure": item["failure"],
            }
            for item in results
        ],
        "selection_evidence": False,
    }
    suite_sha256 = hashlib.sha256(_canonical_json_bytes(suite)).hexdigest()
    suite["report_sha256"] = suite_sha256
    _write_json_atomic(artifact_root / "load-observer-repair-suite.json", suite)
    return suite


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run or safely resume the observer-repair qualification for the three "
            "predeclared candidate-pool v2 challengers."
        )
    )
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--invalidated-artifact-root", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument(
        "--timeout-seconds", type=int, default=DEFAULT_RECOVERY_TIMEOUT_SECONDS
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        suite = run_recovery_suite(
            runtime_root=args.runtime_root,
            model_root=args.model_root,
            invalidated_artifact_root=args.invalidated_artifact_root,
            artifact_root=args.artifact_root,
            software_revision=args.software_revision,
            timeout_seconds=args.timeout_seconds,
        )
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"status=CANDIDATE_POOL_V2_LOAD_OBSERVER_REPAIR_ABORT\nerror={exc}")
        return 2

    print("status=CANDIDATE_POOL_V2_LOAD_OBSERVER_REPAIR_COMPLETE")
    print(f"report_sha256={suite['report_sha256']}")
    print(f"recovery_plan_sha256={suite['recovery_plan_sha256']}")
    print(f"invalidated_suite_file_sha256={suite['invalidated_suite_file_sha256']}")
    print(f"qualified_count={suite['qualified_count']}/3")
    print(f"failed_count={suite['failed_count']}/3")
    print(
        "new_inference_attempt_count_this_invocation="
        f"{suite['new_inference_attempt_count_this_invocation']}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
