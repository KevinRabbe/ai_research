"""Restart-safe load-only qualification for the three frozen v3 expansion scouts.

The runner binds the green expansion source freeze, verifies all three exact GGUF
artifacts and the frozen llama.cpp runtime before the first model launch, writes an
attempt marker before each load-only probe, persists raw stdout/stderr before
classification, and never automatically reruns a consumed scout. Completed reports
are immutable and reusable; any scout directory without a final report is partial
evidence and blocks all new model launches.

This is candidate-development evidence only and never selection evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from .candidate_pool_v3_expansion_source_freeze import (
    EXPANSION_SCOUT_IDS_V3,
    EXPECTED_CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SHA256,
    candidate_pool_v3_expansion_source_freeze_payload,
    validate_candidate_pool_v3_expansion_source_freeze,
)
from .candidate_pool_v3_representation_protocol import (
    candidate_pool_v3_representation_protocol_payload,
)
from .local_candidate_pool_v2_load_observer_repair import _run_raw_attempt
from .local_model_load_preflight import (
    OFFLOAD_PATTERN,
    _git_revision,
    _runtime_observation,
    _sha256_file,
    _verify_runtime_archives,
)

EXPANSION_LOAD_RUNNER_PROTOCOL_SCHEMA_V3 = (
    "plural-cognition-candidate-pool-v3-expansion-load-runner-protocol-v1"
)
EXPANSION_LOAD_ATTEMPT_SCHEMA_V3 = (
    "plural-cognition-candidate-pool-v3-expansion-load-attempt-v1"
)
EXPANSION_LOAD_RESULT_SCHEMA_V3 = (
    "plural-cognition-candidate-pool-v3-expansion-load-result-v1"
)
EXPANSION_LOAD_SUITE_SCHEMA_V3 = (
    "plural-cognition-candidate-pool-v3-expansion-load-suite-v1"
)
EXPANSION_SOURCE_FREEZE_REVISION_V3 = (
    "dea35b4c11d8de39b978bf3a4ba5f098cfab795b"
)
EXPECTED_EXPANSION_LOAD_RUNNER_PROTOCOL_SHA256_V3 = (
    "6670ae531b31bd0548947bcc4ce0b8248204648f0bd3d280c68e1211bed340a4"
)
EXPANSION_LOAD_ARTIFACT_ROOT_V3 = "artifacts/capable-collective/e3l"
EXPANSION_LOAD_CONTEXT_TOKENS_V3 = 4096
EXPANSION_LOAD_PREDICT_TOKENS_V3 = 0
EXPANSION_LOAD_INERT_PROMPT_V3 = "."
EXPANSION_LOAD_LOG_VERBOSITY_V3 = 4
DEFAULT_EXPANSION_LOAD_TIMEOUT_SECONDS_V3 = 900


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(_canonical_json_bytes(payload) + b"\n")
    os.replace(temporary, path)


def _write_json_once(path: Path, payload: dict[str, Any]) -> None:
    expected = _canonical_json_bytes(payload) + b"\n"
    if path.is_file():
        if path.read_bytes() != expected:
            raise RuntimeError(f"existing immutable JSON artifact drifted: {path}")
        return
    if path.exists():
        raise RuntimeError(f"immutable JSON artifact path is not a file: {path}")
    _write_json_atomic(path, payload)


def expansion_scout_sources_v3() -> dict[str, dict[str, Any]]:
    source_freeze = candidate_pool_v3_expansion_source_freeze_payload()
    scouts = source_freeze["scouts"]
    if not isinstance(scouts, list):
        raise RuntimeError("v3 expansion source-freeze scout collection drifted")
    indexed = {item["candidate_id"]: item for item in scouts}
    if tuple(indexed) != EXPANSION_SCOUT_IDS_V3:
        raise RuntimeError("v3 expansion source-freeze scout order drifted")
    return indexed


def expansion_load_runner_protocol_payload_v3() -> dict[str, Any]:
    representation = candidate_pool_v3_representation_protocol_payload()
    sources = expansion_scout_sources_v3()
    return {
        "schema": EXPANSION_LOAD_RUNNER_PROTOCOL_SCHEMA_V3,
        "scientific_status": (
            "candidate-development-v3-expansion-load-only-not-selection-evidence"
        ),
        "predecessor_expansion_source_freeze_sha256": (
            EXPECTED_CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SHA256
        ),
        "source_freeze_revision": EXPANSION_SOURCE_FREEZE_REVISION_V3,
        "scout_ids": list(EXPANSION_SCOUT_IDS_V3),
        "pair_count": len(EXPANSION_SCOUT_IDS_V3),
        "scouts": [
            {
                "candidate_id": candidate_id,
                "filename": sources[candidate_id]["artifact_filename"],
                "artifact_size_bytes": sources[candidate_id]["artifact_size_bytes"],
                "artifact_sha256": sources[candidate_id]["artifact_sha256"],
            }
            for candidate_id in EXPANSION_SCOUT_IDS_V3
        ],
        "runtime": {
            "llama_cpp_build": "b10361",
            "llama_cpp_revision": "14e78ddef7a2061e7d5a31dce4eb7ee0bcdbc840",
            "device": "CUDA0",
        },
        "resource_budget": representation["resource_budget"],
        "load_probe": {
            "context_tokens": EXPANSION_LOAD_CONTEXT_TOKENS_V3,
            "predict_tokens": EXPANSION_LOAD_PREDICT_TOKENS_V3,
            "inert_prompt": EXPANSION_LOAD_INERT_PROMPT_V3,
            "capability_prompt": False,
            "temperature": 0.0,
            "seed": 1,
            "log_verbosity": EXPANSION_LOAD_LOG_VERBOSITY_V3,
            "full_gpu_offload_required": True,
            "fit_mode": False,
            "split_mode": "none",
            "main_gpu": 0,
            "kv_cache": "f16",
            "mmap": True,
            "offline": True,
            "attempts_per_scout": 1,
        },
        "evidence_policy": {
            "all_model_files_verified_before_first_attempt": True,
            "attempt_marker_before_inference": True,
            "completed_report_reused_without_inference": True,
            "partial_attempt_blocks_all_new_inference": True,
            "raw_stdout_stderr_persisted_before_classification": True,
            "load_failure_terminal_for_frozen_artifact": True,
            "automatic_reruns": False,
            "candidate_specific_runtime_tuning": False,
            "artifact_substitution_after_outcome": False,
            "artifact_root": EXPANSION_LOAD_ARTIFACT_ROOT_V3,
            "selection_evidence": False,
        },
        "selection_evidence": False,
    }


def expansion_load_runner_protocol_sha256_v3() -> str:
    return _canonical_sha256(expansion_load_runner_protocol_payload_v3())


def validate_expansion_load_runner_protocol_v3() -> None:
    validate_candidate_pool_v3_expansion_source_freeze()
    payload = expansion_load_runner_protocol_payload_v3()
    if payload["predecessor_expansion_source_freeze_sha256"] != (
        EXPECTED_CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SHA256
    ):
        raise RuntimeError("v3 expansion load runner source-freeze identity drifted")
    if tuple(payload["scout_ids"]) != EXPANSION_SCOUT_IDS_V3:
        raise RuntimeError("v3 expansion load runner scout order drifted")
    if payload["pair_count"] != 3:
        raise RuntimeError("v3 expansion load runner must contain exactly three scouts")
    probe = payload["load_probe"]
    if probe["predict_tokens"] != 0 or probe["capability_prompt"]:
        raise RuntimeError("v3 expansion formal probe must remain load-only")
    if probe["attempts_per_scout"] != 1:
        raise RuntimeError("v3 expansion load attempts must remain one per scout")
    if not probe["full_gpu_offload_required"] or probe["fit_mode"]:
        raise RuntimeError("v3 expansion load resource gate drifted")
    policy = payload["evidence_policy"]
    if policy["automatic_reruns"] or policy["candidate_specific_runtime_tuning"]:
        raise RuntimeError("v3 expansion load retries/tuning remain forbidden")
    if policy["selection_evidence"] or payload["selection_evidence"]:
        raise RuntimeError("v3 expansion load qualification cannot be selection evidence")
    observed = expansion_load_runner_protocol_sha256_v3()
    if observed != EXPECTED_EXPANSION_LOAD_RUNNER_PROTOCOL_SHA256_V3:
        raise RuntimeError(
            f"v3 expansion load-runner protocol identity drifted: {observed}"
        )


def _verify_model_file(path: Path, source: dict[str, Any]) -> tuple[str, int]:
    if not path.is_file():
        raise RuntimeError(f"required expansion scout artifact is missing: {path}")
    observed_size = path.stat().st_size
    expected_size = source["artifact_size_bytes"]
    if observed_size != expected_size:
        raise RuntimeError(
            f"expansion scout artifact size mismatch for {source['candidate_id']}: "
            f"{observed_size} != {expected_size}"
        )
    observed_sha256 = _sha256_file(path)
    if observed_sha256 != source["artifact_sha256"]:
        raise RuntimeError(
            f"expansion scout artifact SHA-256 mismatch for {source['candidate_id']}: "
            f"{observed_sha256}"
        )
    return observed_sha256, observed_size


def _load_only_command(cli: Path, model_path: Path) -> tuple[str, ...]:
    budget = expansion_load_runner_protocol_payload_v3()["resource_budget"]
    return (
        str(cli),
        "-m",
        str(model_path),
        "-c",
        str(EXPANSION_LOAD_CONTEXT_TOKENS_V3),
        "-n",
        "0",
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
        "-t",
        str(budget["threads"]),
        "-tb",
        str(budget["batch_threads"]),
        "-b",
        str(budget["batch_size"]),
        "-ub",
        str(budget["microbatch_size"]),
        "-fa",
        str(budget["flash_attention"]),
        "--no-display-prompt",
        "--log-colors",
        "off",
        "--no-log-timestamps",
        "--log-verbosity",
        str(EXPANSION_LOAD_LOG_VERBOSITY_V3),
        "--perf",
        "-st",
        "-p",
        EXPANSION_LOAD_INERT_PROMPT_V3,
    )


def _classify_load_only_attempt(
    observation: Any, *, stderr: bytes
) -> tuple[str, str | None, int | None, int | None]:
    if observation.timed_out:
        return "LOCAL_MODEL_LOAD_FAIL", "llama-cli load-only probe exceeded timeout", None, None
    if observation.exit_code != 0:
        return (
            "LOCAL_MODEL_LOAD_FAIL",
            f"llama-cli load-only probe failed with exit {observation.exit_code}",
            None,
            None,
        )
    if observation.monitor_error is not None:
        return (
            "LOCAL_MODEL_LOAD_FAIL",
            f"resource monitor failed during load-only probe: {observation.monitor_error}",
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
    return "LOCAL_MODEL_LOAD_PASS", None, offloaded, total


def _validate_completed_report(
    report: dict[str, Any], *, candidate_id: str, software_revision: str
) -> None:
    required = {
        "schema": EXPANSION_LOAD_RESULT_SCHEMA_V3,
        "candidate_id": candidate_id,
        "software_revision": software_revision,
        "runner_protocol_sha256": expansion_load_runner_protocol_sha256_v3(),
        "source_freeze_sha256": EXPECTED_CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SHA256,
        "selection_evidence": False,
    }
    for key, expected in required.items():
        if report.get(key) != expected:
            raise RuntimeError(
                f"completed v3 expansion load report field drifted: {candidate_id}:{key}"
            )
    if report.get("status") not in {"LOCAL_MODEL_LOAD_PASS", "LOCAL_MODEL_LOAD_FAIL"}:
        raise RuntimeError(f"completed v3 expansion load status drifted: {candidate_id}")
    unsigned = dict(report)
    observed = unsigned.pop("report_sha256", None)
    if observed != _canonical_sha256(unsigned):
        raise RuntimeError(f"completed v3 expansion load report content drifted: {candidate_id}")


def _validate_completed_suite(suite: dict[str, Any], *, software_revision: str) -> None:
    required = {
        "schema": EXPANSION_LOAD_SUITE_SCHEMA_V3,
        "status": "CANDIDATE_POOL_V3_EXPANSION_LOAD_QUALIFICATION_COMPLETE",
        "software_revision": software_revision,
        "runner_protocol_sha256": expansion_load_runner_protocol_sha256_v3(),
        "source_freeze_sha256": EXPECTED_CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SHA256,
        "result_count": 3,
        "selection_evidence": False,
    }
    for key, expected in required.items():
        if suite.get(key) != expected:
            raise RuntimeError(f"completed v3 expansion load suite field drifted: {key}")
    if tuple(suite.get("scout_ids", ())) != EXPANSION_SCOUT_IDS_V3:
        raise RuntimeError("completed v3 expansion load suite scout order drifted")
    unsigned = dict(suite)
    observed = unsigned.pop("report_sha256", None)
    if observed != _canonical_sha256(unsigned):
        raise RuntimeError("completed v3 expansion load suite content drifted")


def _global_pair_preflight(
    artifact_root: Path, *, software_revision: str
) -> dict[str, dict[str, Any]]:
    completed: dict[str, dict[str, Any]] = {}
    partial: list[str] = []
    for candidate_id in EXPANSION_SCOUT_IDS_V3:
        candidate_root = artifact_root / candidate_id
        report_path = candidate_root / "result.json"
        if report_path.is_file():
            report = json.loads(report_path.read_text(encoding="ascii"))
            _validate_completed_report(
                report, candidate_id=candidate_id, software_revision=software_revision
            )
            completed[candidate_id] = report
        elif candidate_root.exists():
            partial.append(candidate_id)
    if partial:
        raise RuntimeError(
            "partial v3 expansion load evidence exists; all new model launches are "
            f"forbidden: {','.join(partial)}"
        )
    return completed


def _run_candidate_once(
    *,
    source: dict[str, Any],
    cli: Path,
    model_root: Path,
    artifact_root: Path,
    runtime_observation: Any,
    software_revision: str,
    timeout_seconds: int,
) -> tuple[dict[str, Any], bool]:
    candidate_id = source["candidate_id"]
    candidate_root = artifact_root / candidate_id
    result_path = candidate_root / "result.json"
    if result_path.is_file():
        report = json.loads(result_path.read_text(encoding="ascii"))
        _validate_completed_report(
            report, candidate_id=candidate_id, software_revision=software_revision
        )
        return report, False
    if candidate_root.exists():
        raise RuntimeError(
            "partial v3 expansion load evidence exists without a final result; "
            f"automatic rerun is forbidden: {candidate_root}"
        )

    model_path = model_root / candidate_id / source["artifact_filename"]
    model_sha256, model_size_bytes = _verify_model_file(model_path, source)
    command = _load_only_command(cli, model_path)
    command_sha256 = _canonical_sha256(list(command))
    attempt = {
        "schema": EXPANSION_LOAD_ATTEMPT_SCHEMA_V3,
        "candidate_id": candidate_id,
        "software_revision": software_revision,
        "runner_protocol_sha256": expansion_load_runner_protocol_sha256_v3(),
        "source_freeze_sha256": EXPECTED_CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SHA256,
        "model_file_sha256": model_sha256,
        "model_file_size_bytes": model_size_bytes,
        "command_sha256": command_sha256,
        "model_launch_authorized": True,
        "load_only": True,
        "capability_prompt": False,
        "max_attempts": 1,
        "selection_evidence": False,
    }
    candidate_root.mkdir(parents=True)
    _write_json_atomic(candidate_root / "attempt.json", attempt)

    observation, stdout, stderr = _run_raw_attempt(
        command, timeout_seconds=timeout_seconds
    )

    # Raw process evidence is persisted before any PASS/FAIL classification.
    (candidate_root / "stdout.bin").write_bytes(stdout)
    (candidate_root / "stderr.bin").write_bytes(stderr)

    status, failure, offloaded_layers, total_layers = _classify_load_only_attempt(
        observation, stderr=stderr
    )
    unsigned: dict[str, Any] = {
        "schema": EXPANSION_LOAD_RESULT_SCHEMA_V3,
        "scientific_status": (
            "candidate-development-v3-expansion-load-only-not-selection-evidence"
        ),
        "status": status,
        "candidate_id": candidate_id,
        "software_revision": software_revision,
        "runner_protocol_sha256": expansion_load_runner_protocol_sha256_v3(),
        "source_freeze_sha256": EXPECTED_CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SHA256,
        "candidate_source": source,
        "model_file_sha256": model_sha256,
        "model_file_size_bytes": model_size_bytes,
        "runtime_observation": asdict(runtime_observation),
        "command": list(command),
        "command_sha256": command_sha256,
        "load_observation": asdict(observation),
        "offloaded_layers": offloaded_layers,
        "total_layers": total_layers,
        "failure": failure,
        "attempt_count": 1,
        "load_only": True,
        "capability_prompt": False,
        "selection_evidence": False,
    }
    report = dict(unsigned)
    report["report_sha256"] = _canonical_sha256(unsigned)
    _write_json_atomic(result_path, report)
    return report, True


def run_suite(
    *,
    runtime_root: Path,
    model_root: Path,
    artifact_root: Path,
    software_revision: str,
    timeout_seconds: int = DEFAULT_EXPANSION_LOAD_TIMEOUT_SECONDS_V3,
) -> dict[str, Any]:
    if type(timeout_seconds) is not int or timeout_seconds < 1:
        raise ValueError("timeout_seconds must be a positive integer")
    validate_expansion_load_runner_protocol_v3()
    revision = _git_revision()
    if revision != software_revision:
        raise RuntimeError(
            f"software revision mismatch: checkout={revision} requested={software_revision}"
        )

    _verify_runtime_archives(runtime_root)
    cli = runtime_root / "bin" / "llama-cli.exe"
    runtime_observation = _runtime_observation(cli)
    sources = expansion_scout_sources_v3()

    # Every exact frozen model file is verified before the first model launch.
    for candidate_id in EXPANSION_SCOUT_IDS_V3:
        source = sources[candidate_id]
        model_path = model_root / candidate_id / source["artifact_filename"]
        _verify_model_file(model_path, source)

    completed = _global_pair_preflight(
        artifact_root, software_revision=software_revision
    )
    suite_path = artifact_root / "expansion-load-qualification-suite.json"
    if suite_path.is_file():
        suite = json.loads(suite_path.read_text(encoding="ascii"))
        _validate_completed_suite(suite, software_revision=software_revision)
        if len(completed) != 3:
            raise RuntimeError("completed v3 expansion load suite has missing pair evidence")
        return suite
    if suite_path.exists():
        raise RuntimeError("v3 expansion load suite path is not a file")

    artifact_root.mkdir(parents=True, exist_ok=True)
    _write_json_once(
        artifact_root / "load-runner-protocol.json",
        expansion_load_runner_protocol_payload_v3(),
    )

    results: list[dict[str, Any]] = []
    new_attempts = 0
    for candidate_id in EXPANSION_SCOUT_IDS_V3:
        report, attempted = _run_candidate_once(
            source=sources[candidate_id],
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
            f"new_model_launch={attempted} report_sha256={report['report_sha256']}",
            flush=True,
        )

    pass_count = sum(item["status"] == "LOCAL_MODEL_LOAD_PASS" for item in results)
    fail_count = len(results) - pass_count
    unsigned_suite: dict[str, Any] = {
        "schema": EXPANSION_LOAD_SUITE_SCHEMA_V3,
        "scientific_status": (
            "candidate-development-v3-expansion-load-only-not-selection-evidence"
        ),
        "status": "CANDIDATE_POOL_V3_EXPANSION_LOAD_QUALIFICATION_COMPLETE",
        "software_revision": software_revision,
        "runner_protocol_sha256": expansion_load_runner_protocol_sha256_v3(),
        "source_freeze_sha256": EXPECTED_CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SHA256,
        "scout_ids": list(EXPANSION_SCOUT_IDS_V3),
        "result_count": len(results),
        "qualified_count": pass_count,
        "failed_count": fail_count,
        "new_model_launch_count_this_invocation": new_attempts,
        "results": [
            {
                "candidate_id": item["candidate_id"],
                "status": item["status"],
                "report_sha256": item["report_sha256"],
                "model_file_sha256": item["model_file_sha256"],
                "model_file_size_bytes": item["model_file_size_bytes"],
                "offloaded_layers": item["offloaded_layers"],
                "total_layers": item["total_layers"],
                "peak_gpu_used_mib": item["load_observation"]["peak_gpu_used_mib"],
            }
            for item in results
        ],
        "selection_evidence": False,
    }
    suite = dict(unsigned_suite)
    suite["report_sha256"] = _canonical_sha256(unsigned_suite)
    _write_json_atomic(suite_path, suite)
    return suite


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the frozen v3 expansion load-only qualification suite."
    )
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_EXPANSION_LOAD_TIMEOUT_SECONDS_V3,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        suite = run_suite(
            runtime_root=args.runtime_root,
            model_root=args.model_root,
            artifact_root=args.artifact_root,
            software_revision=args.software_revision,
            timeout_seconds=args.timeout_seconds,
        )
    except BaseException as exc:
        print("status=CANDIDATE_POOL_V3_EXPANSION_LOAD_ABORT", flush=True)
        print(f"error={type(exc).__name__}: {exc}", flush=True)
        return 1

    print("status=CANDIDATE_POOL_V3_EXPANSION_LOAD_QUALIFICATION_COMPLETE", flush=True)
    print(f"qualified_count={suite['qualified_count']}", flush=True)
    print(f"failed_count={suite['failed_count']}", flush=True)
    print(
        f"new_model_launch_count_this_invocation={suite['new_model_launch_count_this_invocation']}",
        flush=True,
    )
    print(f"report_sha256={suite['report_sha256']}", flush=True)
    print(
        f"runner_protocol_sha256={expansion_load_runner_protocol_sha256_v3()}",
        flush=True,
    )
    print("selection_evidence=False", flush=True)
    return 0


validate_expansion_load_runner_protocol_v3()


if __name__ == "__main__":
    raise SystemExit(main())
