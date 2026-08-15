"""Restart-safe six-by-six candidate-pool v2 calibration gate.

This runner consumes only the existing calibration matrix.  It never imports or
constructs selection material.  Every candidate/task pair gets at most one model
inference attempt: an attempt marker is written before the call, a completed pair
is reused without inference, and any partial pair blocks the whole invocation
before another model call is authorized.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from .artifacts import CollectiveStage, ResourceUsage, StageArtifact
from .candidate_pool_v2_calibration_protocol import (
    CALIBRATION_BATCH_THREADS_V2,
    CALIBRATION_BATCH_TOKENS_V2,
    CALIBRATION_CONTEXT_TOKENS_V2,
    CALIBRATION_LOG_VERBOSITY_V2,
    CALIBRATION_MATRIX_SOURCE_GIT_BLOB_SHA1,
    CALIBRATION_MICROBATCH_TOKENS_V2,
    CALIBRATION_PREDICT_TOKENS_V2,
    CALIBRATION_TASK_IDS_V2,
    CALIBRATION_THREADS_V2,
    CANDIDATE_IDS_V2,
    CHALLENGER_IDS_V2,
    FINAL_CALIBRATION_PROTOCOL_SHA256_V2,
    INCUMBENT_IDS_V2,
    LOAD_OBSERVER_REPAIR_PLAN_SHA256_V2,
    LOAD_OBSERVER_REPAIR_SUITE_FILE_SHA256_V2,
    LOAD_OBSERVER_REPAIR_SUITE_REPORT_SHA256_V2,
    MINIMUM_SOLVED_COUNT_V2,
    REQUIRED_PARSE_VALID_COUNT_V2,
    SOURCE_FREEZE_SHA256_V2,
    candidate_pool_v2_calibration_protocol_payload,
)
from .candidate_pool_v2_full_file import (
    extract_full_file_patch_v2,
    solver_prompt_transport_v2,
)
from .candidate_pool_v2_source_freeze import candidate_pool_v2_source_freeze_payload
from .content_store import FileContentStore
from .local_candidate_pool_v2_load_observer_repair import _run_raw_attempt
from .local_model_load_preflight import (
    OFFLOAD_PATTERN,
    _git_revision,
    _runtime_observation,
    _sha256_file,
    _verify_runtime_archives,
)
from .local_models import LOCAL_MODEL_SOURCE_FREEZE_V2
from .local_operational_freeze_v1 import FINAL_RESOURCE_BUDGET_SHA256
from .local_raw_calibration import validate_patch_against_blueprint
from .local_raw_calibration_v6 import extract_assistant_content_v6
from .qualified_docker import probe_qualified_docker_configuration
from .repository_surgery import PatchFormat, RepositorySurgerySubmission
from .repository_surgery_calibration_matrix import (
    _evaluate_patch,
    _metric,
    build_matrix_material,
    calibration_blueprints,
)

CALIBRATION_PAIR_SCHEMA_V2 = "plural-cognition-candidate-pool-v2-calibration-pair-v1"
CALIBRATION_ATTEMPT_SCHEMA_V2 = "plural-cognition-candidate-pool-v2-calibration-attempt-v1"
CALIBRATION_SUITE_SCHEMA_V2 = "plural-cognition-candidate-pool-v2-calibration-suite-v1"
CALIBRATION_PLAN_SCHEMA_V2 = "plural-cognition-candidate-pool-v2-calibration-plan-v1"
DEFAULT_TIMEOUT_SECONDS_V2 = 900
EXPECTED_PREDECESSOR_RESOURCE_BUDGET_SHA256 = (
    "5508ba6ff0f093fd4cf10505513c41951bb1d454992fe6bb13a48bae83c803f7"
)

_EXPECTED_CHALLENGER_REPORT_SHA256 = {
    "gpt-oss-20b-mxfp4": "84d098919a595ba94bd509e396c03afc4f09fec857380d95fddea719f74d1e2f",
    "phi-4-reasoning-plus-14b-q5km": "99f970f90d241afe0d1d2dcdc5ed75ab62235f08552a7a0736d63dfb14d513f8",
    "devstral-small-2-24b-q4km": "d36d20776583919b12609fe75c50e55ce707d4ce3f2d00c02c2f9bffa4fbee27",
}
_PROMPT_TOKEN_RE = re.compile(r"prompt eval time\s*=.*?/\s*(\d+)\s+tokens", re.IGNORECASE)
_OUTPUT_TOKEN_RE = re.compile(r"eval time\s*=.*?/\s*(\d+)\s+runs", re.IGNORECASE)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(_canonical_json_bytes(payload) + b"\n")
    os.replace(temporary, path)


def _git_blob_sha1(path: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", f"HEAD:{path}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"could not resolve git blob for {path}: {completed.stderr.strip()}")
    value = completed.stdout.strip()
    if len(value) != 40:
        raise RuntimeError(f"unexpected git blob identity for {path}: {value!r}")
    return value


def _pair_id(candidate_id: str, task_id: str) -> str:
    return hashlib.sha256(
        _canonical_json_bytes(
            {
                "schema": "plural-cognition-candidate-pool-v2-calibration-pair-id-v1",
                "candidate_id": candidate_id,
                "task_id": task_id,
                "protocol_sha256": FINAL_CALIBRATION_PROTOCOL_SHA256_V2,
            }
        )
    ).hexdigest()


def _pair_root(artifact_root: Path, candidate_id: str, task_id: str) -> Path:
    return artifact_root / "pairs" / candidate_id / task_id


def _pair_state(path: Path) -> str:
    result = path / "result.json"
    if result.is_file():
        return "complete"
    if path.exists():
        return "partial"
    return "missing"


def _candidate_passed(parse_valid_count: int, solved_count: int) -> bool:
    return (
        parse_valid_count == REQUIRED_PARSE_VALID_COUNT_V2
        and solved_count >= MINIMUM_SOLVED_COUNT_V2
    )


def _candidate_sources() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for candidate_id in INCUMBENT_IDS_V2:
        source = LOCAL_MODEL_SOURCE_FREEZE_V2.candidate(candidate_id)
        result[candidate_id] = {
            "candidate_id": candidate_id,
            "source_class": "unchanged-incumbent-v1-source-freeze",
            "filename": source.filename,
            "artifact_size_bytes": source.size_bytes,
            "artifact_sha256": source.artifact_sha256,
            "source_identity_sha256": source.sha256,
        }

    challenger_payload = candidate_pool_v2_source_freeze_payload()
    challengers = {item["candidate_id"]: item for item in challenger_payload["challengers"]}
    if tuple(challengers) != CHALLENGER_IDS_V2:
        raise AssertionError("v2 challenger source order drifted")
    for candidate_id in CHALLENGER_IDS_V2:
        source = challengers[candidate_id]
        source_identity = hashlib.sha256(_canonical_json_bytes(source)).hexdigest()
        result[candidate_id] = {
            "candidate_id": candidate_id,
            "source_class": "candidate-pool-v2-source-freeze",
            "filename": source["filename"],
            "artifact_size_bytes": source["artifact_size_bytes"],
            "artifact_sha256": source["artifact_sha256"],
            "source_identity_sha256": source_identity,
        }
    if tuple(result) != CANDIDATE_IDS_V2:
        raise AssertionError("v2 calibration candidate source order drifted")
    return result


def _verify_model_files(model_root: Path, sources: dict[str, dict[str, Any]]) -> None:
    for candidate_id in CANDIDATE_IDS_V2:
        source = sources[candidate_id]
        path = model_root / candidate_id / source["filename"]
        if not path.is_file():
            raise RuntimeError(f"required v2 calibration model is missing: {path}")
        size = path.stat().st_size
        if size != int(source["artifact_size_bytes"]):
            raise RuntimeError(
                f"model size mismatch for {candidate_id}: {size} != {source['artifact_size_bytes']}"
            )
        digest = _sha256_file(path)
        if digest != source["artifact_sha256"]:
            raise RuntimeError(f"model SHA-256 mismatch for {candidate_id}: {digest}")


def _verify_load_observer_repair(repair_root: Path) -> None:
    suite_path = repair_root / "load-observer-repair-suite.json"
    if not suite_path.is_file():
        raise RuntimeError(f"successful load observer-repair suite is missing: {suite_path}")
    file_sha = _sha256_file(suite_path)
    if file_sha != LOAD_OBSERVER_REPAIR_SUITE_FILE_SHA256_V2:
        raise RuntimeError(f"load observer-repair suite file drifted: {file_sha}")
    suite = json.loads(suite_path.read_text(encoding="ascii"))
    required = {
        "schema": "plural-cognition-candidate-pool-v2-load-observer-repair-suite-v1",
        "scientific_status": "candidate-development-v2-load-observer-repair-not-selection-evidence",
        "recovery_plan_sha256": LOAD_OBSERVER_REPAIR_PLAN_SHA256_V2,
        "invalidated_suite_file_sha256": "a15af45ddc9c95e779beaa22cc9389be7029b42a623ed7bd989794823074ed60",
        "source_freeze_sha256": SOURCE_FREEZE_SHA256_V2,
        "result_count": 3,
        "qualified_count": 3,
        "failed_count": 0,
        "report_sha256": LOAD_OBSERVER_REPAIR_SUITE_REPORT_SHA256_V2,
        "selection_evidence": False,
    }
    for key, expected in required.items():
        if suite.get(key) != expected:
            raise RuntimeError(f"load observer-repair suite field drifted: {key}")
    if tuple(suite.get("challenger_ids", ())) != CHALLENGER_IDS_V2:
        raise RuntimeError("load observer-repair challenger order drifted")
    summaries = {item["candidate_id"]: item for item in suite.get("results", [])}
    if tuple(summaries) != CHALLENGER_IDS_V2:
        raise RuntimeError("load observer-repair result order drifted")
    for candidate_id in CHALLENGER_IDS_V2:
        item = summaries[candidate_id]
        if item.get("status") != "LOCAL_MODEL_LOAD_PASS":
            raise RuntimeError(f"challenger no longer load-qualified: {candidate_id}")
        if item.get("report_sha256") != _EXPECTED_CHALLENGER_REPORT_SHA256[candidate_id]:
            raise RuntimeError(f"challenger load report identity drifted: {candidate_id}")


def _selected_blueprints() -> tuple[Any, ...]:
    blueprints = calibration_blueprints()
    ids = tuple(item.task_id for item in blueprints)
    if ids != CALIBRATION_TASK_IDS_V2:
        raise RuntimeError(f"calibration task identities drifted: {ids!r}")
    return blueprints


def _load_command(
    *, cli: Path, model_path: Path, prompt: bytes, capture: Path
) -> tuple[str, ...]:
    return (
        str(cli),
        "-m", str(model_path),
        "-c", str(CALIBRATION_CONTEXT_TOKENS_V2),
        "-n", str(CALIBRATION_PREDICT_TOKENS_V2),
        "-ngl", "all",
        "-dev", "CUDA0",
        "-fit", "off",
        "-sm", "none",
        "-mg", "0",
        "-ctk", "f16",
        "-ctv", "f16",
        "-lm", "mmap",
        "--offline",
        "--temp", "0",
        "--seed", "1",
        "-t", str(CALIBRATION_THREADS_V2),
        "-tb", str(CALIBRATION_BATCH_THREADS_V2),
        "-b", str(CALIBRATION_BATCH_TOKENS_V2),
        "-ub", str(CALIBRATION_MICROBATCH_TOKENS_V2),
        "-fa", "auto",
        "-cnv",
        "--simple-io",
        "--output-file", str(capture),
        "--no-escape",
        "--no-display-prompt",
        "--log-colors", "off",
        "--no-log-timestamps",
        "--log-verbosity", str(CALIBRATION_LOG_VERBOSITY_V2),
        "--perf",
        "-st",
        "-p", prompt.decode("utf-8"),
    )


def _token_counts(stderr: bytes) -> tuple[int, int, bool]:
    text = stderr.decode("utf-8", errors="replace")
    prompt = _PROMPT_TOKEN_RE.findall(text)
    output = _OUTPUT_TOKEN_RE.findall(text)
    if not prompt or not output:
        return 0, 0, False
    return int(prompt[-1]), int(output[-1]), True


def _producer_configuration_sha256(source_identity_sha256: str) -> str:
    return hashlib.sha256(
        _canonical_json_bytes(
            {
                "schema": "plural-cognition-candidate-pool-v2-calibration-producer-config-v1",
                "source_identity_sha256": source_identity_sha256,
                "protocol_sha256": FINAL_CALIBRATION_PROTOCOL_SHA256_V2,
            }
        )
    ).hexdigest()


def _finalize_pair(pair_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    unsigned = dict(payload)
    unsigned.pop("report_sha256", None)
    report_sha256 = hashlib.sha256(_canonical_json_bytes(unsigned)).hexdigest()
    result = dict(unsigned)
    result["report_sha256"] = report_sha256
    _write_json_atomic(pair_root / "result.json", result)
    return result


def _validate_completed_pair(
    report: dict[str, Any], *, candidate_id: str, task_id: str, software_revision: str
) -> None:
    if report.get("schema") != CALIBRATION_PAIR_SCHEMA_V2:
        raise RuntimeError(f"completed calibration pair schema drifted: {candidate_id}/{task_id}")
    expected = {
        "candidate_id": candidate_id,
        "task_id": task_id,
        "pair_id": _pair_id(candidate_id, task_id),
        "software_revision": software_revision,
        "protocol_sha256": FINAL_CALIBRATION_PROTOCOL_SHA256_V2,
        "selection_evidence": False,
    }
    for key, value in expected.items():
        if report.get(key) != value:
            raise RuntimeError(f"completed calibration pair field drifted: {candidate_id}/{task_id}:{key}")
    unsigned = dict(report)
    observed = unsigned.pop("report_sha256", None)
    expected_sha = hashlib.sha256(_canonical_json_bytes(unsigned)).hexdigest()
    if observed != expected_sha:
        raise RuntimeError(f"completed calibration pair content drifted: {candidate_id}/{task_id}")


def _base_pair_payload(
    *,
    candidate_id: str,
    task_id: str,
    software_revision: str,
    source: dict[str, Any],
    model_path: Path,
    task_sha256: str,
    prompt_sha256: str,
    command_sha256: str,
    observation: Any,
    process_stdout: bytes,
    stderr: bytes,
) -> dict[str, Any]:
    input_tokens, output_tokens, token_counts_observed = _token_counts(stderr)
    return {
        "schema": CALIBRATION_PAIR_SCHEMA_V2,
        "scientific_status": "candidate-development-v2-calibration-only-not-selection-evidence",
        "status": "CANDIDATE_POOL_V2_CALIBRATION_PAIR_COMPLETE",
        "candidate_id": candidate_id,
        "task_id": task_id,
        "pair_id": _pair_id(candidate_id, task_id),
        "software_revision": software_revision,
        "protocol_sha256": FINAL_CALIBRATION_PROTOCOL_SHA256_V2,
        "source_identity_sha256": source["source_identity_sha256"],
        "model_file_sha256": source["artifact_sha256"],
        "model_file_size_bytes": model_path.stat().st_size,
        "task_sha256": task_sha256,
        "prompt_sha256": prompt_sha256,
        "command_sha256": command_sha256,
        "attempt_observation": asdict(observation),
        "process_stdout_sha256": hashlib.sha256(process_stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "token_counts_observed": token_counts_observed,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "selection_evidence": False,
    }


def _run_pair_once(
    *,
    candidate_id: str,
    source: dict[str, Any],
    blueprint: Any,
    material: Any,
    cli: Path,
    model_root: Path,
    artifact_root: Path,
    store: FileContentStore,
    configuration: Any,
    staging_root: Path,
    software_revision: str,
    timeout_seconds: int,
    docker_executable: str,
) -> tuple[dict[str, Any], bool]:
    task_id = blueprint.task_id
    pair_root = _pair_root(artifact_root, candidate_id, task_id)
    state = _pair_state(pair_root)
    if state == "complete":
        report = json.loads((pair_root / "result.json").read_text(encoding="ascii"))
        _validate_completed_pair(
            report,
            candidate_id=candidate_id,
            task_id=task_id,
            software_revision=software_revision,
        )
        return report, False
    if state == "partial":
        raise RuntimeError(
            f"partial v2 calibration pair blocks automatic rerun: {candidate_id}/{task_id}"
        )

    prompt = solver_prompt_transport_v2(blueprint)
    prompt_sha256 = store.put_bytes(prompt)
    pair_root.mkdir(parents=True)
    capture = pair_root / "transcript.txt"
    model_path = model_root / candidate_id / source["filename"]
    command = _load_command(cli=cli, model_path=model_path, prompt=prompt, capture=capture)
    command_sha256 = hashlib.sha256(_canonical_json_bytes(list(command))).hexdigest()
    attempt = {
        "schema": CALIBRATION_ATTEMPT_SCHEMA_V2,
        "candidate_id": candidate_id,
        "task_id": task_id,
        "pair_id": _pair_id(candidate_id, task_id),
        "software_revision": software_revision,
        "protocol_sha256": FINAL_CALIBRATION_PROTOCOL_SHA256_V2,
        "model_file_sha256": source["artifact_sha256"],
        "task_sha256": material.visible_task.sha256,
        "prompt_sha256": prompt_sha256,
        "command_sha256": command_sha256,
        "inference_attempt_authorized": True,
        "max_attempts": 1,
        "selection_evidence": False,
    }
    _write_json_atomic(pair_root / "attempt.json", attempt)

    observation, process_stdout, stderr = _run_raw_attempt(
        command, timeout_seconds=timeout_seconds
    )
    (pair_root / "process-stdout.bin").write_bytes(process_stdout)
    (pair_root / "stderr.bin").write_bytes(stderr)
    _write_json_atomic(pair_root / "attempt-observation.json", asdict(observation))
    if observation.monitor_error is not None:
        raise RuntimeError(
            f"calibration resource monitor failed for {candidate_id}/{task_id}: "
            f"{observation.monitor_error}"
        )

    base = _base_pair_payload(
        candidate_id=candidate_id,
        task_id=task_id,
        software_revision=software_revision,
        source=source,
        model_path=model_path,
        task_sha256=material.visible_task.sha256,
        prompt_sha256=prompt_sha256,
        command_sha256=command_sha256,
        observation=observation,
        process_stdout=process_stdout,
        stderr=stderr,
    )

    stderr_text = stderr.decode("utf-8", errors="replace")
    offload_matches = OFFLOAD_PATTERN.findall(stderr_text)
    offloaded_layers: int | None = None
    total_layers: int | None = None
    if offload_matches:
        offloaded_layers, total_layers = (int(value) for value in offload_matches[-1])

    if observation.timed_out or observation.exit_code != 0:
        failure = (
            f"llama-cli exceeded {timeout_seconds} seconds"
            if observation.timed_out
            else f"llama-cli exited {observation.exit_code}"
        )
        base.update(
            {
                "inference_valid": False,
                "inference_failure": failure,
                "offloaded_layers": offloaded_layers,
                "total_layers": total_layers,
                "transcript_sha256": hashlib.sha256(capture.read_bytes()).hexdigest() if capture.is_file() else None,
                "assistant_sha256": None,
                "reasoning_sha256": None,
                "raw_artifact_sha256": None,
                "parse_valid": False,
                "parse_mode": None,
                "parse_error": failure,
                "patch_sha256": None,
                "submission_sha256": None,
                "evaluation_sha256": None,
                "exact_accuracy": 0.0,
                "evaluator_valid_rate": 0.0,
                "solved": False,
            }
        )
        return _finalize_pair(pair_root, base), True

    if not offload_matches:
        raise RuntimeError(
            f"successful calibration call lacks trace offload evidence: {candidate_id}/{task_id}"
        )
    if offloaded_layers != total_layers:
        failure = f"model was not fully offloaded: {offloaded_layers}/{total_layers}"
        base.update(
            {
                "inference_valid": False,
                "inference_failure": failure,
                "offloaded_layers": offloaded_layers,
                "total_layers": total_layers,
                "transcript_sha256": hashlib.sha256(capture.read_bytes()).hexdigest() if capture.is_file() else None,
                "assistant_sha256": None,
                "reasoning_sha256": None,
                "raw_artifact_sha256": None,
                "parse_valid": False,
                "parse_mode": None,
                "parse_error": failure,
                "patch_sha256": None,
                "submission_sha256": None,
                "evaluation_sha256": None,
                "exact_accuracy": 0.0,
                "evaluator_valid_rate": 0.0,
                "solved": False,
            }
        )
        return _finalize_pair(pair_root, base), True

    if not capture.is_file():
        raise RuntimeError(f"calibration transcript is missing: {capture}")
    transcript = capture.read_bytes()
    transcript_sha256 = hashlib.sha256(transcript).hexdigest()
    try:
        assistant, reasoning = extract_assistant_content_v6(
            transcript=transcript, prompt=prompt
        )
    except ValueError as exc:
        failure = f"assistant transport invalid: {exc}"
        base.update(
            {
                "inference_valid": True,
                "inference_failure": None,
                "offloaded_layers": offloaded_layers,
                "total_layers": total_layers,
                "transcript_sha256": transcript_sha256,
                "assistant_sha256": None,
                "reasoning_sha256": None,
                "raw_artifact_sha256": None,
                "parse_valid": False,
                "parse_mode": None,
                "parse_error": failure,
                "patch_sha256": None,
                "submission_sha256": None,
                "evaluation_sha256": None,
                "exact_accuracy": 0.0,
                "evaluator_valid_rate": 0.0,
                "solved": False,
            }
        )
        return _finalize_pair(pair_root, base), True

    (pair_root / "assistant.txt").write_bytes(assistant)
    reasoning_sha256: str | None = None
    if reasoning is not None:
        (pair_root / "reasoning.txt").write_bytes(reasoning)
        reasoning_sha256 = hashlib.sha256(reasoning).hexdigest()

    assistant_sha256 = store.put_bytes(assistant)
    resources = ResourceUsage(
        input_tokens=int(base["input_tokens"]),
        output_tokens=int(base["output_tokens"]),
        inference_calls=1,
        wall_time_ms=max(0, round(observation.elapsed_seconds * 1000)),
        accelerator_time_ms=max(0, round(observation.elapsed_seconds * 1000)),
        peak_accelerator_bytes=observation.peak_gpu_used_mib * 1024 * 1024,
        peak_ram_bytes=observation.peak_process_rss_bytes or 0,
    )
    raw_artifact = StageArtifact(
        stage=CollectiveStage.RAW_MIND_OUTPUT,
        task=material.visible_task.task,
        run_id=f"candidate-pool-v2-calibration:{candidate_id}:{task_id}",
        producer_id=candidate_id,
        producer_configuration_sha256=_producer_configuration_sha256(
            source["source_identity_sha256"]
        ),
        protocol_sha256=FINAL_CALIBRATION_PROTOCOL_SHA256_V2,
        software_revision=software_revision,
        content_sha256=assistant_sha256,
        resources=resources,
    )
    if store.put_bytes(raw_artifact.canonical_bytes()) != raw_artifact.sha256:
        raise AssertionError("v2 calibration raw artifact storage identity mismatch")

    parse_valid = False
    parse_mode: str | None = None
    parse_error: str | None = None
    patch_sha256: str | None = None
    submission_sha256: str | None = None
    evaluation_sha256: str | None = None
    exact_accuracy = 0.0
    evaluator_valid_rate = 0.0
    solved = False
    try:
        patch, parse_mode = extract_full_file_patch_v2(assistant, blueprint)
        validate_patch_against_blueprint(patch, blueprint)
    except ValueError as exc:
        parse_error = str(exc)
    else:
        parse_valid = True
        patch_sha256 = store.put_bytes(patch)
        submission = RepositorySurgerySubmission(
            task_id=material.visible_task.task.task_id,
            task_payload_sha256=material.visible_task.task.payload_sha256,
            producer_artifact_sha256=raw_artifact.sha256,
            patch_sha256=patch_sha256,
            patch_format=PatchFormat.UNIFIED_DIFF,
            patch_size_bytes=len(patch),
        )
        submission_sha256 = store.put_bytes(submission.canonical_bytes())
        if submission_sha256 != submission.sha256:
            raise AssertionError("v2 calibration submission storage identity mismatch")
        evaluation = _evaluate_patch(
            material=material,
            configuration=configuration,
            store=store,
            staging_root=staging_root,
            patch_sha256=patch_sha256,
            submission_sha256=submission.sha256,
            artifact_sha256=submission.sha256,
            docker_executable=docker_executable,
        )
        evaluation_sha256 = store.put_bytes(evaluation.canonical_bytes())
        if evaluation_sha256 != evaluation.sha256:
            raise AssertionError("v2 calibration evaluation storage identity mismatch")
        exact_accuracy = _metric(evaluation, "exact_accuracy")
        evaluator_valid_rate = _metric(evaluation, "valid_rate")
        solved = bool(evaluation.qualified)

    base.update(
        {
            "inference_valid": True,
            "inference_failure": None,
            "offloaded_layers": offloaded_layers,
            "total_layers": total_layers,
            "transcript_sha256": transcript_sha256,
            "assistant_sha256": assistant_sha256,
            "reasoning_sha256": reasoning_sha256,
            "raw_artifact_sha256": raw_artifact.sha256,
            "parse_valid": parse_valid,
            "parse_mode": parse_mode,
            "parse_error": parse_error,
            "patch_sha256": patch_sha256,
            "submission_sha256": submission_sha256,
            "evaluation_sha256": evaluation_sha256,
            "exact_accuracy": exact_accuracy,
            "evaluator_valid_rate": evaluator_valid_rate,
            "solved": solved,
        }
    )
    return _finalize_pair(pair_root, base), True


def _preflight_pair_states(
    artifact_root: Path, *, software_revision: str
) -> tuple[int, list[dict[str, Any]]]:
    complete = 0
    reports: list[dict[str, Any]] = []
    for candidate_id in CANDIDATE_IDS_V2:
        for task_id in CALIBRATION_TASK_IDS_V2:
            root = _pair_root(artifact_root, candidate_id, task_id)
            state = _pair_state(root)
            if state == "partial":
                raise RuntimeError(
                    f"partial v2 calibration pair blocks all new inference: {candidate_id}/{task_id}"
                )
            if state == "complete":
                report = json.loads((root / "result.json").read_text(encoding="ascii"))
                _validate_completed_pair(
                    report,
                    candidate_id=candidate_id,
                    task_id=task_id,
                    software_revision=software_revision,
                )
                complete += 1
                reports.append(report)
    return complete, reports


def run_calibration(
    *,
    runtime_root: Path,
    model_root: Path,
    load_repair_root: Path,
    artifact_root: Path,
    software_revision: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS_V2,
    docker_executable: str = "docker",
) -> dict[str, Any]:
    if type(timeout_seconds) is not int or timeout_seconds < 1:
        raise ValueError("timeout_seconds must be a positive integer")
    if _git_revision() != software_revision:
        raise RuntimeError("software revision argument does not match current checkout")
    if FINAL_RESOURCE_BUDGET_SHA256 != EXPECTED_PREDECESSOR_RESOURCE_BUDGET_SHA256:
        raise RuntimeError("predecessor shared resource budget identity drifted")
    matrix_blob = _git_blob_sha1(
        "src/plural_cognition/collective/repository_surgery_calibration_matrix.py"
    )
    if matrix_blob != CALIBRATION_MATRIX_SOURCE_GIT_BLOB_SHA1:
        raise RuntimeError(f"calibration matrix source blob drifted: {matrix_blob}")

    _verify_load_observer_repair(load_repair_root)
    _verify_runtime_archives(runtime_root)
    cli = runtime_root / "bin" / "llama-cli.exe"
    runtime_observation = _runtime_observation(cli)
    sources = _candidate_sources()
    _verify_model_files(model_root, sources)
    blueprints = _selected_blueprints()

    artifact_root.mkdir(parents=True, exist_ok=True)
    protocol_bytes = _canonical_json_bytes(candidate_pool_v2_calibration_protocol_payload())
    plan_path = artifact_root / "calibration-protocol.json"
    if plan_path.is_file():
        if plan_path.read_bytes().rstrip(b"\r\n") != protocol_bytes:
            raise RuntimeError("existing v2 calibration protocol artifact drifted")
    else:
        _write_json_atomic(plan_path, candidate_pool_v2_calibration_protocol_payload())
    _write_json_atomic(artifact_root / "runtime-observation.json", asdict(runtime_observation))

    completed_before, _ = _preflight_pair_states(
        artifact_root, software_revision=software_revision
    )
    print(f"existing_completed_calibration_pairs={completed_before}/36", flush=True)
    print(f"expected_new_calibration_attempts={36-completed_before}", flush=True)

    store = FileContentStore(artifact_root / "store")
    staging_root = artifact_root / "staging"
    configuration = probe_qualified_docker_configuration(
        software_revision=software_revision,
        docker_executable=docker_executable,
    )

    results: list[dict[str, Any]] = []
    new_attempts = 0
    with tempfile.TemporaryDirectory(prefix="v2-calibration-material-", dir=artifact_root) as temp:
        build_root = Path(temp)
        materials = {
            blueprint.task_id: build_matrix_material(
                blueprint=blueprint,
                store=store,
                work_root=build_root / blueprint.task_id,
                software_revision=software_revision,
            )
            for blueprint in blueprints
        }
        for candidate_id in CANDIDATE_IDS_V2:
            source = sources[candidate_id]
            for blueprint in blueprints:
                report, attempted = _run_pair_once(
                    candidate_id=candidate_id,
                    source=source,
                    blueprint=blueprint,
                    material=materials[blueprint.task_id],
                    cli=cli,
                    model_root=model_root,
                    artifact_root=artifact_root,
                    store=store,
                    configuration=configuration,
                    staging_root=staging_root,
                    software_revision=software_revision,
                    timeout_seconds=timeout_seconds,
                    docker_executable=docker_executable,
                )
                results.append(report)
                new_attempts += int(attempted)
                print(
                    f"candidate={candidate_id} task={blueprint.task_id} "
                    f"parse_valid={report['parse_valid']} solved={report['solved']} "
                    f"new_inference_attempt={attempted} report_sha256={report['report_sha256']}",
                    flush=True,
                )

    if len(results) != 36:
        raise AssertionError(f"v2 calibration result count drifted: {len(results)}")
    if staging_root.exists() and any(staging_root.iterdir()):
        raise RuntimeError("v2 calibration left qualified-Docker staging residue")

    summaries: list[dict[str, Any]] = []
    eligible: list[str] = []
    for candidate_id in CANDIDATE_IDS_V2:
        own = [item for item in results if item["candidate_id"] == candidate_id]
        if len(own) != 6:
            raise AssertionError(f"candidate calibration task count drifted: {candidate_id}")
        parse_valid_count = sum(bool(item["parse_valid"]) for item in own)
        solved_count = sum(bool(item["solved"]) for item in own)
        passed = _candidate_passed(parse_valid_count, solved_count)
        if passed:
            eligible.append(candidate_id)
        peak_gpu = max(int(item["attempt_observation"]["peak_gpu_used_mib"]) for item in own)
        summaries.append(
            {
                "candidate_id": candidate_id,
                "task_count": 6,
                "parse_valid_count": parse_valid_count,
                "solved_count": solved_count,
                "passed_calibration_gate": passed,
                "peak_gpu_used_mib": peak_gpu,
            }
        )
        print(
            f"candidate={candidate_id} calibration_summary=parse:{parse_valid_count}/6 "
            f"solved:{solved_count}/6 passed_gate={passed}",
            flush=True,
        )

    suite = {
        "schema": CALIBRATION_SUITE_SCHEMA_V2,
        "scientific_status": "candidate-development-v2-calibration-only-not-selection-evidence",
        "status": "CANDIDATE_POOL_V2_CALIBRATION_COMPLETE",
        "software_revision": software_revision,
        "protocol_sha256": FINAL_CALIBRATION_PROTOCOL_SHA256_V2,
        "load_repair_suite_file_sha256": LOAD_OBSERVER_REPAIR_SUITE_FILE_SHA256_V2,
        "source_freeze_sha256": SOURCE_FREEZE_SHA256_V2,
        "candidate_ids": list(CANDIDATE_IDS_V2),
        "task_ids": list(CALIBRATION_TASK_IDS_V2),
        "pair_count": len(results),
        "new_inference_attempt_count_this_invocation": new_attempts,
        "gate": {
            "required_parse_valid_count": REQUIRED_PARSE_VALID_COUNT_V2,
            "minimum_solved_count": MINIMUM_SOLVED_COUNT_V2,
        },
        "summaries": summaries,
        "eligible_candidate_ids": eligible,
        "eligible_candidate_count": len(eligible),
        "results": [
            {
                "candidate_id": item["candidate_id"],
                "task_id": item["task_id"],
                "report_sha256": item["report_sha256"],
                "parse_valid": item["parse_valid"],
                "solved": item["solved"],
            }
            for item in results
        ],
        "selection_evidence": False,
    }
    suite_sha = hashlib.sha256(_canonical_json_bytes(suite)).hexdigest()
    suite["report_sha256"] = suite_sha
    _write_json_atomic(artifact_root / "candidate-pool-v2-calibration-suite.json", suite)
    return suite


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run or safely resume the fixed six-by-six candidate-pool v2 calibration gate."
    )
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--load-repair-root", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS_V2)
    parser.add_argument("--docker-executable", default="docker")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        suite = run_calibration(
            runtime_root=args.runtime_root,
            model_root=args.model_root,
            load_repair_root=args.load_repair_root,
            artifact_root=args.artifact_root,
            software_revision=args.software_revision,
            timeout_seconds=args.timeout_seconds,
            docker_executable=args.docker_executable,
        )
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"status=CANDIDATE_POOL_V2_CALIBRATION_ABORT\nerror={exc}")
        return 2

    print("status=CANDIDATE_POOL_V2_CALIBRATION_COMPLETE")
    print(f"report_sha256={suite['report_sha256']}")
    print(f"protocol_sha256={suite['protocol_sha256']}")
    print(f"pair_count={suite['pair_count']}")
    print(f"eligible_candidate_count={suite['eligible_candidate_count']}/6")
    print(
        "eligible_candidate_ids=" + ",".join(suite["eligible_candidate_ids"])
    )
    print(
        "new_inference_attempt_count_this_invocation=" +
        str(suite["new_inference_attempt_count_this_invocation"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
