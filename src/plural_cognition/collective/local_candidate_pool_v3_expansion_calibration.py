"""Restart-safe sequential calibration for the frozen candidate-pool v3 expansion scouts.

This runner reuses the already-qualified v3 development task material, representation,
transport, runtime/resource envelope, and Docker grading path. It changes only the
candidate source bindings, evidence identities, and the predeclared sequential stopping
rule: evaluate scouts in frozen order and stop permanently after the first gate pass.

Calibration is development-only evidence and never selection evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from .artifacts import CollectiveStage, ResourceUsage, StageArtifact
from .candidate_pool_v3_expansion_load_outcome_freeze import (
    EXPECTED_EXPANSION_LOAD_OUTCOME_FREEZE_SHA256_V3,
    EXPANSION_LOAD_SUITE_FILE_SHA256_V3,
    EXPANSION_LOAD_SUITE_REPORT_SHA256_V3,
    candidate_pool_v3_expansion_load_outcome_freeze_payload,
    validate_candidate_pool_v3_expansion_load_outcome_freeze,
)
from .candidate_pool_v3_expansion_protocol import (
    EXPECTED_CANDIDATE_POOL_V3_EXPANSION_PROTOCOL_SHA256,
    EXPANSION_MAX_CALIBRATION_CANDIDATES_V3,
    EXPANSION_MAX_CANDIDATE_TASK_CALLS_V3,
)
from .candidate_pool_v3_expansion_source_freeze import (
    EXPANSION_SCOUT_IDS_V3,
    candidate_pool_v3_expansion_source_freeze_payload,
)
from .candidate_pool_v3_full_file import (
    extract_full_file_patch_v3,
    solver_prompt_transport_v3,
)
from .candidate_pool_v3_representation_protocol import (
    EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256,
    V3_MINIMUM_SOLVED_COUNT,
    V3_REQUIRED_PARSE_VALID_COUNT,
    candidate_pool_v3_representation_protocol_payload,
    validate_v3_representation_protocol,
)
from .content_store import FileContentStore
from .local_candidate_pool_v2_load_observer_repair import _run_raw_attempt
from .local_candidate_pool_v3_calibration import (
    _load_command as _base_load_command,
    _selected_blueprints,
    _token_counts,
    _validate_material_bindings,
    _verify_qualification_root,
)
from .local_model_load_preflight import (
    OFFLOAD_PATTERN,
    _git_revision,
    _runtime_observation,
    _sha256_file,
    _verify_runtime_archives,
)
from .local_raw_calibration import validate_patch_against_blueprint
from .local_raw_calibration_v6 import extract_assistant_content_v6
from .qualified_docker import probe_qualified_docker_configuration
from .repository_surgery import PatchFormat, RepositorySurgerySubmission
from .repository_surgery_calibration_matrix import (
    _evaluate_patch,
    _metric,
    build_matrix_material,
)
from .repository_surgery_calibration_pack_v3 import CALIBRATION_TASK_IDS_V3
from .repository_surgery_calibration_qualification_freeze_v3 import (
    EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3,
    REPAIRED_CALIBRATION_PACK_CANONICAL_SHA256_V3,
    validate_calibration_qualification_freeze_v3,
)

EXPANSION_CALIBRATION_RUNNER_PROTOCOL_SCHEMA_V3 = (
    "plural-cognition-candidate-pool-v3-expansion-calibration-runner-protocol-v1"
)
EXPANSION_CALIBRATION_PAIR_SCHEMA_V3 = (
    "plural-cognition-candidate-pool-v3-expansion-calibration-pair-v1"
)
EXPANSION_CALIBRATION_ATTEMPT_SCHEMA_V3 = (
    "plural-cognition-candidate-pool-v3-expansion-calibration-attempt-v1"
)
EXPANSION_CALIBRATION_SUITE_SCHEMA_V3 = (
    "plural-cognition-candidate-pool-v3-expansion-calibration-suite-v1"
)
EXPANSION_LOAD_OUTCOME_FREEZE_REVISION_V3 = (
    "30ff8664ff2244baa75d540a7dd37d24ed257733"
)
BASE_V3_CALIBRATION_ENGINE_GIT_BLOB_SHA1 = (
    "e4e03da726ecf0ce2694c49b69a3c32896dfbaa3"
)
EXPECTED_EXPANSION_CALIBRATION_RUNNER_PROTOCOL_SHA256_V3 = (
    "2135fa7de82f14a024927792ea91f4e0d01b78115e6fd549b1f06e716a22e17f"
)
EXPANSION_CALIBRATION_ARTIFACT_ROOT_V3 = "artifacts/capable-collective/e3c"
EXPANSION_LOAD_ARTIFACT_ROOT_V3 = "artifacts/capable-collective/e3l"
DEFAULT_EXPANSION_CALIBRATION_TIMEOUT_SECONDS_V3 = 900
EXPANSION_CALIBRATION_MAX_PAIR_COUNT_V3 = 18


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


def _load_json_ascii(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="ascii"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"could not read immutable JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"immutable JSON is not an object: {path}")
    return payload


def expansion_candidate_sources_v3() -> dict[str, dict[str, Any]]:
    payload = candidate_pool_v3_expansion_source_freeze_payload()
    scouts = payload.get("scouts")
    if not isinstance(scouts, list):
        raise RuntimeError("expansion source-freeze scout collection drifted")
    indexed = {item["candidate_id"]: item for item in scouts}
    if tuple(indexed) != EXPANSION_SCOUT_IDS_V3:
        raise RuntimeError("expansion scout source ordering drifted")

    result: dict[str, dict[str, Any]] = {}
    for candidate_id in EXPANSION_SCOUT_IDS_V3:
        source = indexed[candidate_id]
        result[candidate_id] = {
            "candidate_id": candidate_id,
            "source_class": "candidate-pool-v3-expansion-source-freeze",
            "filename": source["artifact_filename"],
            "artifact_size_bytes": source["artifact_size_bytes"],
            "artifact_sha256": source["artifact_sha256"],
            "source_identity_sha256": _canonical_sha256(source),
        }
    return result


def expansion_calibration_runner_protocol_payload_v3() -> dict[str, Any]:
    representation = candidate_pool_v3_representation_protocol_payload()
    sources = expansion_candidate_sources_v3()
    return {
        "schema": EXPANSION_CALIBRATION_RUNNER_PROTOCOL_SCHEMA_V3,
        "scientific_status": (
            "candidate-development-v3-expansion-calibration-only-not-selection-evidence"
        ),
        "predecessor_load_outcome_freeze_revision": (
            EXPANSION_LOAD_OUTCOME_FREEZE_REVISION_V3
        ),
        "predecessor_load_outcome_freeze_sha256": (
            EXPECTED_EXPANSION_LOAD_OUTCOME_FREEZE_SHA256_V3
        ),
        "expansion_protocol_sha256": (
            EXPECTED_CANDIDATE_POOL_V3_EXPANSION_PROTOCOL_SHA256
        ),
        "representation_protocol_sha256": (
            EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256
        ),
        "qualification_freeze_sha256": (
            EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3
        ),
        "repaired_calibration_pack_sha256": (
            REPAIRED_CALIBRATION_PACK_CANONICAL_SHA256_V3
        ),
        "base_v3_calibration_engine_git_blob_sha1": (
            BASE_V3_CALIBRATION_ENGINE_GIT_BLOB_SHA1
        ),
        "scout_ids": list(EXPANSION_SCOUT_IDS_V3),
        "task_ids": list(CALIBRATION_TASK_IDS_V3),
        "max_pair_count": EXPANSION_CALIBRATION_MAX_PAIR_COUNT_V3,
        "candidate_sources": [
            sources[candidate_id] for candidate_id in EXPANSION_SCOUT_IDS_V3
        ],
        "resource_budget": representation["resource_budget"],
        "transport": representation["transport"],
        "representation": representation["representation"],
        "gate": {
            "required_parse_valid_count": V3_REQUIRED_PARSE_VALID_COUNT,
            "minimum_solved_count": V3_MINIMUM_SOLVED_COUNT,
        },
        "sequential_policy": {
            "ordered_scout_ids": list(EXPANSION_SCOUT_IDS_V3),
            "stop_after_first_gate_pass": True,
            "max_candidates_calibrated": EXPANSION_MAX_CALIBRATION_CANDIDATES_V3,
            "max_candidate_task_calls": EXPANSION_MAX_CANDIDATE_TASK_CALLS_V3,
            "one_call_per_pair": True,
            "max_attempts_per_pair": 1,
            "attempt_marker_before_inference": True,
            "partial_pair_blocks_all_new_inference": True,
            "completed_result_reused_verbatim": True,
            "failed_candidate_rerun_authorized": False,
            "candidate_specific_prompt_tuning": False,
            "automatic_reruns": False,
        },
        "artifact_root": EXPANSION_CALIBRATION_ARTIFACT_ROOT_V3,
        "load_artifact_root": EXPANSION_LOAD_ARTIFACT_ROOT_V3,
        "selection_evidence": False,
    }


def expansion_calibration_runner_protocol_sha256_v3() -> str:
    return _canonical_sha256(expansion_calibration_runner_protocol_payload_v3())


def validate_expansion_calibration_runner_protocol_v3() -> None:
    validate_candidate_pool_v3_expansion_load_outcome_freeze()
    validate_v3_representation_protocol()
    validate_calibration_qualification_freeze_v3()
    payload = expansion_calibration_runner_protocol_payload_v3()

    if tuple(payload["scout_ids"]) != EXPANSION_SCOUT_IDS_V3:
        raise RuntimeError("expansion calibration scout order drifted")
    if tuple(payload["task_ids"]) != CALIBRATION_TASK_IDS_V3:
        raise RuntimeError("expansion calibration task order drifted")
    if payload["max_pair_count"] != 18:
        raise RuntimeError("expansion calibration inference cap drifted")
    if payload["gate"] != {
        "required_parse_valid_count": 6,
        "minimum_solved_count": 4,
    }:
        raise RuntimeError("expansion calibration gate drifted")
    sequential = payload["sequential_policy"]
    if tuple(sequential["ordered_scout_ids"]) != EXPANSION_SCOUT_IDS_V3:
        raise RuntimeError("expansion sequential scout order drifted")
    if not sequential["stop_after_first_gate_pass"]:
        raise RuntimeError("expansion calibration must stop after first pass")
    if sequential["max_candidates_calibrated"] != 3:
        raise RuntimeError("expansion calibration candidate cap drifted")
    if sequential["max_candidate_task_calls"] != 18:
        raise RuntimeError("expansion calibration call cap drifted")
    if sequential["max_attempts_per_pair"] != 1:
        raise RuntimeError("expansion calibration attempts-per-pair drifted")
    if sequential["failed_candidate_rerun_authorized"]:
        raise RuntimeError("failed expansion calibration candidates cannot rerun")
    if sequential["candidate_specific_prompt_tuning"]:
        raise RuntimeError("candidate-specific expansion calibration tuning forbidden")
    if sequential["automatic_reruns"]:
        raise RuntimeError("automatic expansion calibration reruns forbidden")
    if payload["selection_evidence"]:
        raise RuntimeError("expansion calibration cannot be selection evidence")

    digest = expansion_calibration_runner_protocol_sha256_v3()
    if digest != EXPECTED_EXPANSION_CALIBRATION_RUNNER_PROTOCOL_SHA256_V3:
        raise RuntimeError(
            f"expansion calibration runner protocol identity drifted: {digest}"
        )


def _pair_id(candidate_id: str, task_id: str) -> str:
    return _canonical_sha256(
        {
            "schema": "plural-cognition-candidate-pool-v3-expansion-calibration-pair-id-v1",
            "candidate_id": candidate_id,
            "task_id": task_id,
            "runner_protocol_sha256": (
                expansion_calibration_runner_protocol_sha256_v3()
            ),
        }
    )


def _pair_root(artifact_root: Path, candidate_id: str, task_id: str) -> Path:
    return artifact_root / "pairs" / candidate_id / task_id


def _pair_state(path: Path) -> str:
    if (path / "result.json").is_file():
        return "complete"
    if path.exists():
        return "partial"
    return "missing"


def _candidate_passed(parse_valid_count: int, solved_count: int) -> bool:
    return (
        parse_valid_count == V3_REQUIRED_PARSE_VALID_COUNT
        and solved_count >= V3_MINIMUM_SOLVED_COUNT
    )


def _candidate_summary(
    candidate_id: str, reports: list[dict[str, Any]]
) -> dict[str, Any]:
    if len(reports) != len(CALIBRATION_TASK_IDS_V3):
        raise RuntimeError(
            f"cannot summarize incomplete expansion calibration candidate: {candidate_id}"
        )
    parse_valid_count = sum(bool(item["parse_valid"]) for item in reports)
    solved_count = sum(bool(item["solved"]) for item in reports)
    peak_gpu = max(
        int(item["attempt_observation"]["peak_gpu_used_mib"]) for item in reports
    )
    return {
        "candidate_id": candidate_id,
        "task_count": len(CALIBRATION_TASK_IDS_V3),
        "parse_valid_count": parse_valid_count,
        "solved_count": solved_count,
        "passed_calibration_gate": _candidate_passed(
            parse_valid_count, solved_count
        ),
        "peak_gpu_used_mib": peak_gpu,
    }


def _verify_model_files(
    model_root: Path, sources: dict[str, dict[str, Any]]
) -> None:
    for candidate_id in EXPANSION_SCOUT_IDS_V3:
        source = sources[candidate_id]
        path = model_root / candidate_id / source["filename"]
        if not path.is_file():
            raise RuntimeError(
                f"required expansion calibration model is missing: {path}"
            )
        observed_size = path.stat().st_size
        if observed_size != int(source["artifact_size_bytes"]):
            raise RuntimeError(
                f"model size mismatch for {candidate_id}: "
                f"{observed_size} != {source['artifact_size_bytes']}"
            )
        observed_sha = _sha256_file(path)
        if observed_sha != source["artifact_sha256"]:
            raise RuntimeError(
                f"model SHA-256 mismatch for {candidate_id}: {observed_sha}"
            )


def _verify_load_root(load_root: Path) -> None:
    outcome = candidate_pool_v3_expansion_load_outcome_freeze_payload()
    suite_path = load_root / "expansion-load-qualification-suite.json"
    if not suite_path.is_file():
        raise RuntimeError(f"frozen expansion load suite is missing: {suite_path}")
    if _sha256_file(suite_path) != EXPANSION_LOAD_SUITE_FILE_SHA256_V3:
        raise RuntimeError("frozen expansion load suite file SHA-256 drifted")
    suite = _load_json_ascii(suite_path)
    unsigned_suite = dict(suite)
    observed_report_sha = unsigned_suite.pop("report_sha256", None)
    if observed_report_sha != EXPANSION_LOAD_SUITE_REPORT_SHA256_V3:
        raise RuntimeError("frozen expansion load suite report identity drifted")
    if _canonical_sha256(unsigned_suite) != EXPANSION_LOAD_SUITE_REPORT_SHA256_V3:
        raise RuntimeError("frozen expansion load suite canonical content drifted")
    if tuple(suite.get("scout_ids", ())) != EXPANSION_SCOUT_IDS_V3:
        raise RuntimeError("frozen expansion load suite scout order drifted")
    if suite.get("qualified_count") != 3 or suite.get("failed_count") != 0:
        raise RuntimeError("frozen expansion load qualification result drifted")

    expected_results = {
        item["candidate_id"]: item for item in outcome["results"]
    }
    for candidate_id in EXPANSION_SCOUT_IDS_V3:
        root = load_root / candidate_id
        attempt_path = root / "attempt.json"
        result_path = root / "result.json"
        if not attempt_path.is_file() or not result_path.is_file():
            raise RuntimeError(
                f"frozen expansion load pair evidence is incomplete: {candidate_id}"
            )
        report = _load_json_ascii(result_path)
        expected = expected_results[candidate_id]
        if report.get("candidate_id") != candidate_id:
            raise RuntimeError(f"expansion load result candidate drifted: {candidate_id}")
        for key in (
            "status",
            "model_file_sha256",
            "model_file_size_bytes",
            "offloaded_layers",
            "total_layers",
        ):
            if report.get(key) != expected[key]:
                raise RuntimeError(
                    f"expansion load result field drifted: {candidate_id}:{key}"
                )
        unsigned = dict(report)
        observed = unsigned.pop("report_sha256", None)
        if observed != expected["report_sha256"]:
            raise RuntimeError(
                f"expansion load result report identity drifted: {candidate_id}"
            )
        if _canonical_sha256(unsigned) != expected["report_sha256"]:
            raise RuntimeError(
                f"expansion load result canonical content drifted: {candidate_id}"
            )
        if report.get("status") != "LOCAL_MODEL_LOAD_PASS":
            raise RuntimeError(
                f"expansion scout no longer load-qualified: {candidate_id}"
            )
        if report.get("offloaded_layers") != report.get("total_layers"):
            raise RuntimeError(
                f"expansion scout no longer proves full offload: {candidate_id}"
            )


def _producer_configuration_sha256(source_identity_sha256: str) -> str:
    return _canonical_sha256(
        {
            "schema": (
                "plural-cognition-candidate-pool-v3-expansion-calibration-producer-config-v1"
            ),
            "source_identity_sha256": source_identity_sha256,
            "runner_protocol_sha256": (
                expansion_calibration_runner_protocol_sha256_v3()
            ),
        }
    )


def _finalize_pair(
    pair_root: Path, payload: dict[str, Any]
) -> dict[str, Any]:
    unsigned = dict(payload)
    unsigned.pop("report_sha256", None)
    result = dict(unsigned)
    result["report_sha256"] = _canonical_sha256(unsigned)
    _write_json_atomic(pair_root / "result.json", result)
    return result


def _validate_completed_pair(
    report: dict[str, Any],
    *,
    candidate_id: str,
    task_id: str,
    software_revision: str,
) -> None:
    required = {
        "schema": EXPANSION_CALIBRATION_PAIR_SCHEMA_V3,
        "candidate_id": candidate_id,
        "task_id": task_id,
        "pair_id": _pair_id(candidate_id, task_id),
        "software_revision": software_revision,
        "runner_protocol_sha256": (
            expansion_calibration_runner_protocol_sha256_v3()
        ),
        "representation_protocol_sha256": (
            EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256
        ),
        "qualification_freeze_sha256": (
            EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3
        ),
        "load_outcome_freeze_sha256": (
            EXPECTED_EXPANSION_LOAD_OUTCOME_FREEZE_SHA256_V3
        ),
        "selection_evidence": False,
    }
    for key, expected in required.items():
        if report.get(key) != expected:
            raise RuntimeError(
                "completed expansion calibration pair field drifted: "
                f"{candidate_id}/{task_id}:{key}"
            )
    unsigned = dict(report)
    observed = unsigned.pop("report_sha256", None)
    if observed != _canonical_sha256(unsigned):
        raise RuntimeError(
            f"completed expansion calibration pair content drifted: "
            f"{candidate_id}/{task_id}"
        )


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
        "schema": EXPANSION_CALIBRATION_PAIR_SCHEMA_V3,
        "scientific_status": (
            "candidate-development-v3-expansion-calibration-only-not-selection-evidence"
        ),
        "status": "CANDIDATE_POOL_V3_EXPANSION_CALIBRATION_PAIR_COMPLETE",
        "candidate_id": candidate_id,
        "task_id": task_id,
        "pair_id": _pair_id(candidate_id, task_id),
        "software_revision": software_revision,
        "runner_protocol_sha256": (
            expansion_calibration_runner_protocol_sha256_v3()
        ),
        "representation_protocol_sha256": (
            EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256
        ),
        "qualification_freeze_sha256": (
            EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3
        ),
        "load_outcome_freeze_sha256": (
            EXPECTED_EXPANSION_LOAD_OUTCOME_FREEZE_SHA256_V3
        ),
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
        report = _load_json_ascii(pair_root / "result.json")
        _validate_completed_pair(
            report,
            candidate_id=candidate_id,
            task_id=task_id,
            software_revision=software_revision,
        )
        return report, False
    if state == "partial":
        raise RuntimeError(
            "partial expansion calibration pair blocks automatic rerun: "
            f"{candidate_id}/{task_id}"
        )

    prompt = solver_prompt_transport_v3(blueprint)
    prompt_sha256 = store.put_bytes(prompt)
    pair_root.mkdir(parents=True)
    capture = pair_root / "transcript.txt"
    model_path = model_root / candidate_id / source["filename"]
    command = _base_load_command(
        cli=cli,
        model_path=model_path,
        prompt=prompt,
        capture=capture,
    )
    command_sha256 = _canonical_sha256(list(command))
    attempt = {
        "schema": EXPANSION_CALIBRATION_ATTEMPT_SCHEMA_V3,
        "candidate_id": candidate_id,
        "task_id": task_id,
        "pair_id": _pair_id(candidate_id, task_id),
        "software_revision": software_revision,
        "runner_protocol_sha256": (
            expansion_calibration_runner_protocol_sha256_v3()
        ),
        "representation_protocol_sha256": (
            EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256
        ),
        "qualification_freeze_sha256": (
            EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3
        ),
        "load_outcome_freeze_sha256": (
            EXPECTED_EXPANSION_LOAD_OUTCOME_FREEZE_SHA256_V3
        ),
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
        command,
        timeout_seconds=timeout_seconds,
    )
    (pair_root / "process-stdout.bin").write_bytes(process_stdout)
    (pair_root / "stderr.bin").write_bytes(stderr)
    _write_json_atomic(pair_root / "attempt-observation.json", asdict(observation))
    if observation.monitor_error is not None:
        raise RuntimeError(
            "expansion calibration resource monitor failed for "
            f"{candidate_id}/{task_id}: {observation.monitor_error}"
        )

    base_payload = _base_pair_payload(
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
        offloaded_layers, total_layers = (
            int(value) for value in offload_matches[-1]
        )

    if observation.timed_out or observation.exit_code != 0:
        failure = (
            f"llama-cli exceeded {timeout_seconds} seconds"
            if observation.timed_out
            else f"llama-cli exited {observation.exit_code}"
        )
        base_payload.update(
            {
                "inference_valid": False,
                "inference_failure": failure,
                "offloaded_layers": offloaded_layers,
                "total_layers": total_layers,
                "transcript_sha256": (
                    hashlib.sha256(capture.read_bytes()).hexdigest()
                    if capture.is_file()
                    else None
                ),
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
        return _finalize_pair(pair_root, base_payload), True

    if not offload_matches:
        raise RuntimeError(
            "successful expansion calibration call lacks trace offload evidence: "
            f"{candidate_id}/{task_id}"
        )
    if offloaded_layers != total_layers:
        failure = f"model was not fully offloaded: {offloaded_layers}/{total_layers}"
        base_payload.update(
            {
                "inference_valid": False,
                "inference_failure": failure,
                "offloaded_layers": offloaded_layers,
                "total_layers": total_layers,
                "transcript_sha256": (
                    hashlib.sha256(capture.read_bytes()).hexdigest()
                    if capture.is_file()
                    else None
                ),
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
        return _finalize_pair(pair_root, base_payload), True
    if not capture.is_file():
        raise RuntimeError(
            f"expansion calibration transcript is missing: {capture}"
        )

    transcript = capture.read_bytes()
    transcript_sha256 = hashlib.sha256(transcript).hexdigest()
    try:
        assistant, reasoning = extract_assistant_content_v6(
            transcript=transcript,
            prompt=prompt,
        )
    except ValueError as exc:
        failure = f"assistant transport invalid: {exc}"
        base_payload.update(
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
        return _finalize_pair(pair_root, base_payload), True

    (pair_root / "assistant.txt").write_bytes(assistant)
    reasoning_sha256: str | None = None
    if reasoning is not None:
        (pair_root / "reasoning.txt").write_bytes(reasoning)
        reasoning_sha256 = hashlib.sha256(reasoning).hexdigest()
    assistant_sha256 = store.put_bytes(assistant)
    resources = ResourceUsage(
        input_tokens=int(base_payload["input_tokens"]),
        output_tokens=int(base_payload["output_tokens"]),
        inference_calls=1,
        wall_time_ms=max(0, round(observation.elapsed_seconds * 1000)),
        accelerator_time_ms=max(0, round(observation.elapsed_seconds * 1000)),
        peak_accelerator_bytes=observation.peak_gpu_used_mib * 1024 * 1024,
        peak_ram_bytes=observation.peak_process_rss_bytes or 0,
    )
    raw_artifact = StageArtifact(
        stage=CollectiveStage.RAW_MIND_OUTPUT,
        task=material.visible_task.task,
        run_id=f"candidate-pool-v3-expansion-calibration:{candidate_id}:{task_id}",
        producer_id=candidate_id,
        producer_configuration_sha256=_producer_configuration_sha256(
            source["source_identity_sha256"]
        ),
        protocol_sha256=expansion_calibration_runner_protocol_sha256_v3(),
        software_revision=software_revision,
        content_sha256=assistant_sha256,
        resources=resources,
    )
    if store.put_bytes(raw_artifact.canonical_bytes()) != raw_artifact.sha256:
        raise AssertionError(
            "expansion calibration raw artifact storage identity mismatch"
        )

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
        patch, parse_mode = extract_full_file_patch_v3(assistant, blueprint)
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
            raise AssertionError(
                "expansion calibration submission storage identity mismatch"
            )
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
            raise AssertionError(
                "expansion calibration evaluation storage identity mismatch"
            )
        exact_accuracy = _metric(evaluation, "exact_accuracy")
        evaluator_valid_rate = _metric(evaluation, "valid_rate")
        solved = bool(evaluation.qualified)

    base_payload.update(
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
    return _finalize_pair(pair_root, base_payload), True


def _scan_existing_progress(
    artifact_root: Path, *, software_revision: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
    results: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    passing_candidate: str | None = None
    earlier_open = False

    for candidate_id in EXPANSION_SCOUT_IDS_V3:
        own: list[dict[str, Any]] = []
        missing_seen = False
        for task_id in CALIBRATION_TASK_IDS_V3:
            root = _pair_root(artifact_root, candidate_id, task_id)
            state = _pair_state(root)
            if state == "partial":
                raise RuntimeError(
                    "partial expansion calibration pair blocks all new inference: "
                    f"{candidate_id}/{task_id}"
                )
            if state == "missing":
                missing_seen = True
                continue
            if state == "complete":
                if missing_seen:
                    raise RuntimeError(
                        "non-prefix expansion calibration evidence within scout: "
                        f"{candidate_id}/{task_id}"
                    )
                if passing_candidate is not None:
                    raise RuntimeError(
                        "expansion calibration evidence exists after an earlier "
                        f"passing scout: {candidate_id}/{task_id}"
                    )
                if earlier_open:
                    raise RuntimeError(
                        "later expansion scout evidence exists before earlier scout "
                        f"completion: {candidate_id}/{task_id}"
                    )
                report = _load_json_ascii(root / "result.json")
                _validate_completed_pair(
                    report,
                    candidate_id=candidate_id,
                    task_id=task_id,
                    software_revision=software_revision,
                )
                own.append(report)
                results.append(report)

        if not own:
            if passing_candidate is None:
                earlier_open = True
            continue
        if len(own) < len(CALIBRATION_TASK_IDS_V3):
            earlier_open = True
            continue
        if earlier_open:
            raise RuntimeError(
                "completed later expansion scout appears after an earlier open scout"
            )
        summary = _candidate_summary(candidate_id, own)
        summaries.append(summary)
        if summary["passed_calibration_gate"]:
            passing_candidate = candidate_id

    return results, summaries, passing_candidate


def _finalize_suite(
    *,
    artifact_root: Path,
    software_revision: str,
    results: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    passing_candidate_id: str | None,
    new_attempts: int,
) -> dict[str, Any]:
    evaluated_ids = [item["candidate_id"] for item in summaries]
    expected_evaluated = list(EXPANSION_SCOUT_IDS_V3[: len(evaluated_ids)])
    if evaluated_ids != expected_evaluated:
        raise RuntimeError("expansion calibration evaluated scout prefix drifted")
    if len(results) != len(evaluated_ids) * len(CALIBRATION_TASK_IDS_V3):
        raise RuntimeError("expansion calibration result count is not a complete prefix")
    if len(results) > EXPANSION_CALIBRATION_MAX_PAIR_COUNT_V3:
        raise RuntimeError("expansion calibration exceeded pair budget")
    if passing_candidate_id is not None:
        if not summaries or summaries[-1]["candidate_id"] != passing_candidate_id:
            raise RuntimeError("passing expansion scout is not the final evaluated scout")
        if not summaries[-1]["passed_calibration_gate"]:
            raise RuntimeError("passing expansion scout summary does not pass gate")
    elif any(item["passed_calibration_gate"] for item in summaries):
        raise RuntimeError("expansion calibration pass exists without stop identity")

    suite = {
        "schema": EXPANSION_CALIBRATION_SUITE_SCHEMA_V3,
        "scientific_status": (
            "candidate-development-v3-expansion-calibration-only-not-selection-evidence"
        ),
        "status": "CANDIDATE_POOL_V3_EXPANSION_CALIBRATION_COMPLETE",
        "software_revision": software_revision,
        "runner_protocol_sha256": (
            expansion_calibration_runner_protocol_sha256_v3()
        ),
        "representation_protocol_sha256": (
            EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256
        ),
        "qualification_freeze_sha256": (
            EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3
        ),
        "load_outcome_freeze_sha256": (
            EXPECTED_EXPANSION_LOAD_OUTCOME_FREEZE_SHA256_V3
        ),
        "repaired_calibration_pack_sha256": (
            REPAIRED_CALIBRATION_PACK_CANONICAL_SHA256_V3
        ),
        "scout_ids": list(EXPANSION_SCOUT_IDS_V3),
        "task_ids": list(CALIBRATION_TASK_IDS_V3),
        "pair_count": len(results),
        "new_inference_attempt_count_this_invocation": new_attempts,
        "gate": {
            "required_parse_valid_count": V3_REQUIRED_PARSE_VALID_COUNT,
            "minimum_solved_count": V3_MINIMUM_SOLVED_COUNT,
        },
        "summaries": summaries,
        "evaluated_candidate_ids": evaluated_ids,
        "unevaluated_candidate_ids": list(
            EXPANSION_SCOUT_IDS_V3[len(evaluated_ids) :]
        ),
        "passing_candidate_id": passing_candidate_id,
        "new_eligible_candidate_count": int(passing_candidate_id is not None),
        "population_feasible": passing_candidate_id is not None,
        "stopped_after_first_gate_pass": passing_candidate_id is not None,
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
    suite["report_sha256"] = _canonical_sha256(suite)
    _write_json_atomic(
        artifact_root / "candidate-pool-v3-expansion-calibration-suite.json",
        suite,
    )
    return suite


def _validate_completed_suite(
    path: Path, *, software_revision: str
) -> dict[str, Any]:
    suite = _load_json_ascii(path)
    required = {
        "schema": EXPANSION_CALIBRATION_SUITE_SCHEMA_V3,
        "scientific_status": (
            "candidate-development-v3-expansion-calibration-only-not-selection-evidence"
        ),
        "status": "CANDIDATE_POOL_V3_EXPANSION_CALIBRATION_COMPLETE",
        "software_revision": software_revision,
        "runner_protocol_sha256": (
            expansion_calibration_runner_protocol_sha256_v3()
        ),
        "representation_protocol_sha256": (
            EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256
        ),
        "qualification_freeze_sha256": (
            EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3
        ),
        "load_outcome_freeze_sha256": (
            EXPECTED_EXPANSION_LOAD_OUTCOME_FREEZE_SHA256_V3
        ),
        "selection_evidence": False,
    }
    for key, expected in required.items():
        if suite.get(key) != expected:
            raise RuntimeError(
                f"completed expansion calibration suite field drifted: {key}"
            )
    unsigned = dict(suite)
    observed = unsigned.pop("report_sha256", None)
    if observed != _canonical_sha256(unsigned):
        raise RuntimeError("completed expansion calibration suite content drifted")
    summaries = suite.get("summaries")
    results = suite.get("results")
    if not isinstance(summaries, list) or not isinstance(results, list):
        raise RuntimeError("completed expansion calibration suite collections drifted")
    if not 1 <= len(summaries) <= 3:
        raise RuntimeError("completed expansion calibration summary count drifted")
    if len(results) != len(summaries) * len(CALIBRATION_TASK_IDS_V3):
        raise RuntimeError("completed expansion calibration result count drifted")
    if suite.get("pair_count") != len(results):
        raise RuntimeError("completed expansion calibration pair count drifted")
    passing = suite.get("passing_candidate_id")
    if passing is not None:
        if summaries[-1].get("candidate_id") != passing:
            raise RuntimeError("completed expansion calibration stop identity drifted")
        if not summaries[-1].get("passed_calibration_gate"):
            raise RuntimeError("completed expansion calibration stop gate drifted")
        if suite.get("unevaluated_candidate_ids") != list(
            EXPANSION_SCOUT_IDS_V3[len(summaries) :]
        ):
            raise RuntimeError("completed expansion calibration unevaluated set drifted")
    elif len(summaries) != len(EXPANSION_SCOUT_IDS_V3):
        raise RuntimeError(
            "completed negative expansion calibration must evaluate all scouts"
        )
    return suite


def run_expansion_calibration_v3(
    *,
    runtime_root: Path,
    model_root: Path,
    qualification_root: Path,
    load_root: Path,
    artifact_root: Path,
    software_revision: str,
    timeout_seconds: int = DEFAULT_EXPANSION_CALIBRATION_TIMEOUT_SECONDS_V3,
    docker_executable: str = "docker",
) -> dict[str, Any]:
    if type(timeout_seconds) is not int or timeout_seconds < 1:
        raise ValueError("timeout_seconds must be a positive integer")
    if _git_revision() != software_revision:
        raise RuntimeError(
            "software revision argument does not match current checkout"
        )

    validate_expansion_calibration_runner_protocol_v3()
    _verify_qualification_root(qualification_root)
    _verify_load_root(load_root)
    _verify_runtime_archives(runtime_root)
    cli = runtime_root / "bin" / "llama-cli.exe"
    runtime_observation = _runtime_observation(cli)
    sources = expansion_candidate_sources_v3()
    _verify_model_files(model_root, sources)
    blueprints = _selected_blueprints()

    suite_path = artifact_root / "candidate-pool-v3-expansion-calibration-suite.json"
    if suite_path.is_file():
        return _validate_completed_suite(
            suite_path, software_revision=software_revision
        )

    artifact_root.mkdir(parents=True, exist_ok=True)
    _write_json_once(
        artifact_root / "expansion-calibration-runner-protocol-v3.json",
        expansion_calibration_runner_protocol_payload_v3(),
    )
    _write_json_once(
        artifact_root / "runtime-observation.json",
        asdict(runtime_observation),
    )

    existing_results, existing_summaries, existing_pass = _scan_existing_progress(
        artifact_root, software_revision=software_revision
    )
    print(
        f"existing_completed_expansion_calibration_pairs={len(existing_results)}/18",
        flush=True,
    )

    if existing_pass is not None or len(existing_summaries) == len(EXPANSION_SCOUT_IDS_V3):
        return _finalize_suite(
            artifact_root=artifact_root,
            software_revision=software_revision,
            results=existing_results,
            summaries=existing_summaries,
            passing_candidate_id=existing_pass,
            new_attempts=0,
        )

    store = FileContentStore(artifact_root / "store")
    staging_root = artifact_root / "staging"
    configuration = probe_qualified_docker_configuration(
        software_revision=software_revision,
        docker_executable=docker_executable,
    )
    evidence = _verify_qualification_root(qualification_root)

    results = list(existing_results)
    summaries = list(existing_summaries)
    completed_candidate_ids = {
        item["candidate_id"] for item in existing_summaries
    }
    new_attempts = 0
    passing_candidate_id: str | None = None

    with tempfile.TemporaryDirectory(
        prefix="v3-expansion-calibration-material-",
        dir=artifact_root,
    ) as temp:
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
        _validate_material_bindings(materials, evidence["pack"])

        for candidate_id in EXPANSION_SCOUT_IDS_V3:
            if candidate_id in completed_candidate_ids:
                continue
            source = sources[candidate_id]
            own = [
                item for item in results if item["candidate_id"] == candidate_id
            ]
            for blueprint in blueprints:
                if any(item["task_id"] == blueprint.task_id for item in own):
                    continue
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
                own.append(report)
                results.append(report)
                new_attempts += int(attempted)
                print(
                    f"candidate={candidate_id} task={blueprint.task_id} "
                    f"parse_valid={report['parse_valid']} "
                    f"solved={report['solved']} "
                    f"new_inference_attempt={attempted} "
                    f"report_sha256={report['report_sha256']}",
                    flush=True,
                )

            summary = _candidate_summary(candidate_id, own)
            summaries.append(summary)
            print(
                f"candidate={candidate_id} "
                f"calibration_summary=parse:{summary['parse_valid_count']}/6 "
                f"solved:{summary['solved_count']}/6 "
                f"passed_gate={summary['passed_calibration_gate']}",
                flush=True,
            )
            if summary["passed_calibration_gate"]:
                passing_candidate_id = candidate_id
                print(
                    f"stop_after_first_gate_pass={candidate_id}",
                    flush=True,
                )
                break

    if staging_root.exists() and any(staging_root.iterdir()):
        raise RuntimeError(
            "expansion calibration left qualified-Docker staging residue"
        )

    if passing_candidate_id is None and len(summaries) != 3:
        raise RuntimeError(
            "expansion calibration stopped without a pass before exhausting scouts"
        )

    return _finalize_suite(
        artifact_root=artifact_root,
        software_revision=software_revision,
        results=results,
        summaries=summaries,
        passing_candidate_id=passing_candidate_id,
        new_attempts=new_attempts,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run or safely resume the ordered candidate-pool v3 expansion "
            "calibration until the first gate pass."
        )
    )
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--qualification-root", required=True, type=Path)
    parser.add_argument("--load-root", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_EXPANSION_CALIBRATION_TIMEOUT_SECONDS_V3,
    )
    parser.add_argument("--docker-executable", default="docker")
    return parser


def _print_suite(suite: dict[str, Any], *, reused: bool) -> None:
    print("status=CANDIDATE_POOL_V3_EXPANSION_CALIBRATION_COMPLETE")
    print(f"completed_suite_reused={reused}")
    print(f"report_sha256={suite['report_sha256']}")
    print(f"runner_protocol_sha256={suite['runner_protocol_sha256']}")
    print(f"pair_count={suite['pair_count']}")
    print(
        "evaluated_candidate_ids="
        + ",".join(suite["evaluated_candidate_ids"])
    )
    print(
        "unevaluated_candidate_ids="
        + ",".join(suite["unevaluated_candidate_ids"])
    )
    print(
        "passing_candidate_id="
        + (suite["passing_candidate_id"] or "")
    )
    print(f"population_feasible={suite['population_feasible']}")
    print("selection_evidence=False")
    print(
        "new_inference_attempt_count_this_invocation="
        + (
            "0"
            if reused
            else str(suite["new_inference_attempt_count_this_invocation"])
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    suite_path = (
        args.artifact_root / "candidate-pool-v3-expansion-calibration-suite.json"
    )
    try:
        if suite_path.is_file():
            suite = _validate_completed_suite(
                suite_path, software_revision=args.software_revision
            )
            _print_suite(suite, reused=True)
            return 0
        suite = run_expansion_calibration_v3(
            runtime_root=args.runtime_root,
            model_root=args.model_root,
            qualification_root=args.qualification_root,
            load_root=args.load_root,
            artifact_root=args.artifact_root,
            software_revision=args.software_revision,
            timeout_seconds=args.timeout_seconds,
            docker_executable=args.docker_executable,
        )
    except (AssertionError, KeyError, OSError, RuntimeError, ValueError) as exc:
        print(
            "status=CANDIDATE_POOL_V3_EXPANSION_CALIBRATION_ABORT\n"
            f"error={exc}"
        )
        return 2
    _print_suite(suite, reused=False)
    return 0


validate_expansion_calibration_runner_protocol_v3()


if __name__ == "__main__":
    raise SystemExit(main())
