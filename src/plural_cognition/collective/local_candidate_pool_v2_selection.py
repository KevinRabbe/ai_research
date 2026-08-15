"""Restart-safe one-shot five-by-twelve candidate-pool v2 selection runner.

This is the only authorized candidate-model execution on the fresh qualified v2
selection pack. Every candidate/task pair gets at most one model inference
attempt. Completed pairs are reused without inference; any partial pair blocks
the whole invocation before another model call is authorized.
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
from .bakeoff import (
    BakeoffPlan,
    CandidateModel,
    CandidateTaskResult,
    DeploymentClass,
    PopulationSelection,
    select_population,
)
from .candidate_pool_v2_calibration_protocol import (
    CALIBRATION_BATCH_THREADS_V2,
    CALIBRATION_BATCH_TOKENS_V2,
    CALIBRATION_CONTEXT_TOKENS_V2,
    CALIBRATION_LOG_VERBOSITY_V2,
    CALIBRATION_MICROBATCH_TOKENS_V2,
    CALIBRATION_PREDICT_TOKENS_V2,
    CALIBRATION_THREADS_V2,
    PREDECESSOR_RESOURCE_BUDGET_SHA256_V2,
)
from .candidate_pool_v2_operational_freeze import (
    CALIBRATION_SUITE_FILE_SHA256_V2,
    CALIBRATION_SUITE_REPORT_SHA256_V2,
    FINAL_CANDIDATE_IDS_V2,
    FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256,
)
from .candidate_pool_v2_selection_protocol import (
    BAKEOFF_SELECTOR_GIT_BLOB_SHA1,
    FINAL_SELECTION_PROTOCOL_SHA256_V2,
    FULL_FILE_INTERPRETER_GIT_BLOB_SHA1,
    SELECTION_MIN_VALID_RATE_V2,
    SELECTION_PACK_V2_GIT_BLOB_SHA1,
    SELECTION_PAIR_COUNT_V2,
    SELECTION_POPULATION_SIZE_V2,
    SELECTION_TASK_IDS_V2,
    candidate_pool_v2_selection_protocol_payload,
)
from .candidate_pool_v2_full_file import extract_full_file_patch_v2
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
from .local_raw_calibration import validate_patch_against_blueprint
from .local_raw_calibration_v6 import extract_assistant_content_v6
from .mind import MindIdentity
from .qualified_docker import probe_qualified_docker_configuration
from .repository_surgery import PatchFormat, RepositorySurgerySubmission
from .repository_surgery_calibration_matrix import _evaluate_patch, _metric
from .repository_surgery_selection_freeze_v2 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2,
    SELECTION_OPERATIONAL_CONFIG_FREEZE_SHA256_V2,
    SELECTION_PACK_SHA256_V2,
    SELECTION_PACK_SOURCE_REVISION_V2,
    SELECTION_QUALIFICATION_REPORT_SHA256_V2,
    SELECTION_QUALIFIED_DOCKER_REPORT_SHA256_V2,
    validate_selection_pack_freeze_v2_against_repository,
)
from .repository_surgery_selection_pack_v1 import (
    SelectionMaterial,
    build_selection_material,
)
from .repository_surgery_selection_pack_v2 import (
    SELECTION_TASK_COUNT_V2,
    selection_blueprints_v2,
    solver_prompt_transport_selection_v2,
)

SELECTION_PAIR_SCHEMA_V2 = "plural-cognition-candidate-pool-v2-selection-pair-v1"
SELECTION_ATTEMPT_SCHEMA_V2 = "plural-cognition-candidate-pool-v2-selection-attempt-v1"
SELECTION_SUITE_SCHEMA_V2 = "plural-cognition-candidate-pool-v2-selection-suite-v1"
SELECTION_INVALID_ARTIFACT_SCHEMA_V2 = "plural-cognition-candidate-pool-v2-selection-invalid-artifact-v1"
DEFAULT_TIMEOUT_SECONDS_V2 = 900

_PROMPT_TOKEN_RE = re.compile(r"prompt eval time\s*=.*?/\s*(\d+)\s+tokens", re.IGNORECASE)
_OUTPUT_TOKEN_RE = re.compile(r"eval time\s*=.*?/\s*(\d+)\s+runs", re.IGNORECASE)
_QUANTIZATION = {
    "qwen3-8b-q8": "Q8_0",
    "qwen2.5-coder-14b-q5km": "Q5_K_M",
    "devstral-24b-q4km": "Q4_K_M",
    "gpt-oss-20b-mxfp4": "native-mxfp4",
    "devstral-small-2-24b-q4km": "Q4_K_M",
}


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
                "schema": "plural-cognition-candidate-pool-v2-selection-pair-id-v1",
                "candidate_id": candidate_id,
                "task_id": task_id,
                "protocol_sha256": FINAL_SELECTION_PROTOCOL_SHA256_V2,
                "selection_pack_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2,
            }
        )
    ).hexdigest()


def _pair_root(artifact_root: Path, candidate_id: str, task_id: str) -> Path:
    return artifact_root / "pairs" / candidate_id / task_id


def _pair_state(path: Path) -> str:
    if (path / "result.json").is_file():
        return "complete"
    if path.exists():
        return "partial"
    return "missing"


def _token_counts(stderr: bytes) -> tuple[int, int, bool]:
    text = stderr.decode("utf-8", errors="replace")
    prompt = _PROMPT_TOKEN_RE.findall(text)
    output = _OUTPUT_TOKEN_RE.findall(text)
    if not prompt or not output:
        return 0, 0, False
    return int(prompt[-1]), int(output[-1]), True


def _candidate_sources() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for candidate_id in FINAL_CANDIDATE_IDS_V2[:3]:
        source = LOCAL_MODEL_SOURCE_FREEZE_V2.candidate(candidate_id)
        result[candidate_id] = {
            "candidate_id": candidate_id,
            "source_class": "unchanged-incumbent-v1-source-freeze",
            "filename": source.filename,
            "artifact_size_bytes": source.size_bytes,
            "artifact_sha256": source.artifact_sha256,
            "source_identity_sha256": source.sha256,
            "architecture_class": source.source_repository,
            "model_revision": source.source_repository_revision,
            "quantization": _QUANTIZATION[candidate_id],
        }

    challenger_payload = candidate_pool_v2_source_freeze_payload()
    challengers = {item["candidate_id"]: item for item in challenger_payload["challengers"]}
    for candidate_id in FINAL_CANDIDATE_IDS_V2[3:]:
        source = challengers[candidate_id]
        source_identity = hashlib.sha256(_canonical_json_bytes(source)).hexdigest()
        size = source["artifact_size_bytes"]
        if type(size) is not int or size < 1:
            raise RuntimeError(f"selection challenger lacks exact artifact size: {candidate_id}")
        result[candidate_id] = {
            "candidate_id": candidate_id,
            "source_class": "candidate-pool-v2-source-freeze",
            "filename": source["filename"],
            "artifact_size_bytes": size,
            "artifact_sha256": source["artifact_sha256"],
            "source_identity_sha256": source_identity,
            "architecture_class": source["first_party_repo"],
            "model_revision": source["artifact_linked_source_revision"],
            "quantization": source["quantization"],
        }

    if tuple(result) != FINAL_CANDIDATE_IDS_V2:
        raise AssertionError("v2 selection candidate source order drifted")
    return result


def _producer_configuration_sha256(source_identity_sha256: str) -> str:
    return hashlib.sha256(
        _canonical_json_bytes(
            {
                "schema": "plural-cognition-candidate-pool-v2-selection-producer-config-v1",
                "source_identity_sha256": source_identity_sha256,
                "protocol_sha256": FINAL_SELECTION_PROTOCOL_SHA256_V2,
            }
        )
    ).hexdigest()


def _candidate_models(sources: dict[str, dict[str, Any]]) -> tuple[CandidateModel, ...]:
    result: list[CandidateModel] = []
    for candidate_id in FINAL_CANDIDATE_IDS_V2:
        source = sources[candidate_id]
        configuration_sha256 = _producer_configuration_sha256(source["source_identity_sha256"])
        result.append(
            CandidateModel(
                candidate_id=candidate_id,
                mind=MindIdentity(
                    mind_id=candidate_id,
                    backend_family="llama.cpp-local",
                    model_id=source["architecture_class"],
                    model_revision=source["model_revision"],
                    configuration_sha256=configuration_sha256,
                ),
                deployment_class=DeploymentClass.LOCAL,
                architecture_class=source["architecture_class"],
                context_tokens=CALIBRATION_CONTEXT_TOKENS_V2,
                quantization=source["quantization"],
            )
        )
    return tuple(result)


def _verify_model_files(model_root: Path, sources: dict[str, dict[str, Any]]) -> None:
    for candidate_id in FINAL_CANDIDATE_IDS_V2:
        source = sources[candidate_id]
        path = model_root / candidate_id / source["filename"]
        if not path.is_file():
            raise RuntimeError(f"required v2 selection model is missing: {path}")
        size = path.stat().st_size
        if size != int(source["artifact_size_bytes"]):
            raise RuntimeError(
                f"model size mismatch for {candidate_id}: {size} != {source['artifact_size_bytes']}"
            )
        digest = _sha256_file(path)
        if digest != source["artifact_sha256"]:
            raise RuntimeError(f"model SHA-256 mismatch for {candidate_id}: {digest}")


def _verify_calibration_suite(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"completed v2 calibration suite is missing: {path}")
    if _sha256_file(path) != CALIBRATION_SUITE_FILE_SHA256_V2:
        raise RuntimeError("completed v2 calibration suite file SHA-256 drifted")
    suite = json.loads(path.read_text(encoding="ascii"))
    if suite.get("report_sha256") != CALIBRATION_SUITE_REPORT_SHA256_V2:
        raise RuntimeError("completed v2 calibration suite report identity drifted")
    if tuple(suite.get("eligible_candidate_ids", ())) != FINAL_CANDIDATE_IDS_V2:
        raise RuntimeError("completed v2 calibration eligible population drifted")
    if suite.get("pair_count") != 36 or suite.get("selection_evidence") is not False:
        raise RuntimeError("completed v2 calibration evidence fields drifted")


def _verify_frozen_selection_artifacts(
    selection_pack_path: Path, qualification_path: Path
) -> dict[str, Any]:
    if not selection_pack_path.is_file() or not qualification_path.is_file():
        raise RuntimeError("frozen v2 selection-pack or qualification artifact is missing")
    if _sha256_file(selection_pack_path) != SELECTION_PACK_SHA256_V2:
        raise RuntimeError("frozen v2 selection-pack artifact SHA-256 drifted")
    if _sha256_file(qualification_path) != SELECTION_QUALIFICATION_REPORT_SHA256_V2:
        raise RuntimeError("frozen v2 selection qualification artifact SHA-256 drifted")

    pack = json.loads(selection_pack_path.read_text(encoding="ascii"))
    qualification = json.loads(qualification_path.read_text(encoding="ascii"))

    if pack.get("operational_config_freeze_sha256") != SELECTION_OPERATIONAL_CONFIG_FREEZE_SHA256_V2:
        raise RuntimeError("v2 selection pack operational freeze binding drifted")
    if pack.get("task_count") != SELECTION_TASK_COUNT_V2:
        raise RuntimeError("v2 selection pack task count drifted")
    if tuple(pack.get("candidate_ids", ())) != FINAL_CANDIDATE_IDS_V2:
        raise RuntimeError("v2 selection pack candidate order drifted")
    pack_task_ids = tuple(item.get("task_id") for item in pack.get("tasks", ()))
    if pack_task_ids != SELECTION_TASK_IDS_V2:
        raise RuntimeError("v2 selection pack task identities drifted")

    required_qualification = {
        "software_revision": SELECTION_PACK_SOURCE_REVISION_V2,
        "operational_config_freeze_sha256": SELECTION_OPERATIONAL_CONFIG_FREEZE_SHA256_V2,
        "selection_pack_sha256": SELECTION_PACK_SHA256_V2,
        "qualified_docker_report_sha256": SELECTION_QUALIFIED_DOCKER_REPORT_SHA256_V2,
        "task_count": SELECTION_TASK_COUNT_V2,
        "candidate_model_inference_performed": False,
        "selection_outcomes_observed": False,
    }
    for key, expected in required_qualification.items():
        if qualification.get(key) != expected:
            raise RuntimeError(f"v2 selection qualification field drifted: {key}")

    qualifications = qualification.get("qualifications", ())
    if len(qualifications) != SELECTION_TASK_COUNT_V2:
        raise RuntimeError("v2 selection qualification task count drifted")
    qualification_by_task = {item["task_id"]: item for item in qualifications}
    if tuple(qualification_by_task) != SELECTION_TASK_IDS_V2:
        raise RuntimeError("v2 selection qualification task identities drifted")
    for task_id in SELECTION_TASK_IDS_V2:
        item = qualification_by_task[task_id]
        if float(item.get("baseline_exact_accuracy", 1.0)) >= 1.0:
            raise RuntimeError(f"v2 selection baseline is no longer observably defective: {task_id}")
        if float(item.get("gold_exact_accuracy", 0.0)) != 1.0:
            raise RuntimeError(f"v2 selection gold accuracy drifted: {task_id}")
        if float(item.get("gold_valid_rate", 0.0)) != 1.0:
            raise RuntimeError(f"v2 selection gold valid rate drifted: {task_id}")
    return pack


def _materials(
    *, store: FileContentStore, build_root: Path, frozen_pack: dict[str, Any]
) -> tuple[SelectionMaterial, ...]:
    expected = {item["task_id"]: item for item in frozen_pack["tasks"]}
    materials: list[SelectionMaterial] = []
    for blueprint in selection_blueprints_v2():
        material = build_selection_material(
            blueprint=blueprint,
            store=store,
            work_root=build_root / blueprint.task_id,
            software_revision=SELECTION_PACK_SOURCE_REVISION_V2,
        )
        entry = expected.get(blueprint.task_id)
        if entry is None:
            raise RuntimeError(f"frozen v2 pack lacks task: {blueprint.task_id}")
        actual = {
            "task_sha256": material.visible_task.sha256,
            "generation_record_sha256": material.generation_record.sha256,
            "evaluation_plan_sha256": material.evaluation_plan.sha256,
        }
        for key, value in actual.items():
            if entry.get(key) != value:
                raise RuntimeError(f"frozen v2 selection material drifted for {blueprint.task_id}: {key}")
        materials.append(material)
    if len(materials) != SELECTION_TASK_COUNT_V2 or len(expected) != SELECTION_TASK_COUNT_V2:
        raise RuntimeError("frozen v2 selection material count drifted")
    return tuple(materials)


def _plan(
    materials: Sequence[SelectionMaterial], sources: dict[str, dict[str, Any]]
) -> BakeoffPlan:
    return BakeoffPlan(
        tasks=tuple(item.visible_task.task for item in materials),
        candidates=_candidate_models(sources),
        raw_protocol_sha256=FINAL_SELECTION_PROTOCOL_SHA256_V2,
        resource_budget_sha256=PREDECESSOR_RESOURCE_BUDGET_SHA256_V2,
        min_valid_rate=SELECTION_MIN_VALID_RATE_V2,
        population_size=SELECTION_POPULATION_SIZE_V2,
        require_strongest_member=True,
    )


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
    if report.get("schema") != SELECTION_PAIR_SCHEMA_V2:
        raise RuntimeError(f"completed v2 selection pair schema drifted: {candidate_id}/{task_id}")
    expected = {
        "candidate_id": candidate_id,
        "task_id": task_id,
        "pair_id": _pair_id(candidate_id, task_id),
        "software_revision": software_revision,
        "protocol_sha256": FINAL_SELECTION_PROTOCOL_SHA256_V2,
        "selection_pack_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2,
        "selection_evidence": True,
    }
    for key, value in expected.items():
        if report.get(key) != value:
            raise RuntimeError(f"completed v2 selection pair field drifted: {candidate_id}/{task_id}:{key}")
    unsigned = dict(report)
    observed = unsigned.pop("report_sha256", None)
    expected_sha = hashlib.sha256(_canonical_json_bytes(unsigned)).hexdigest()
    if observed != expected_sha:
        raise RuntimeError(f"completed v2 selection pair content drifted: {candidate_id}/{task_id}")


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
        "schema": SELECTION_PAIR_SCHEMA_V2,
        "scientific_status": "candidate-pool-v2-fresh-selection-evidence",
        "status": "CANDIDATE_POOL_V2_SELECTION_PAIR_COMPLETE",
        "candidate_id": candidate_id,
        "task_id": task_id,
        "pair_id": _pair_id(candidate_id, task_id),
        "software_revision": software_revision,
        "protocol_sha256": FINAL_SELECTION_PROTOCOL_SHA256_V2,
        "selection_pack_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2,
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
        "selection_evidence": True,
    }


def _resources_from_base(base: dict[str, Any]) -> ResourceUsage:
    observation = base["attempt_observation"]
    return ResourceUsage(
        input_tokens=int(base["input_tokens"]),
        output_tokens=int(base["output_tokens"]),
        inference_calls=1,
        wall_time_ms=max(0, round(float(observation["elapsed_seconds"]) * 1000)),
        accelerator_time_ms=max(0, round(float(observation["elapsed_seconds"]) * 1000)),
        peak_accelerator_bytes=int(observation["peak_gpu_used_mib"]) * 1024 * 1024,
        peak_ram_bytes=int(observation["peak_process_rss_bytes"] or 0),
    )


def _invalid_bakeoff_artifacts(
    *,
    store: FileContentStore,
    candidate_id: str,
    task_id: str,
    reason: str,
    base: dict[str, Any],
) -> tuple[str, str]:
    raw_payload = {
        "schema": SELECTION_INVALID_ARTIFACT_SCHEMA_V2,
        "kind": "raw-output-unavailable",
        "candidate_id": candidate_id,
        "task_id": task_id,
        "reason": reason,
        "process_stdout_sha256": base["process_stdout_sha256"],
        "stderr_sha256": base["stderr_sha256"],
    }
    evaluation_payload = {
        "schema": SELECTION_INVALID_ARTIFACT_SCHEMA_V2,
        "kind": "invalid-evaluation",
        "candidate_id": candidate_id,
        "task_id": task_id,
        "reason": reason,
        "valid": False,
        "passed": False,
    }
    return (
        store.put_bytes(_canonical_json_bytes(raw_payload)),
        store.put_bytes(_canonical_json_bytes(evaluation_payload)),
    )


def _finalize_invalid_pair(
    *,
    pair_root: Path,
    base: dict[str, Any],
    store: FileContentStore,
    candidate_id: str,
    task_id: str,
    reason: str,
    inference_valid: bool,
    offloaded_layers: int | None,
    total_layers: int | None,
    transcript_sha256: str | None,
) -> dict[str, Any]:
    raw_sha, evaluation_sha = _invalid_bakeoff_artifacts(
        store=store,
        candidate_id=candidate_id,
        task_id=task_id,
        reason=reason,
        base=base,
    )
    base.update(
        {
            "inference_valid": inference_valid,
            "inference_failure": None if inference_valid else reason,
            "offloaded_layers": offloaded_layers,
            "total_layers": total_layers,
            "transcript_sha256": transcript_sha256,
            "assistant_sha256": None,
            "reasoning_sha256": None,
            "raw_artifact_sha256": None,
            "parse_valid": False,
            "parse_mode": None,
            "parse_error": reason,
            "patch_sha256": None,
            "submission_sha256": None,
            "evaluation_sha256": None,
            "exact_accuracy": 0.0,
            "evaluator_valid_rate": 0.0,
            "solved": False,
            "bakeoff_raw_artifact_sha256": raw_sha,
            "bakeoff_evaluation_sha256": evaluation_sha,
        }
    )
    return _finalize_pair(pair_root, base)


def _run_pair_once(
    *,
    candidate_id: str,
    source: dict[str, Any],
    blueprint: Any,
    material: SelectionMaterial,
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
            f"partial v2 selection pair blocks automatic rerun: {candidate_id}/{task_id}"
        )

    prompt = solver_prompt_transport_selection_v2(blueprint)
    prompt_sha256 = store.put_bytes(prompt)
    pair_root.mkdir(parents=True)
    capture = pair_root / "transcript.txt"
    model_path = model_root / candidate_id / source["filename"]
    command = _load_command(cli=cli, model_path=model_path, prompt=prompt, capture=capture)
    command_sha256 = hashlib.sha256(_canonical_json_bytes(list(command))).hexdigest()
    attempt = {
        "schema": SELECTION_ATTEMPT_SCHEMA_V2,
        "candidate_id": candidate_id,
        "task_id": task_id,
        "pair_id": _pair_id(candidate_id, task_id),
        "software_revision": software_revision,
        "protocol_sha256": FINAL_SELECTION_PROTOCOL_SHA256_V2,
        "selection_pack_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2,
        "model_file_sha256": source["artifact_sha256"],
        "task_sha256": material.visible_task.sha256,
        "prompt_sha256": prompt_sha256,
        "command_sha256": command_sha256,
        "inference_attempt_authorized": True,
        "max_attempts": 1,
        "selection_evidence": True,
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
            f"selection resource monitor failed for {candidate_id}/{task_id}: "
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

    transcript_sha256 = (
        hashlib.sha256(capture.read_bytes()).hexdigest() if capture.is_file() else None
    )
    if observation.timed_out or observation.exit_code != 0:
        failure = (
            f"llama-cli exceeded {timeout_seconds} seconds"
            if observation.timed_out
            else f"llama-cli exited {observation.exit_code}"
        )
        return (
            _finalize_invalid_pair(
                pair_root=pair_root,
                base=base,
                store=store,
                candidate_id=candidate_id,
                task_id=task_id,
                reason=failure,
                inference_valid=False,
                offloaded_layers=offloaded_layers,
                total_layers=total_layers,
                transcript_sha256=transcript_sha256,
            ),
            True,
        )

    if not offload_matches:
        raise RuntimeError(
            f"successful selection call lacks trace offload evidence: {candidate_id}/{task_id}"
        )
    if offloaded_layers != total_layers:
        failure = f"model was not fully offloaded: {offloaded_layers}/{total_layers}"
        return (
            _finalize_invalid_pair(
                pair_root=pair_root,
                base=base,
                store=store,
                candidate_id=candidate_id,
                task_id=task_id,
                reason=failure,
                inference_valid=False,
                offloaded_layers=offloaded_layers,
                total_layers=total_layers,
                transcript_sha256=transcript_sha256,
            ),
            True,
        )
    if not capture.is_file():
        raise RuntimeError(f"selection transcript is missing: {capture}")

    transcript = capture.read_bytes()
    transcript_sha256 = hashlib.sha256(transcript).hexdigest()
    try:
        assistant, reasoning = extract_assistant_content_v6(
            transcript=transcript, prompt=prompt
        )
    except ValueError as exc:
        failure = f"assistant transport invalid: {exc}"
        return (
            _finalize_invalid_pair(
                pair_root=pair_root,
                base=base,
                store=store,
                candidate_id=candidate_id,
                task_id=task_id,
                reason=failure,
                inference_valid=True,
                offloaded_layers=offloaded_layers,
                total_layers=total_layers,
                transcript_sha256=transcript_sha256,
            ),
            True,
        )

    (pair_root / "assistant.txt").write_bytes(assistant)
    reasoning_sha256: str | None = None
    if reasoning is not None:
        (pair_root / "reasoning.txt").write_bytes(reasoning)
        reasoning_sha256 = hashlib.sha256(reasoning).hexdigest()

    assistant_sha256 = store.put_bytes(assistant)
    resources = _resources_from_base(base)
    raw_artifact = StageArtifact(
        stage=CollectiveStage.RAW_MIND_OUTPUT,
        task=material.visible_task.task,
        run_id=f"candidate-pool-v2-selection:{candidate_id}:{task_id}",
        producer_id=candidate_id,
        producer_configuration_sha256=_producer_configuration_sha256(
            source["source_identity_sha256"]
        ),
        protocol_sha256=FINAL_SELECTION_PROTOCOL_SHA256_V2,
        software_revision=software_revision,
        content_sha256=assistant_sha256,
        resources=resources,
    )
    if store.put_bytes(raw_artifact.canonical_bytes()) != raw_artifact.sha256:
        raise AssertionError("v2 selection raw artifact storage identity mismatch")

    parse_valid = False
    parse_mode: str | None = None
    parse_error: str | None = None
    patch_sha256: str | None = None
    submission_sha256: str | None = None
    evaluation_sha256: str | None = None
    exact_accuracy = 0.0
    evaluator_valid_rate = 0.0
    solved = False
    bakeoff_evaluation_sha256: str

    try:
        patch, parse_mode = extract_full_file_patch_v2(assistant, blueprint)
        validate_patch_against_blueprint(patch, blueprint)
    except ValueError as exc:
        parse_error = str(exc)
        invalid_evaluation = {
            "schema": SELECTION_INVALID_ARTIFACT_SCHEMA_V2,
            "kind": "invalid-evaluation",
            "candidate_id": candidate_id,
            "task_id": task_id,
            "reason": parse_error,
            "valid": False,
            "passed": False,
            "raw_artifact_sha256": raw_artifact.sha256,
        }
        bakeoff_evaluation_sha256 = store.put_bytes(
            _canonical_json_bytes(invalid_evaluation)
        )
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
            raise AssertionError("v2 selection submission storage identity mismatch")
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
            raise AssertionError("v2 selection evaluation storage identity mismatch")
        bakeoff_evaluation_sha256 = evaluation_sha256
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
            "bakeoff_raw_artifact_sha256": raw_artifact.sha256,
            "bakeoff_evaluation_sha256": bakeoff_evaluation_sha256,
        }
    )
    return _finalize_pair(pair_root, base), True


def _preflight_pair_states(
    artifact_root: Path, *, software_revision: str
) -> tuple[int, list[dict[str, Any]]]:
    complete = 0
    reports: list[dict[str, Any]] = []
    for candidate_id in FINAL_CANDIDATE_IDS_V2:
        for task_id in SELECTION_TASK_IDS_V2:
            root = _pair_root(artifact_root, candidate_id, task_id)
            state = _pair_state(root)
            if state == "partial":
                raise RuntimeError(
                    f"partial v2 selection pair blocks all new inference: {candidate_id}/{task_id}"
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


def _candidate_task_result(
    report: dict[str, Any], material: SelectionMaterial
) -> CandidateTaskResult:
    return CandidateTaskResult(
        candidate_id=report["candidate_id"],
        task=material.visible_task.task,
        valid=bool(report["parse_valid"]),
        passed=bool(report["solved"]),
        raw_artifact_sha256=report["bakeoff_raw_artifact_sha256"],
        evaluation_sha256=report["bakeoff_evaluation_sha256"],
        resources=_resources_from_base(report),
    )


def _population_payload(selection: PopulationSelection) -> dict[str, Any]:
    return {
        "status": selection.status.value,
        "bakeoff_plan_sha256": selection.bakeoff_plan_sha256,
        "diagnostics": [asdict(item) for item in selection.diagnostics],
        "eligible_candidate_ids": list(selection.eligible_candidate_ids),
        "strongest_candidate_id": selection.strongest_candidate_id,
        "selected_candidate_ids": list(selection.selected_candidate_ids),
        "best_constituent_score": selection.best_constituent_score,
        "oracle_union_score": selection.oracle_union_score,
        "complementarity_headroom": selection.complementarity_headroom,
        "mean_pairwise_error_correlation": selection.mean_pairwise_error_correlation,
    }


def run_selection(
    *,
    runtime_root: Path,
    model_root: Path,
    artifact_root: Path,
    selection_pack_path: Path,
    qualification_path: Path,
    calibration_suite_path: Path,
    software_revision: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS_V2,
    docker_executable: str = "docker",
) -> dict[str, Any]:
    if type(timeout_seconds) is not int or timeout_seconds < 1:
        raise ValueError("timeout_seconds must be a positive integer")
    if _git_revision() != software_revision:
        raise RuntimeError("software revision argument does not match current checkout")

    validate_selection_pack_freeze_v2_against_repository()
    expected_blobs = {
        "src/plural_cognition/collective/repository_surgery_selection_pack_v2.py": SELECTION_PACK_V2_GIT_BLOB_SHA1,
        "src/plural_cognition/collective/candidate_pool_v2_full_file.py": FULL_FILE_INTERPRETER_GIT_BLOB_SHA1,
        "src/plural_cognition/collective/bakeoff.py": BAKEOFF_SELECTOR_GIT_BLOB_SHA1,
    }
    for path, expected in expected_blobs.items():
        observed = _git_blob_sha1(path)
        if observed != expected:
            raise RuntimeError(f"selection source blob drifted for {path}: {observed}")

    _verify_calibration_suite(calibration_suite_path)
    frozen_pack = _verify_frozen_selection_artifacts(
        selection_pack_path, qualification_path
    )
    _verify_runtime_archives(runtime_root)
    cli = runtime_root / "bin" / "llama-cli.exe"
    runtime_observation = _runtime_observation(cli)
    sources = _candidate_sources()
    _verify_model_files(model_root, sources)

    artifact_root.mkdir(parents=True, exist_ok=True)
    suite_path = artifact_root / "candidate-pool-v2-selection-suite.json"
    if suite_path.exists():
        raise RuntimeError("completed selection suite already exists; use the safe selection gate")

    protocol_bytes = _canonical_json_bytes(candidate_pool_v2_selection_protocol_payload())
    protocol_path = artifact_root / "selection-protocol.json"
    if protocol_path.is_file():
        if protocol_path.read_bytes().rstrip(b"\r\n") != protocol_bytes:
            raise RuntimeError("existing v2 selection protocol artifact drifted")
    else:
        _write_json_atomic(protocol_path, candidate_pool_v2_selection_protocol_payload())

    runtime_bytes = _canonical_json_bytes(asdict(runtime_observation))
    runtime_path = artifact_root / "runtime-observation.json"
    if runtime_path.is_file():
        if runtime_path.read_bytes().rstrip(b"\r\n") != runtime_bytes:
            raise RuntimeError("existing v2 selection runtime observation drifted")
    else:
        _write_json_atomic(runtime_path, asdict(runtime_observation))

    completed_before, _ = _preflight_pair_states(
        artifact_root, software_revision=software_revision
    )
    print(
        f"existing_completed_selection_pairs={completed_before}/{SELECTION_PAIR_COUNT_V2}",
        flush=True,
    )
    print(
        f"expected_new_selection_attempts={SELECTION_PAIR_COUNT_V2-completed_before}",
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
    with tempfile.TemporaryDirectory(prefix="v2-selection-material-", dir=artifact_root) as temp:
        build_root = Path(temp)
        materials = _materials(store=store, build_root=build_root, frozen_pack=frozen_pack)
        plan = _plan(materials, sources)
        plan_path = artifact_root / "bakeoff-plan.json"
        if plan_path.is_file():
            if plan_path.read_bytes().rstrip(b"\r\n") != plan.canonical_bytes():
                raise RuntimeError("existing v2 bakeoff plan drifted")
        else:
            plan_path.write_bytes(plan.canonical_bytes() + b"\n")

        material_by_task = {item.blueprint.task_id: item for item in materials}
        for candidate_id in FINAL_CANDIDATE_IDS_V2:
            source = sources[candidate_id]
            for blueprint in selection_blueprints_v2():
                report, attempted = _run_pair_once(
                    candidate_id=candidate_id,
                    source=source,
                    blueprint=blueprint,
                    material=material_by_task[blueprint.task_id],
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

        if len(results) != SELECTION_PAIR_COUNT_V2:
            raise AssertionError(f"v2 selection result count drifted: {len(results)}")
        if staging_root.exists() and any(staging_root.iterdir()):
            raise RuntimeError("v2 selection left qualified-Docker staging residue")

        candidate_results = [
            _candidate_task_result(item, material_by_task[item["task_id"]])
            for item in results
        ]
        selection = select_population(plan, candidate_results)

    suite = {
        "schema": SELECTION_SUITE_SCHEMA_V2,
        "scientific_status": "candidate-pool-v2-fresh-selection-evidence",
        "status": "CANDIDATE_POOL_V2_SELECTION_COMPLETE",
        "software_revision": software_revision,
        "protocol_sha256": FINAL_SELECTION_PROTOCOL_SHA256_V2,
        "selection_pack_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2,
        "selection_pack_sha256": SELECTION_PACK_SHA256_V2,
        "qualification_report_sha256": SELECTION_QUALIFICATION_REPORT_SHA256_V2,
        "operational_config_freeze_sha256": FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256,
        "calibration_suite_file_sha256": CALIBRATION_SUITE_FILE_SHA256_V2,
        "candidate_ids": list(FINAL_CANDIDATE_IDS_V2),
        "task_ids": list(SELECTION_TASK_IDS_V2),
        "pair_count": len(results),
        "new_inference_attempt_count_this_invocation": new_attempts,
        "bakeoff_plan_sha256": plan.sha256,
        "results": [
            {
                "candidate_id": item["candidate_id"],
                "task_id": item["task_id"],
                "report_sha256": item["report_sha256"],
                "parse_valid": item["parse_valid"],
                "solved": item["solved"],
                "exact_accuracy": item["exact_accuracy"],
                "evaluator_valid_rate": item["evaluator_valid_rate"],
            }
            for item in results
        ],
        "population_selection": _population_payload(selection),
        "selection_evidence": True,
    }
    suite_sha = hashlib.sha256(_canonical_json_bytes(suite)).hexdigest()
    suite["report_sha256"] = suite_sha
    _write_json_atomic(suite_path, suite)
    return suite


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run or safely resume the frozen five-by-twelve candidate-pool v2 selection."
    )
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--selection-pack", required=True, type=Path)
    parser.add_argument("--qualification-report", required=True, type=Path)
    parser.add_argument("--calibration-suite", required=True, type=Path)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS_V2)
    parser.add_argument("--docker-executable", default="docker")
    return parser


def _print_suite(suite: dict[str, Any]) -> None:
    selection = suite["population_selection"]
    print("status=CANDIDATE_POOL_V2_SELECTION_COMPLETE")
    print(f"report_sha256={suite['report_sha256']}")
    print(f"protocol_sha256={suite['protocol_sha256']}")
    print(f"selection_pack_freeze_sha256={suite['selection_pack_freeze_sha256']}")
    print(f"pair_count={suite['pair_count']}")
    print(
        "new_inference_attempt_count_this_invocation="
        + str(suite["new_inference_attempt_count_this_invocation"])
    )
    for diagnostic in selection["diagnostics"]:
        print(
            f"candidate={diagnostic['candidate_id']} score={diagnostic['score']:.6f} "
            f"valid_rate={diagnostic['valid_rate']:.6f} pass_count={diagnostic['pass_count']} "
            f"valid_count={diagnostic['valid_count']} accelerator_time_ms={diagnostic['total_accelerator_time_ms']} "
            f"tokens={diagnostic['total_tokens']}"
        )
    print(f"selection_status={selection['status']}")
    print(f"eligible_candidate_ids={','.join(selection['eligible_candidate_ids'])}")
    print(f"strongest_candidate_id={selection['strongest_candidate_id'] or ''}")
    print(f"selected_candidate_ids={','.join(selection['selected_candidate_ids'])}")
    print(f"best_constituent_score={selection['best_constituent_score']}")
    print(f"oracle_union_score={selection['oracle_union_score']}")
    print(f"complementarity_headroom={selection['complementarity_headroom']}")
    print(f"mean_pairwise_error_correlation={selection['mean_pairwise_error_correlation']}")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        suite = run_selection(
            runtime_root=args.runtime_root,
            model_root=args.model_root,
            artifact_root=args.artifact_root,
            selection_pack_path=args.selection_pack,
            qualification_path=args.qualification_report,
            calibration_suite_path=args.calibration_suite,
            software_revision=args.software_revision,
            timeout_seconds=args.timeout_seconds,
            docker_executable=args.docker_executable,
        )
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"status=CANDIDATE_POOL_V2_SELECTION_ABORT\nerror={exc}")
        return 2
    _print_suite(suite)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
