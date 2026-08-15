"""Restart-safe formal load qualification for the candidate-pool v2 challengers.

The three challenger identities are frozen before this module is used. Each challenger
gets at most one model load/generation attempt. A completed PASS or FAIL report is
terminal and is reused without inference. An artifact directory containing an attempt
marker but no final report blocks automatic rerun so an interrupted expensive call is
never silently repeated.

This is candidate-development evidence only, never selection evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from .candidate_pool_v2_source_freeze import (
    FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256,
    QUALIFICATION_PROTOCOL_SHA256,
    candidate_pool_v2_source_freeze_payload,
)
from .local_model_load_preflight import (
    _canonical_json_bytes,
    _git_revision,
    _load_command,
    _run_load,
    _runtime_observation,
    _sha256_file,
    _verify_runtime_archives,
)

LOAD_PLAN_SCHEMA_V2 = "plural-cognition-candidate-pool-v2-load-qualification-plan-v1"
LOAD_REPORT_SCHEMA_V2 = "plural-cognition-candidate-pool-v2-load-qualification-result-v1"
LOAD_SUITE_SCHEMA_V2 = "plural-cognition-candidate-pool-v2-load-qualification-suite-v1"
EXPECTED_LOAD_PLAN_SHA256_V2 = "db6c3f0383e3509cd915b1500291e68fb380be93c138db132f4f0944d127d23a"
SOURCE_FREEZE_REVISION_V2 = "03431c4b7b6ae51385afbd910030229c4792e3eb"
CHALLENGER_IDS_V2 = (
    "gpt-oss-20b-mxfp4",
    "phi-4-reasoning-plus-14b-q5km",
    "devstral-small-2-24b-q4km",
)
LOAD_CONTEXT_TOKENS_V2 = 4096
LOAD_PREDICT_TOKENS_V2 = 32
DEFAULT_TIMEOUT_SECONDS_V2 = 900


def load_qualification_plan_payload_v2() -> dict[str, Any]:
    return {
        "schema": LOAD_PLAN_SCHEMA_V2,
        "scientific_status": "candidate-development-v2-load-qualification-not-selection-evidence",
        "candidate_pool_v2_protocol_sha256": QUALIFICATION_PROTOCOL_SHA256,
        "candidate_pool_v2_source_freeze_sha256": FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256,
        "candidate_pool_v2_source_freeze_revision": SOURCE_FREEZE_REVISION_V2,
        "challenger_ids": list(CHALLENGER_IDS_V2),
        "runtime": {
            "llama_cpp_build": "b10361",
            "llama_cpp_revision": "14e78ddef7a2061e7d5a31dce4eb7ee0bcdbc840",
            "device": "CUDA0",
        },
        "load_probe": {
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
            "attempts_per_challenger": 1,
        },
        "evidence_policy": {
            "completed_report_reused_without_inference": True,
            "partial_attempt_blocks_rerun": True,
            "candidate_load_failures_are_terminal_for_cycle": True,
            "artifact_substitution_after_outcome": False,
            "selection_evidence": False,
        },
    }


FINAL_LOAD_PLAN_SHA256_V2 = hashlib.sha256(
    _canonical_json_bytes(load_qualification_plan_payload_v2())
).hexdigest()
if FINAL_LOAD_PLAN_SHA256_V2 != EXPECTED_LOAD_PLAN_SHA256_V2:
    raise AssertionError("candidate-pool v2 load qualification plan identity drifted")


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


def _verify_challenger_file(path: Path, candidate: dict[str, Any]) -> tuple[str, int]:
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


def _candidate_load_failure(exc: RuntimeError) -> bool:
    text = str(exc)
    return text.startswith(
        (
            "llama-cli load/generation failed with exit ",
            "llama-cli load/generation exceeded ",
            "llama-cli produced no generated stdout",
            "llama-cli log did not prove GPU layer offload",
            "model was not fully offloaded to GPU:",
        )
    )


def _validate_completed_report(
    report: dict[str, Any], *, candidate_id: str, software_revision: str
) -> None:
    if report.get("schema") != LOAD_REPORT_SCHEMA_V2:
        raise RuntimeError(f"completed load report schema drifted for {candidate_id}")
    if report.get("candidate_id") != candidate_id:
        raise RuntimeError(f"completed load report candidate drifted for {candidate_id}")
    if report.get("software_revision") != software_revision:
        raise RuntimeError(f"completed load report software revision drifted for {candidate_id}")
    if report.get("load_plan_sha256") != FINAL_LOAD_PLAN_SHA256_V2:
        raise RuntimeError(f"completed load report plan drifted for {candidate_id}")
    if report.get("source_freeze_sha256") != FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256:
        raise RuntimeError(f"completed load report source freeze drifted for {candidate_id}")
    if report.get("status") not in {"LOCAL_MODEL_LOAD_PASS", "LOCAL_MODEL_LOAD_FAIL"}:
        raise RuntimeError(f"completed load report status drifted for {candidate_id}")


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
    report_path = candidate_root / "load-preflight.json"
    attempt_path = candidate_root / "attempt.json"

    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="ascii"))
        _validate_completed_report(
            report, candidate_id=candidate_id, software_revision=software_revision
        )
        return report, False
    if candidate_root.exists():
        raise RuntimeError(
            "partial v2 load evidence exists without a final report; automatic rerun is "
            f"forbidden: {candidate_root}"
        )

    model_path = model_root / candidate_id / candidate["filename"]
    model_sha256, model_size_bytes = _verify_challenger_file(model_path, candidate)
    command = _load_command(
        cli,
        model_path,
        context_tokens=LOAD_CONTEXT_TOKENS_V2,
        predict_tokens=LOAD_PREDICT_TOKENS_V2,
    )
    command_sha256 = hashlib.sha256(_canonical_json_bytes(list(command))).hexdigest()
    attempt = {
        "schema": "plural-cognition-candidate-pool-v2-load-attempt-v1",
        "candidate_id": candidate_id,
        "software_revision": software_revision,
        "load_plan_sha256": FINAL_LOAD_PLAN_SHA256_V2,
        "source_freeze_sha256": FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256,
        "model_file_sha256": model_sha256,
        "model_file_size_bytes": model_size_bytes,
        "command_sha256": command_sha256,
        "inference_attempt_authorized": True,
        "max_attempts": 1,
    }
    candidate_root.mkdir(parents=True)
    _write_json_atomic(attempt_path, attempt)

    try:
        load, stdout, stderr = _run_load(command, timeout_seconds=timeout_seconds)
    except RuntimeError as exc:
        if not _candidate_load_failure(exc):
            raise
        report = {
            "schema": LOAD_REPORT_SCHEMA_V2,
            "scientific_status": "candidate-development-v2-load-qualification-not-selection-evidence",
            "status": "LOCAL_MODEL_LOAD_FAIL",
            "candidate_id": candidate_id,
            "software_revision": software_revision,
            "load_plan_sha256": FINAL_LOAD_PLAN_SHA256_V2,
            "source_freeze_sha256": FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256,
            "candidate_source": candidate,
            "model_file_sha256": model_sha256,
            "model_file_size_bytes": model_size_bytes,
            "runtime_observation": asdict(runtime_observation),
            "command": list(command),
            "command_sha256": command_sha256,
            "failure": str(exc),
            "attempt_count": 1,
            "selection_evidence": False,
        }
        report_sha256 = hashlib.sha256(_canonical_json_bytes(report)).hexdigest()
        report["report_sha256"] = report_sha256
        _write_json_atomic(report_path, report)
        return report, True

    (candidate_root / "stdout.bin").write_bytes(stdout)
    (candidate_root / "stderr.bin").write_bytes(stderr)
    report = {
        "schema": LOAD_REPORT_SCHEMA_V2,
        "scientific_status": "candidate-development-v2-load-qualification-not-selection-evidence",
        "status": "LOCAL_MODEL_LOAD_PASS",
        "candidate_id": candidate_id,
        "software_revision": software_revision,
        "load_plan_sha256": FINAL_LOAD_PLAN_SHA256_V2,
        "source_freeze_sha256": FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256,
        "candidate_source": candidate,
        "model_file_sha256": model_sha256,
        "model_file_size_bytes": model_size_bytes,
        "runtime_observation": asdict(runtime_observation),
        "command": list(command),
        "command_sha256": command_sha256,
        "load_observation": asdict(load),
        "attempt_count": 1,
        "selection_evidence": False,
    }
    report_sha256 = hashlib.sha256(_canonical_json_bytes(report)).hexdigest()
    report["report_sha256"] = report_sha256
    _write_json_atomic(report_path, report)
    return report, True


def run_suite(
    *,
    runtime_root: Path,
    model_root: Path,
    artifact_root: Path,
    software_revision: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS_V2,
) -> dict[str, Any]:
    if type(timeout_seconds) is not int or timeout_seconds < 1:
        raise ValueError("timeout_seconds must be a positive integer")
    revision = _git_revision()
    if revision != software_revision:
        raise RuntimeError(f"software revision mismatch: checkout={revision} requested={software_revision}")

    _verify_runtime_archives(runtime_root)
    cli = runtime_root / "bin" / "llama-cli.exe"
    runtime_observation = _runtime_observation(cli)
    challengers = _challengers()

    # Verify all three immutable model files before authorizing the first expensive call.
    for candidate_id in CHALLENGER_IDS_V2:
        candidate = challengers[candidate_id]
        model_path = model_root / candidate_id / candidate["filename"]
        _verify_challenger_file(model_path, candidate)

    artifact_root.mkdir(parents=True, exist_ok=True)
    plan_path = artifact_root / "load-plan.json"
    if plan_path.exists():
        existing = plan_path.read_bytes().rstrip(b"\r\n")
        if existing != _canonical_json_bytes(load_qualification_plan_payload_v2()):
            raise RuntimeError("existing v2 load-plan artifact drifted")
    else:
        _write_json_atomic(plan_path, load_qualification_plan_payload_v2())

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
        "schema": LOAD_SUITE_SCHEMA_V2,
        "scientific_status": "candidate-development-v2-load-qualification-not-selection-evidence",
        "status": "CANDIDATE_POOL_V2_LOAD_QUALIFICATION_COMPLETE",
        "software_revision": software_revision,
        "load_plan_sha256": FINAL_LOAD_PLAN_SHA256_V2,
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
            }
            for item in results
        ],
        "selection_evidence": False,
    }
    suite_sha256 = hashlib.sha256(_canonical_json_bytes(suite)).hexdigest()
    suite["report_sha256"] = suite_sha256
    _write_json_atomic(artifact_root / "load-qualification-suite.json", suite)
    return suite


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run or safely resume the three predeclared candidate-pool v2 load qualifications."
    )
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS_V2)
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
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"status=CANDIDATE_POOL_V2_LOAD_QUALIFICATION_ABORT\nerror={exc}")
        return 2

    print("status=CANDIDATE_POOL_V2_LOAD_QUALIFICATION_COMPLETE")
    print(f"report_sha256={suite['report_sha256']}")
    print(f"load_plan_sha256={suite['load_plan_sha256']}")
    print(f"source_freeze_sha256={suite['source_freeze_sha256']}")
    print(f"qualified_count={suite['qualified_count']}/3")
    print(f"failed_count={suite['failed_count']}/3")
    print(
        "new_inference_attempt_count_this_invocation="
        f"{suite['new_inference_attempt_count_this_invocation']}"
    )
    print(f"output={args.artifact_root / 'load-qualification-suite.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
