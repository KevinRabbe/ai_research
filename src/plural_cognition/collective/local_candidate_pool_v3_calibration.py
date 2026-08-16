"""Restart-safe four-by-six candidate-pool v3 development calibration gate.

The runner is deliberately conservative. It binds the frozen repaired v3
calibration qualification, verifies exact model/runtime identities before any new
inference, preflights all 24 pair roots globally, writes an immutable attempt
marker before each model call, and never automatically reruns a consumed pair.
Completed ``result.json`` evidence is validated and reused verbatim.

Calibration is development-only evidence and never selection evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from .artifacts import CollectiveStage, ResourceUsage, StageArtifact
from .candidate_pool_v2_source_freeze import (
    FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256,
    candidate_pool_v2_source_freeze_payload,
)
from .candidate_pool_v3_full_file import (
    extract_full_file_patch_v3,
    solver_prompt_transport_v3,
)
from .candidate_pool_v3_representation_protocol import (
    EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256,
    V3_DEVELOPMENT_CANDIDATE_IDS,
    V3_FRESH_CALIBRATION_TASK_COUNT,
    V3_MINIMUM_SOLVED_COUNT,
    V3_REQUIRED_PARSE_VALID_COUNT,
    candidate_pool_v3_representation_protocol_payload,
    validate_v3_representation_protocol,
)
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
from .repository_surgery_calibration_pack_v3_repair import (
    repaired_calibration_blueprints_v3,
)
from .repository_surgery_calibration_qualification_freeze_v3 import (
    CALIBRATION_QUALIFICATION_SOFTWARE_REVISION_V3,
    EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3,
    QUALIFIED_DOCKER_REPORT_SHA256_V3,
    REPAIRED_CALIBRATION_PACK_CANONICAL_SHA256_V3,
    REPAIRED_CALIBRATION_PACK_FILE_SHA256_V3,
    REPAIRED_CALIBRATION_QUALIFICATION_CANONICAL_SHA256_V3,
    REPAIRED_CALIBRATION_QUALIFICATION_FILE_SHA256_V3,
    REPAIR_RECORD_CANONICAL_SHA256_V3,
    REPAIR_RECORD_FILE_SHA256_V3,
    validate_calibration_qualification_freeze_v3,
)

CALIBRATION_PAIR_SCHEMA_V3 = "plural-cognition-candidate-pool-v3-calibration-pair-v1"
CALIBRATION_ATTEMPT_SCHEMA_V3 = "plural-cognition-candidate-pool-v3-calibration-attempt-v1"
CALIBRATION_SUITE_SCHEMA_V3 = "plural-cognition-candidate-pool-v3-calibration-suite-v1"
CALIBRATION_RUNNER_PROTOCOL_SCHEMA_V3 = (
    "plural-cognition-candidate-pool-v3-calibration-runner-protocol-v1"
)
DEFAULT_TIMEOUT_SECONDS_V3 = 900
PAIR_COUNT_V3 = len(V3_DEVELOPMENT_CANDIDATE_IDS) * V3_FRESH_CALIBRATION_TASK_COUNT

_PROMPT_TOKEN_RE = re.compile(r"prompt eval time\s*=.*?/\s*(\d+)\s+tokens", re.IGNORECASE)
_OUTPUT_TOKEN_RE = re.compile(r"eval time\s*=.*?/\s*(\d+)\s+runs", re.IGNORECASE)
_PROTOCOL_CACHE: dict[str, Any] | None = None


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


def _source_identity(payload: dict[str, Any]) -> str:
    return _canonical_sha256(payload)


def candidate_sources_v3() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for candidate_id in (
        "qwen3-8b-q8",
        "qwen2.5-coder-14b-q5km",
        "devstral-24b-q4km",
    ):
        source = LOCAL_MODEL_SOURCE_FREEZE_V2.candidate(candidate_id)
        result[candidate_id] = {
            "candidate_id": candidate_id,
            "source_class": "local-model-source-freeze-v2",
            "filename": source.filename,
            "artifact_size_bytes": source.size_bytes,
            "artifact_sha256": source.artifact_sha256,
            "source_identity_sha256": source.sha256,
        }

    challenger_payload = candidate_pool_v2_source_freeze_payload()
    challengers = {
        item["candidate_id"]: item for item in challenger_payload["challengers"]
    }
    source = challengers["gpt-oss-20b-mxfp4"]
    result["gpt-oss-20b-mxfp4"] = {
        "candidate_id": "gpt-oss-20b-mxfp4",
        "source_class": "candidate-pool-v2-source-freeze",
        "filename": source["filename"],
        "artifact_size_bytes": source["artifact_size_bytes"],
        "artifact_sha256": source["artifact_sha256"],
        "source_identity_sha256": _source_identity(source),
    }
    ordered = {
        candidate_id: result[candidate_id]
        for candidate_id in V3_DEVELOPMENT_CANDIDATE_IDS
    }
    if tuple(ordered) != V3_DEVELOPMENT_CANDIDATE_IDS:
        raise RuntimeError("v3 calibration source ordering drifted")
    return ordered


def calibration_runner_protocol_payload_v3() -> dict[str, Any]:
    representation = candidate_pool_v3_representation_protocol_payload()
    sources = candidate_sources_v3()
    return {
        "schema": CALIBRATION_RUNNER_PROTOCOL_SCHEMA_V3,
        "scientific_status": (
            "candidate-development-v3-calibration-only-not-selection-evidence"
        ),
        "predecessor_qualification_freeze_sha256": (
            EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3
        ),
        "qualification_software_revision": (
            CALIBRATION_QUALIFICATION_SOFTWARE_REVISION_V3
        ),
        "representation_protocol_sha256": (
            EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256
        ),
        "repaired_calibration_pack_canonical_sha256": (
            REPAIRED_CALIBRATION_PACK_CANONICAL_SHA256_V3
        ),
        "repaired_calibration_qualification_canonical_sha256": (
            REPAIRED_CALIBRATION_QUALIFICATION_CANONICAL_SHA256_V3
        ),
        "repair_record_canonical_sha256": REPAIR_RECORD_CANONICAL_SHA256_V3,
        "qualified_docker_report_sha256": QUALIFIED_DOCKER_REPORT_SHA256_V3,
        "local_model_source_freeze_sha256": LOCAL_MODEL_SOURCE_FREEZE_V2.sha256,
        "challenger_source_freeze_sha256": (
            FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256
        ),
        "candidate_ids": list(V3_DEVELOPMENT_CANDIDATE_IDS),
        "task_ids": list(CALIBRATION_TASK_IDS_V3),
        "pair_count": PAIR_COUNT_V3,
        "candidate_sources": [
            sources[candidate_id] for candidate_id in V3_DEVELOPMENT_CANDIDATE_IDS
        ],
        "resource_budget": representation["resource_budget"],
        "transport": representation["transport"],
        "representation": representation["representation"],
        "gate": {
            "required_parse_valid_count": V3_REQUIRED_PARSE_VALID_COUNT,
            "minimum_solved_count": V3_MINIMUM_SOLVED_COUNT,
        },
        "pair_policy": {
            "max_attempts": 1,
            "attempt_marker_before_inference": True,
            "partial_pair_blocks_all_new_inference": True,
            "completed_result_reused_verbatim": True,
            "candidate_specific_tuning": False,
            "automatic_reruns": False,
        },
        "selection_evidence": False,
    }


def calibration_runner_protocol_sha256_v3() -> str:
    return _canonical_sha256(calibration_runner_protocol_payload_v3())


def _pair_id(candidate_id: str, task_id: str) -> str:
    return _canonical_sha256(
        {
            "schema": "plural-cognition-candidate-pool-v3-calibration-pair-id-v1",
            "candidate_id": candidate_id,
            "task_id": task_id,
            "runner_protocol_sha256": calibration_runner_protocol_sha256_v3(),
        }
    )


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
        parse_valid_count == V3_REQUIRED_PARSE_VALID_COUNT
        and solved_count >= V3_MINIMUM_SOLVED_COUNT
    )


def _verify_model_files(
    model_root: Path, sources: dict[str, dict[str, Any]]
) -> None:
    for candidate_id in V3_DEVELOPMENT_CANDIDATE_IDS:
        source = sources[candidate_id]
        path = model_root / candidate_id / source["filename"]
        if not path.is_file():
            raise RuntimeError(f"required v3 calibration model is missing: {path}")
        size = path.stat().st_size
        if size != int(source["artifact_size_bytes"]):
            raise RuntimeError(
                f"model size mismatch for {candidate_id}: "
                f"{size} != {source['artifact_size_bytes']}"
            )
        digest = _sha256_file(path)
        if digest != source["artifact_sha256"]:
            raise RuntimeError(
                f"model SHA-256 mismatch for {candidate_id}: {digest}"
            )


def _load_json_ascii(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="ascii"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"could not read frozen qualification JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"qualification JSON is not an object: {path}")
    return payload


def _verify_file_and_canonical(
    path: Path, *, file_sha256: str, canonical_sha256: str
) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"frozen qualification artifact is missing: {path}")
    observed_file = _sha256_file(path)
    if observed_file != file_sha256:
        raise RuntimeError(f"frozen qualification file SHA-256 drifted: {path}")
    payload = _load_json_ascii(path)
    if _canonical_sha256(payload) != canonical_sha256:
        raise RuntimeError(
            f"frozen qualification canonical SHA-256 drifted: {path}"
        )
    return payload


def _verify_qualification_root(
    qualification_root: Path,
) -> dict[str, dict[str, Any]]:
    validate_calibration_qualification_freeze_v3()
    repair_record = _verify_file_and_canonical(
        qualification_root / "calibration-pack-v3-repair-record.json",
        file_sha256=REPAIR_RECORD_FILE_SHA256_V3,
        canonical_sha256=REPAIR_RECORD_CANONICAL_SHA256_V3,
    )
    pack = _verify_file_and_canonical(
        qualification_root / "calibration-pack-v3-repair.json",
        file_sha256=REPAIRED_CALIBRATION_PACK_FILE_SHA256_V3,
        canonical_sha256=REPAIRED_CALIBRATION_PACK_CANONICAL_SHA256_V3,
    )
    qualification = _verify_file_and_canonical(
        qualification_root / "calibration-qualification-v3-repair.json",
        file_sha256=REPAIRED_CALIBRATION_QUALIFICATION_FILE_SHA256_V3,
        canonical_sha256=REPAIRED_CALIBRATION_QUALIFICATION_CANONICAL_SHA256_V3,
    )
    if (
        qualification.get("software_revision")
        != CALIBRATION_QUALIFICATION_SOFTWARE_REVISION_V3
    ):
        raise RuntimeError("frozen v3 qualification software revision drifted")
    if (
        qualification.get("qualified_docker_report_sha256")
        != QUALIFIED_DOCKER_REPORT_SHA256_V3
    ):
        raise RuntimeError("frozen v3 qualification Docker identity drifted")
    if (
        qualification.get("calibration_pack_sha256")
        != REPAIRED_CALIBRATION_PACK_CANONICAL_SHA256_V3
    ):
        raise RuntimeError("frozen v3 qualification no longer binds repaired pack")
    if (
        qualification.get("repair_record_sha256")
        != REPAIR_RECORD_CANONICAL_SHA256_V3
    ):
        raise RuntimeError("frozen v3 qualification no longer binds repair record")
    for key in (
        "candidate_model_inference_performed",
        "calibration_candidate_outcomes_observed",
        "selection_outcomes_observed",
        "selection_evidence",
        "failed_artifact_root_reused",
    ):
        if qualification.get(key) is not False:
            raise RuntimeError(
                f"frozen v3 qualification safety field drifted: {key}"
            )
    if tuple(pack.get("candidate_ids", ())) != V3_DEVELOPMENT_CANDIDATE_IDS:
        raise RuntimeError("frozen v3 pack candidate identities drifted")
    task_entries = pack.get("tasks")
    if not isinstance(task_entries, list) or tuple(
        item.get("task_id")
        for item in task_entries
        if isinstance(item, dict)
    ) != CALIBRATION_TASK_IDS_V3:
        raise RuntimeError("frozen v3 pack task identities drifted")
    return {
        "repair_record": repair_record,
        "pack": pack,
        "qualification": qualification,
    }


def _selected_blueprints() -> tuple[Any, ...]:
    blueprints = repaired_calibration_blueprints_v3()
    if tuple(item.task_id for item in blueprints) != CALIBRATION_TASK_IDS_V3:
        raise RuntimeError("repaired v3 calibration task identities drifted")
    return blueprints


def _representation_protocol_cached() -> dict[str, Any]:
    global _PROTOCOL_CACHE
    if _PROTOCOL_CACHE is None:
        _PROTOCOL_CACHE = candidate_pool_v3_representation_protocol_payload()
    return _PROTOCOL_CACHE


def _load_command(
    *, cli: Path, model_path: Path, prompt: bytes, capture: Path
) -> tuple[str, ...]:
    protocol = _representation_protocol_cached()
    budget = protocol["resource_budget"]
    transport = protocol["transport"]
    return (
        str(cli),
        "-m",
        str(model_path),
        "-c",
        str(budget["context_tokens"]),
        "-n",
        str(budget["predict_tokens"]),
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
        "-cnv",
        "--simple-io",
        "--output-file",
        str(capture),
        "--no-escape",
        "--no-display-prompt",
        "--log-colors",
        "off",
        "--no-log-timestamps",
        "--log-verbosity",
        str(transport["log_verbosity"]),
        "--perf",
        "-st",
        "-p",
        prompt.decode("utf-8"),
    )


def _token_counts(stderr: bytes) -> tuple[int, int, bool]:
    text = stderr.decode("utf-8", errors="replace")
    prompt = _PROMPT_TOKEN_RE.findall(text)
    output = _OUTPUT_TOKEN_RE.findall(text)
    if not prompt or not output:
        return 0, 0, False
    return int(prompt[-1]), int(output[-1]), True


def _producer_configuration_sha256(source_identity_sha256: str) -> str:
    return _canonical_sha256(
        {
            "schema": (
                "plural-cognition-candidate-pool-v3-calibration-producer-config-v1"
            ),
            "source_identity_sha256": source_identity_sha256,
            "runner_protocol_sha256": calibration_runner_protocol_sha256_v3(),
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
        "schema": CALIBRATION_PAIR_SCHEMA_V3,
        "candidate_id": candidate_id,
        "task_id": task_id,
        "pair_id": _pair_id(candidate_id, task_id),
        "software_revision": software_revision,
        "runner_protocol_sha256": calibration_runner_protocol_sha256_v3(),
        "representation_protocol_sha256": (
            EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256
        ),
        "selection_evidence": False,
    }
    for key, expected in required.items():
        if report.get(key) != expected:
            raise RuntimeError(
                "completed v3 calibration pair field drifted: "
                f"{candidate_id}/{task_id}:{key}"
            )
    unsigned = dict(report)
    observed = unsigned.pop("report_sha256", None)
    if observed != _canonical_sha256(unsigned):
        raise RuntimeError(
            f"completed v3 calibration pair content drifted: {candidate_id}/{task_id}"
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
        "schema": CALIBRATION_PAIR_SCHEMA_V3,
        "scientific_status": (
            "candidate-development-v3-calibration-only-not-selection-evidence"
        ),
        "status": "CANDIDATE_POOL_V3_CALIBRATION_PAIR_COMPLETE",
        "candidate_id": candidate_id,
        "task_id": task_id,
        "pair_id": _pair_id(candidate_id, task_id),
        "software_revision": software_revision,
        "runner_protocol_sha256": calibration_runner_protocol_sha256_v3(),
        "representation_protocol_sha256": (
            EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256
        ),
        "qualification_freeze_sha256": (
            EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3
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
            "partial v3 calibration pair blocks automatic rerun: "
            f"{candidate_id}/{task_id}"
        )

    prompt = solver_prompt_transport_v3(blueprint)
    prompt_sha256 = store.put_bytes(prompt)
    pair_root.mkdir(parents=True)
    capture = pair_root / "transcript.txt"
    model_path = model_root / candidate_id / source["filename"]
    command = _load_command(
        cli=cli,
        model_path=model_path,
        prompt=prompt,
        capture=capture,
    )
    command_sha256 = _canonical_sha256(list(command))
    attempt = {
        "schema": CALIBRATION_ATTEMPT_SCHEMA_V3,
        "candidate_id": candidate_id,
        "task_id": task_id,
        "pair_id": _pair_id(candidate_id, task_id),
        "software_revision": software_revision,
        "runner_protocol_sha256": calibration_runner_protocol_sha256_v3(),
        "representation_protocol_sha256": (
            EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256
        ),
        "qualification_freeze_sha256": (
            EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3
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
    _write_json_atomic(
        pair_root / "attempt-observation.json",
        asdict(observation),
    )
    if observation.monitor_error is not None:
        raise RuntimeError(
            "calibration resource monitor failed for "
            f"{candidate_id}/{task_id}: {observation.monitor_error}"
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
        offloaded_layers, total_layers = (
            int(value) for value in offload_matches[-1]
        )

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
        return _finalize_pair(pair_root, base), True

    if not offload_matches:
        raise RuntimeError(
            "successful v3 calibration call lacks trace offload evidence: "
            f"{candidate_id}/{task_id}"
        )
    if offloaded_layers != total_layers:
        failure = (
            f"model was not fully offloaded: {offloaded_layers}/{total_layers}"
        )
        base.update(
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
        return _finalize_pair(pair_root, base), True
    if not capture.is_file():
        raise RuntimeError(f"v3 calibration transcript is missing: {capture}")

    transcript = capture.read_bytes()
    transcript_sha256 = hashlib.sha256(transcript).hexdigest()
    try:
        assistant, reasoning = extract_assistant_content_v6(
            transcript=transcript,
            prompt=prompt,
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
        accelerator_time_ms=max(
            0,
            round(observation.elapsed_seconds * 1000),
        ),
        peak_accelerator_bytes=(
            observation.peak_gpu_used_mib * 1024 * 1024
        ),
        peak_ram_bytes=observation.peak_process_rss_bytes or 0,
    )
    raw_artifact = StageArtifact(
        stage=CollectiveStage.RAW_MIND_OUTPUT,
        task=material.visible_task.task,
        run_id=f"candidate-pool-v3-calibration:{candidate_id}:{task_id}",
        producer_id=candidate_id,
        producer_configuration_sha256=_producer_configuration_sha256(
            source["source_identity_sha256"]
        ),
        protocol_sha256=calibration_runner_protocol_sha256_v3(),
        software_revision=software_revision,
        content_sha256=assistant_sha256,
        resources=resources,
    )
    if store.put_bytes(raw_artifact.canonical_bytes()) != raw_artifact.sha256:
        raise AssertionError(
            "v3 calibration raw artifact storage identity mismatch"
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
                "v3 calibration submission storage identity mismatch"
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
                "v3 calibration evaluation storage identity mismatch"
            )
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
    artifact_root: Path,
    *,
    software_revision: str,
) -> tuple[int, list[dict[str, Any]]]:
    complete = 0
    reports: list[dict[str, Any]] = []
    for candidate_id in V3_DEVELOPMENT_CANDIDATE_IDS:
        for task_id in CALIBRATION_TASK_IDS_V3:
            root = _pair_root(artifact_root, candidate_id, task_id)
            state = _pair_state(root)
            if state == "partial":
                raise RuntimeError(
                    "partial v3 calibration pair blocks all new inference: "
                    f"{candidate_id}/{task_id}"
                )
            if state == "complete":
                report = _load_json_ascii(root / "result.json")
                _validate_completed_pair(
                    report,
                    candidate_id=candidate_id,
                    task_id=task_id,
                    software_revision=software_revision,
                )
                complete += 1
                reports.append(report)
    return complete, reports


def _validate_material_bindings(
    materials: dict[str, Any],
    frozen_pack: dict[str, Any],
) -> None:
    entries = {
        item["task_id"]: item
        for item in frozen_pack["tasks"]
    }
    if tuple(entries) != CALIBRATION_TASK_IDS_V3:
        raise RuntimeError("frozen qualification pack task order drifted")
    for blueprint in _selected_blueprints():
        material = materials[blueprint.task_id]
        entry = entries[blueprint.task_id]
        prompt_sha = hashlib.sha256(
            solver_prompt_transport_v3(blueprint)
        ).hexdigest()
        if material.visible_task.sha256 != entry["task_sha256"]:
            raise RuntimeError(
                "v3 calibration visible-task identity drifted: "
                f"{blueprint.task_id}"
            )
        if prompt_sha != entry["solver_prompt_sha256"]:
            raise RuntimeError(
                "v3 calibration solver-prompt identity drifted: "
                f"{blueprint.task_id}"
            )


def _validate_completed_suite(
    path: Path,
    *,
    software_revision: str,
) -> dict[str, Any]:
    suite = _load_json_ascii(path)
    required = {
        "schema": CALIBRATION_SUITE_SCHEMA_V3,
        "scientific_status": (
            "candidate-development-v3-calibration-only-not-selection-evidence"
        ),
        "status": "CANDIDATE_POOL_V3_CALIBRATION_COMPLETE",
        "software_revision": software_revision,
        "runner_protocol_sha256": calibration_runner_protocol_sha256_v3(),
        "representation_protocol_sha256": (
            EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256
        ),
        "qualification_freeze_sha256": (
            EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3
        ),
        "pair_count": PAIR_COUNT_V3,
        "selection_evidence": False,
    }
    for key, expected in required.items():
        if suite.get(key) != expected:
            raise RuntimeError(
                f"completed v3 calibration suite field drifted: {key}"
            )
    unsigned = dict(suite)
    observed = unsigned.pop("report_sha256", None)
    if observed != _canonical_sha256(unsigned):
        raise RuntimeError("completed v3 calibration suite content drifted")
    if (
        not isinstance(suite.get("results"), list)
        or len(suite["results"]) != PAIR_COUNT_V3
    ):
        raise RuntimeError("completed v3 calibration suite result count drifted")
    if (
        not isinstance(suite.get("summaries"), list)
        or len(suite["summaries"])
        != len(V3_DEVELOPMENT_CANDIDATE_IDS)
    ):
        raise RuntimeError("completed v3 calibration suite summary count drifted")
    return suite


def run_calibration_v3(
    *,
    runtime_root: Path,
    model_root: Path,
    qualification_root: Path,
    artifact_root: Path,
    software_revision: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS_V3,
    docker_executable: str = "docker",
) -> dict[str, Any]:
    if type(timeout_seconds) is not int or timeout_seconds < 1:
        raise ValueError("timeout_seconds must be a positive integer")
    if _git_revision() != software_revision:
        raise RuntimeError(
            "software revision argument does not match current checkout"
        )
    validate_v3_representation_protocol()
    validate_calibration_qualification_freeze_v3()
    evidence = _verify_qualification_root(qualification_root)
    _verify_runtime_archives(runtime_root)
    cli = runtime_root / "bin" / "llama-cli.exe"
    runtime_observation = _runtime_observation(cli)
    sources = candidate_sources_v3()
    _verify_model_files(model_root, sources)
    blueprints = _selected_blueprints()

    suite_path = artifact_root / "candidate-pool-v3-calibration-suite.json"
    if suite_path.is_file():
        return _validate_completed_suite(
            suite_path,
            software_revision=software_revision,
        )

    artifact_root.mkdir(parents=True, exist_ok=True)
    _write_json_once(
        artifact_root / "calibration-runner-protocol-v3.json",
        calibration_runner_protocol_payload_v3(),
    )
    _write_json_once(
        artifact_root / "runtime-observation.json",
        asdict(runtime_observation),
    )

    completed_before, _ = _preflight_pair_states(
        artifact_root,
        software_revision=software_revision,
    )
    print(
        f"existing_completed_calibration_pairs={completed_before}/{PAIR_COUNT_V3}",
        flush=True,
    )
    print(
        f"expected_new_calibration_attempts={PAIR_COUNT_V3-completed_before}",
        flush=True,
    )

    store = FileContentStore(artifact_root / "store")
    staging_root = artifact_root / "staging"
    configuration = probe_qualified_docker_configuration(
        software_revision=software_revision,
        docker_executable=docker_executable,
    )

    results: list[dict[str, Any]] = []
    new_attempts = 0
    with tempfile.TemporaryDirectory(
        prefix="v3-calibration-material-",
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
        for candidate_id in V3_DEVELOPMENT_CANDIDATE_IDS:
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
                    f"parse_valid={report['parse_valid']} "
                    f"solved={report['solved']} "
                    f"new_inference_attempt={attempted} "
                    f"report_sha256={report['report_sha256']}",
                    flush=True,
                )

    if len(results) != PAIR_COUNT_V3:
        raise AssertionError(
            f"v3 calibration result count drifted: {len(results)}"
        )
    if staging_root.exists() and any(staging_root.iterdir()):
        raise RuntimeError(
            "v3 calibration left qualified-Docker staging residue"
        )

    summaries: list[dict[str, Any]] = []
    eligible: list[str] = []
    for candidate_id in V3_DEVELOPMENT_CANDIDATE_IDS:
        own = [
            item
            for item in results
            if item["candidate_id"] == candidate_id
        ]
        if len(own) != V3_FRESH_CALIBRATION_TASK_COUNT:
            raise AssertionError(
                f"candidate calibration task count drifted: {candidate_id}"
            )
        parse_valid_count = sum(
            bool(item["parse_valid"]) for item in own
        )
        solved_count = sum(bool(item["solved"]) for item in own)
        passed = _candidate_passed(parse_valid_count, solved_count)
        if passed:
            eligible.append(candidate_id)
        peak_gpu = max(
            int(item["attempt_observation"]["peak_gpu_used_mib"])
            for item in own
        )
        summaries.append(
            {
                "candidate_id": candidate_id,
                "task_count": V3_FRESH_CALIBRATION_TASK_COUNT,
                "parse_valid_count": parse_valid_count,
                "solved_count": solved_count,
                "passed_calibration_gate": passed,
                "peak_gpu_used_mib": peak_gpu,
            }
        )
        print(
            f"candidate={candidate_id} "
            f"calibration_summary=parse:{parse_valid_count}/6 "
            f"solved:{solved_count}/6 passed_gate={passed}",
            flush=True,
        )

    suite = {
        "schema": CALIBRATION_SUITE_SCHEMA_V3,
        "scientific_status": (
            "candidate-development-v3-calibration-only-not-selection-evidence"
        ),
        "status": "CANDIDATE_POOL_V3_CALIBRATION_COMPLETE",
        "software_revision": software_revision,
        "runner_protocol_sha256": calibration_runner_protocol_sha256_v3(),
        "representation_protocol_sha256": (
            EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256
        ),
        "qualification_freeze_sha256": (
            EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3
        ),
        "repaired_calibration_pack_sha256": (
            REPAIRED_CALIBRATION_PACK_CANONICAL_SHA256_V3
        ),
        "candidate_ids": list(V3_DEVELOPMENT_CANDIDATE_IDS),
        "task_ids": list(CALIBRATION_TASK_IDS_V3),
        "pair_count": len(results),
        "new_inference_attempt_count_this_invocation": new_attempts,
        "gate": {
            "required_parse_valid_count": V3_REQUIRED_PARSE_VALID_COUNT,
            "minimum_solved_count": V3_MINIMUM_SOLVED_COUNT,
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
    suite["report_sha256"] = _canonical_sha256(suite)
    _write_json_atomic(suite_path, suite)
    return suite


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run, safely resume, or reuse the fixed 4x6 "
            "candidate-pool v3 calibration gate."
        )
    )
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--qualification-root", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS_V3,
    )
    parser.add_argument("--docker-executable", default="docker")
    return parser


def _print_suite(suite: dict[str, Any], *, reused: bool) -> None:
    print("status=CANDIDATE_POOL_V3_CALIBRATION_COMPLETE")
    print(f"completed_suite_reused={reused}")
    print(f"report_sha256={suite['report_sha256']}")
    print(f"runner_protocol_sha256={suite['runner_protocol_sha256']}")
    print(
        "representation_protocol_sha256="
        + suite["representation_protocol_sha256"]
    )
    print(
        "qualification_freeze_sha256="
        + suite["qualification_freeze_sha256"]
    )
    print(f"pair_count={suite['pair_count']}")
    print(
        f"eligible_candidate_count={suite['eligible_candidate_count']}/4"
    )
    print(
        "eligible_candidate_ids="
        + ",".join(suite["eligible_candidate_ids"])
    )
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
    suite_path = args.artifact_root / "candidate-pool-v3-calibration-suite.json"
    try:
        if suite_path.is_file():
            suite = _validate_completed_suite(
                suite_path,
                software_revision=args.software_revision,
            )
            _print_suite(suite, reused=True)
            return 0
        suite = run_calibration_v3(
            runtime_root=args.runtime_root,
            model_root=args.model_root,
            qualification_root=args.qualification_root,
            artifact_root=args.artifact_root,
            software_revision=args.software_revision,
            timeout_seconds=args.timeout_seconds,
            docker_executable=args.docker_executable,
        )
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"status=CANDIDATE_POOL_V3_CALIBRATION_ABORT\nerror={exc}")
        return 2
    _print_suite(suite, reused=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
