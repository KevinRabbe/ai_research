"""Recover the interrupted targeted V5 self-review run without repeating completed calls.

The first target execution reached the tenth of twelve review calls and then failed while
persisting a non-scientific process-stdout sidecar. This recovery path is intentionally
separate from the original runner. It treats the partial artifact root as immutable,
reconstructs the exact twelve review prompts from frozen V4 drafts, requires exactly the
first ten transcript captures and no captures for the final two pairs, reuses those ten
transcripts without model inference, and performs exactly the two missing review calls.

No V5 candidate output is inspected to choose the recovery rule. The scientific V5
protocol and continuation gate are unchanged; this module only repairs orchestration and
evidence durability. The consumed V1 split remains development-only evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from .consumed_selection_development_v5_self_review import (
    DEVELOPMENT_PROTOCOL_SHA256_V5,
    TARGET_CANDIDATE_IDS_V5,
    TARGET_RESULT_COUNT_V5,
    TARGET_TASK_IDS_V5,
    TARGET_V4_PARSED_COUNT_V5,
    TARGET_V4_SOLVED_COUNT_V5,
    development_protocol_payload_v5,
    extract_reviewed_patch_v5,
)
from .content_store import FileContentStore
from .local_consumed_selection_development_v5_self_review import (
    DEFAULT_TIMEOUT_SECONDS,
    _development_configuration_sha256,
    _load_frozen_v4_drafts,
    _review_prompt,
)
from .local_model_load_preflight import _run_load, _verify_model_file, _verify_runtime_archives
from .local_models import LOCAL_MODEL_SOURCE_FREEZE_V2
from .local_operational_freeze_v1 import FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1
from .local_raw_calibration import validate_patch_against_blueprint
from .local_raw_calibration_v6 import extract_assistant_content_v6
from .local_selection_bakeoff_v1 import (
    _load_command,
    _materials,
    _metric,
    _runtime_observation_resilient,
    _token_counts,
    _verify_frozen_artifacts,
)
from .qualified_docker import probe_qualified_docker_configuration
from .repository_surgery import PatchFormat, RepositorySurgerySubmission
from .repository_surgery_calibration_matrix import _evaluate_patch
from .repository_surgery_selection_freeze_v1 import FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256
from .repository_surgery_selection_outcome_freeze_v1 import FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256
from .repository_surgery_selection_pack_v1 import selection_blueprints

RECOVERY_SCHEMA_V5 = "plural-cognition-consumed-selection-development-v5-self-review-recovery-v1"
RECOVERY_MANIFEST_SCHEMA_V5 = "plural-cognition-consumed-selection-development-v5-partial-manifest-v1"
RECOVERY_OUTPUT_MANIFEST_SCHEMA_V5 = "plural-cognition-consumed-selection-development-v5-recovery-output-manifest-v1"
ORIGINAL_V5_SOFTWARE_REVISION = "e9fb2e9630080dfe88ad5faaf15702d5643032cd"
PARTIAL_REUSED_REVIEW_CALLS_V5 = 10
RECOVERY_NEW_REVIEW_CALLS_V5 = 2

_EXPECTED_PAIR_ORDER_V5 = tuple(
    (candidate_id, task_id)
    for candidate_id in TARGET_CANDIDATE_IDS_V5
    for task_id in TARGET_TASK_IDS_V5
)
PARTIAL_REUSED_PAIRS_V5 = _EXPECTED_PAIR_ORDER_V5[:PARTIAL_REUSED_REVIEW_CALLS_V5]
RECOVERY_NEW_PAIRS_V5 = _EXPECTED_PAIR_ORDER_V5[PARTIAL_REUSED_REVIEW_CALLS_V5:]


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_bytes_durable(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def _partial_manifest(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise ValueError(f"partial V5 artifact root is missing: {root}")
    if (root / "consumed-selection-development-v5-self-review.json").exists():
        raise ValueError("partial V5 root unexpectedly contains a complete report")
    if (root / "output-channel-manifest.json").exists():
        raise ValueError("partial V5 root unexpectedly contains a final output manifest")
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file():
            raw = path.read_bytes()
            entries.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "size_bytes": len(raw),
                    "sha256": _sha256_bytes(raw),
                }
            )
    payload = {"schema": RECOVERY_MANIFEST_SCHEMA_V5, "entries": entries}
    payload["sha256"] = _sha256_bytes(_canonical_json_bytes(payload))
    return payload


def _write_recovery_output_manifest(root: Path) -> str:
    entries: list[dict[str, Any]] = []
    for directory in (root / "reused-partial-output", root / "llama-output"):
        if directory.is_dir():
            for path in sorted(directory.rglob("*"), key=lambda item: item.as_posix()):
                if path.is_file():
                    raw = path.read_bytes()
                    entries.append(
                        {
                            "path": path.relative_to(root).as_posix(),
                            "size_bytes": len(raw),
                            "sha256": _sha256_bytes(raw),
                        }
                    )
    payload = {
        "schema": RECOVERY_OUTPUT_MANIFEST_SCHEMA_V5,
        "development_protocol_sha256": DEVELOPMENT_PROTOCOL_SHA256_V5,
        "entries": entries,
    }
    raw = _canonical_json_bytes(payload)
    (root / "output-channel-manifest.json").write_bytes(raw)
    return _sha256_bytes(raw)


def _expected_prompts(
    *, v4_targeted_root: Path, v4_remainder_root: Path
) -> tuple[
    dict[tuple[str, str], dict[str, Any]],
    dict[str, Any],
    dict[tuple[str, str], tuple[bytes, str]],
]:
    frozen_v4 = _load_frozen_v4_drafts(v4_targeted_root, v4_remainder_root)
    blueprints = {item.task_id: item for item in selection_blueprints()}
    prompts: dict[tuple[str, str], tuple[bytes, str]] = {}
    for pair in _EXPECTED_PAIR_ORDER_V5:
        candidate_id, task_id = pair
        frozen = frozen_v4[pair]
        prompt = _review_prompt(blueprints[task_id], frozen["draft_output"])
        prompts[pair] = (prompt, _sha256_bytes(prompt))
    return frozen_v4, blueprints, prompts


def validate_partial_v5_root(
    *, partial_root: Path, v4_targeted_root: Path, v4_remainder_root: Path
) -> dict[str, Any]:
    """Validate the no-repeat recovery boundary without interpreting candidate answers."""

    manifest = _partial_manifest(partial_root)
    _frozen_v4, _blueprints, prompts = _expected_prompts(
        v4_targeted_root=v4_targeted_root, v4_remainder_root=v4_remainder_root
    )
    actual_transcripts = tuple(
        sorted(
            path.relative_to(partial_root).as_posix()
            for path in (partial_root / "llama-output").rglob("*.transcript.txt")
        )
    )
    if len(actual_transcripts) != PARTIAL_REUSED_REVIEW_CALLS_V5:
        raise ValueError(
            "partial V5 transcript count drifted: "
            f"{len(actual_transcripts)} != {PARTIAL_REUSED_REVIEW_CALLS_V5}"
        )

    expected_paths: list[str] = []
    for candidate_id, task_id in PARTIAL_REUSED_PAIRS_V5:
        _prompt, prompt_sha256 = prompts[(candidate_id, task_id)]
        path = partial_root / "llama-output" / candidate_id / f"{prompt_sha256}.transcript.txt"
        expected_paths.append(path.relative_to(partial_root).as_posix())
        if not path.is_file():
            raise ValueError(f"required completed V5 transcript is missing: {path}")
    if tuple(sorted(expected_paths)) != actual_transcripts:
        raise ValueError("partial V5 transcripts are not exactly the first ten predeclared pairs")

    for candidate_id, task_id in RECOVERY_NEW_PAIRS_V5:
        _prompt, prompt_sha256 = prompts[(candidate_id, task_id)]
        path = partial_root / "llama-output" / candidate_id / f"{prompt_sha256}.transcript.txt"
        if path.exists():
            raise ValueError(f"would repeat an already captured V5 review call: {path}")

    return {
        "partial_manifest": manifest,
        "reused_pairs": list(PARTIAL_REUSED_PAIRS_V5),
        "new_pairs": list(RECOVERY_NEW_PAIRS_V5),
    }


def _evaluate_answer(
    *,
    assistant: bytes,
    candidate_id: str,
    task_id: str,
    blueprint: Any,
    material: Any,
    configuration: Any,
    store: FileContentStore,
    staging_root: Path,
    producer_record_sha256: str,
    docker_executable: str,
) -> dict[str, Any]:
    parse_valid = False
    parse_mode: str | None = None
    parse_error: str | None = None
    patch_sha256: str | None = None
    submission_sha256: str | None = None
    exact_accuracy = 0.0
    evaluator_valid_rate = 0.0
    solved = False
    try:
        patch, parse_mode = extract_reviewed_patch_v5(assistant, blueprint)
        validate_patch_against_blueprint(patch, blueprint)
    except ValueError as exc:
        parse_error = str(exc)
        invalid = {
            "schema": "plural-cognition-consumed-selection-development-invalid-v5-self-review-recovery",
            "candidate_id": candidate_id,
            "task_id": task_id,
            "producer_record_sha256": producer_record_sha256,
            "parse_error": parse_error,
        }
        evaluation_sha256 = store.put_bytes(_canonical_json_bytes(invalid))
    else:
        parse_valid = True
        patch_sha256 = store.put_bytes(patch)
        submission = RepositorySurgerySubmission(
            task_id=material.visible_task.task.task_id,
            task_payload_sha256=material.visible_task.task.payload_sha256,
            producer_artifact_sha256=producer_record_sha256,
            patch_sha256=patch_sha256,
            patch_format=PatchFormat.UNIFIED_DIFF,
            patch_size_bytes=len(patch),
        )
        submission_sha256 = store.put_bytes(submission.canonical_bytes())
        if submission_sha256 != submission.sha256:
            raise AssertionError("V5 recovery submission storage identity mismatch")
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
            raise AssertionError("V5 recovery evaluation storage identity mismatch")
        exact_accuracy = _metric(evaluation, "exact_accuracy")
        evaluator_valid_rate = _metric(evaluation, "valid_rate")
        solved = bool(evaluation.qualified)
    return {
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


def run_targeted_v5_recovery(
    *,
    runtime_root: Path,
    model_root: Path,
    artifact_root: Path,
    partial_root: Path,
    selection_pack_path: Path,
    qualification_path: Path,
    v4_targeted_root: Path,
    v4_remainder_root: Path,
    software_revision: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    docker_executable: str = "docker",
) -> dict[str, Any]:
    if artifact_root.exists():
        raise ValueError(f"fresh V5 recovery artifact already exists: {artifact_root}")
    if type(timeout_seconds) is not int or timeout_seconds < 1:
        raise ValueError("timeout_seconds must be a positive integer")

    boundary = validate_partial_v5_root(
        partial_root=partial_root,
        v4_targeted_root=v4_targeted_root,
        v4_remainder_root=v4_remainder_root,
    )
    partial_manifest = boundary["partial_manifest"]
    frozen_v4, blueprints, prompts = _expected_prompts(
        v4_targeted_root=v4_targeted_root, v4_remainder_root=v4_remainder_root
    )

    selected_v4 = [frozen_v4[pair]["result"] for pair in _EXPECTED_PAIR_ORDER_V5]
    baseline = (
        len(selected_v4),
        sum(1 for item in selected_v4 if item["parse_valid"]),
        sum(1 for item in selected_v4 if item["solved"]),
    )
    if baseline != (TARGET_RESULT_COUNT_V5, TARGET_V4_PARSED_COUNT_V5, TARGET_V4_SOLVED_COUNT_V5):
        raise ValueError(f"predeclared V5 targeted V4 baseline drifted: {baseline}")

    FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.validate_against()
    frozen_pack = _verify_frozen_artifacts(selection_pack_path, qualification_path)
    _verify_runtime_archives(runtime_root)
    cli = runtime_root / "bin" / "llama-cli.exe"
    runtime_observation = _runtime_observation_resilient(cli)
    runtime_observation_bytes = _canonical_json_bytes(asdict(runtime_observation))
    runtime_observation_sha256 = _sha256_bytes(runtime_observation_bytes)
    for candidate_id in TARGET_CANDIDATE_IDS_V5:
        source = LOCAL_MODEL_SOURCE_FREEZE_V2.candidate(candidate_id)
        _verify_model_file(model_root / candidate_id / source.filename, source)

    artifact_root.mkdir(parents=True)
    store = FileContentStore(artifact_root / "store")
    build_root = artifact_root / "build"
    build_root.mkdir()
    staging_root = artifact_root / "staging"
    configuration = probe_qualified_docker_configuration(
        software_revision=software_revision, docker_executable=docker_executable
    )
    materials = _materials(store=store, build_root=build_root, frozen_pack=frozen_pack)
    material_by_task = {item.blueprint.task_id: item for item in materials}
    (artifact_root / "runtime-observation.json").write_bytes(runtime_observation_bytes)
    (artifact_root / "development-protocol.json").write_bytes(
        _canonical_json_bytes(development_protocol_payload_v5())
    )
    (artifact_root / "partial-root-manifest.json").write_bytes(
        _canonical_json_bytes(partial_manifest)
    )

    results: list[dict[str, Any]] = []
    for candidate_id, task_id in _EXPECTED_PAIR_ORDER_V5:
        blueprint = blueprints[task_id]
        material = material_by_task[task_id]
        frozen = frozen_v4[(candidate_id, task_id)]
        draft_result = frozen["result"]
        prompt, prompt_sha256 = prompts[(candidate_id, task_id)]
        raw_stderr_sha256: str | None = None
        token_counts_observed: bool | None = None
        input_tokens: int | None = None
        output_tokens: int | None = None
        elapsed_seconds: float | None = None
        baseline_gpu_used_mib: int | None = None
        peak_gpu_used_mib: int | None = None
        peak_process_rss_bytes: int | None = None
        offloaded_layers: int | None = None
        total_layers: int | None = None

        if (candidate_id, task_id) in PARTIAL_REUSED_PAIRS_V5:
            transcript_path = (
                partial_root / "llama-output" / candidate_id / f"{prompt_sha256}.transcript.txt"
            )
            transcript = transcript_path.read_bytes()
            assistant, reasoning = extract_assistant_content_v6(transcript=transcript, prompt=prompt)
            existing_assistant = transcript_path.with_suffix(".assistant.txt")
            if existing_assistant.is_file() and existing_assistant.read_bytes() != assistant:
                raise ValueError(f"partial V5 assistant sidecar disagrees with transcript: {existing_assistant}")
            copy_root = artifact_root / "reused-partial-output" / candidate_id
            _write_bytes_durable(copy_root / transcript_path.name, transcript)
            _write_bytes_durable(copy_root / f"{prompt_sha256}.transcript.assistant.txt", assistant)
            if reasoning is not None:
                _write_bytes_durable(copy_root / f"{prompt_sha256}.transcript.reasoning.txt", reasoning)
            source_kind = "partial-transcript-reused-no-inference"
            new_review_inference = False
            provenance = {
                "schema": "plural-cognition-v5-recovery-reused-output-v1",
                "candidate_id": candidate_id,
                "task_id": task_id,
                "development_protocol_sha256": DEVELOPMENT_PROTOCOL_SHA256_V5,
                "original_v5_software_revision": ORIGINAL_V5_SOFTWARE_REVISION,
                "partial_root_manifest_sha256": partial_manifest["sha256"],
                "review_prompt_sha256": prompt_sha256,
                "transcript_sha256": _sha256_bytes(transcript),
                "raw_output_sha256": _sha256_bytes(assistant),
            }
        else:
            source = LOCAL_MODEL_SOURCE_FREEZE_V2.candidate(candidate_id)
            model_path = model_root / candidate_id / source.filename
            output_root = artifact_root / "llama-output" / candidate_id
            output_root.mkdir(parents=True, exist_ok=True)
            capture = output_root / f"{prompt_sha256}.transcript.txt"
            command = _load_command(cli=cli, model_path=model_path, prompt=prompt, capture=capture)
            load, process_stdout, stderr = _run_load(command, timeout_seconds=timeout_seconds)
            if not capture.is_file():
                raise RuntimeError(f"V5 recovery transcript is missing after inference: {capture}")
            transcript = capture.read_bytes()
            assistant, reasoning = extract_assistant_content_v6(transcript=transcript, prompt=prompt)
            _write_bytes_durable(capture, transcript)
            _write_bytes_durable(capture.with_suffix(".process-stdout.bin"), process_stdout)
            _write_bytes_durable(capture.with_suffix(".assistant.txt"), assistant)
            if reasoning is not None:
                _write_bytes_durable(capture.with_suffix(".reasoning.txt"), reasoning)
            input_tokens, output_tokens, token_counts_observed = _token_counts(stderr)
            raw_stderr_sha256 = store.put_bytes(stderr)
            elapsed_seconds = load.elapsed_seconds
            baseline_gpu_used_mib = load.baseline_gpu_used_mib
            peak_gpu_used_mib = load.peak_gpu_used_mib
            peak_process_rss_bytes = load.peak_process_rss_bytes
            offloaded_layers = load.offloaded_layers
            total_layers = load.total_layers
            source_kind = "missing-review-inference"
            new_review_inference = True
            provenance = {
                "schema": "plural-cognition-v5-recovery-new-output-v1",
                "candidate_id": candidate_id,
                "task_id": task_id,
                "development_protocol_sha256": DEVELOPMENT_PROTOCOL_SHA256_V5,
                "recovery_software_revision": software_revision,
                "review_prompt_sha256": prompt_sha256,
                "transcript_sha256": _sha256_bytes(transcript),
                "raw_output_sha256": _sha256_bytes(assistant),
                "raw_stderr_sha256": raw_stderr_sha256,
                "load_observation": asdict(load),
            }

        raw_output_sha256 = store.put_bytes(assistant)
        producer_record_sha256 = store.put_bytes(_canonical_json_bytes(provenance))
        evaluated = _evaluate_answer(
            assistant=assistant,
            candidate_id=candidate_id,
            task_id=task_id,
            blueprint=blueprint,
            material=material,
            configuration=configuration,
            store=store,
            staging_root=staging_root,
            producer_record_sha256=producer_record_sha256,
            docker_executable=docker_executable,
        )
        results.append(
            {
                "candidate_id": candidate_id,
                "task_id": task_id,
                "source_kind": source_kind,
                "new_review_inference": new_review_inference,
                "draft_reused_from_v4": True,
                "draft_prompt_sha256": draft_result["prompt_sha256"],
                "draft_raw_output_sha256": frozen["draft_output_sha256"],
                "draft_parse_valid": bool(draft_result["parse_valid"]),
                "draft_solved": bool(draft_result["solved"]),
                "review_prompt_sha256": prompt_sha256,
                "development_configuration_sha256": _development_configuration_sha256(candidate_id),
                "producer_record_sha256": producer_record_sha256,
                "raw_output_sha256": raw_output_sha256,
                "output_changed_from_draft": raw_output_sha256 != frozen["draft_output_sha256"],
                "transcript_sha256": _sha256_bytes(transcript),
                "raw_stderr_sha256": raw_stderr_sha256,
                "parse_valid": evaluated["parse_valid"],
                "parse_mode": evaluated["parse_mode"],
                "parse_error": evaluated["parse_error"],
                "patch_sha256": evaluated["patch_sha256"],
                "submission_sha256": evaluated["submission_sha256"],
                "evaluation_sha256": evaluated["evaluation_sha256"],
                "exact_accuracy": evaluated["exact_accuracy"],
                "evaluator_valid_rate": evaluated["evaluator_valid_rate"],
                "solved": evaluated["solved"],
                "token_counts_observed": token_counts_observed,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "elapsed_seconds": elapsed_seconds,
                "baseline_gpu_used_mib": baseline_gpu_used_mib,
                "peak_gpu_used_mib": peak_gpu_used_mib,
                "peak_process_rss_bytes": peak_process_rss_bytes,
                "offloaded_layers": offloaded_layers,
                "total_layers": total_layers,
            }
        )

    if len(results) != TARGET_RESULT_COUNT_V5:
        raise AssertionError("V5 recovery did not construct the exact 12-pair matrix")
    if sum(1 for item in results if item["new_review_inference"]) != RECOVERY_NEW_REVIEW_CALLS_V5:
        raise AssertionError("V5 recovery new-inference count drifted")
    if staging_root.exists() and any(staging_root.iterdir()):
        raise RuntimeError("V5 recovery left Docker staging residue")

    report = {
        "schema": RECOVERY_SCHEMA_V5,
        "scientific_status": "development-only-consumed-split-self-review-not-selection-evidence",
        "development_protocol_sha256": DEVELOPMENT_PROTOCOL_SHA256_V5,
        "original_v5_software_revision": ORIGINAL_V5_SOFTWARE_REVISION,
        "recovery_software_revision": software_revision,
        "consumed_selection_outcome_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256,
        "selection_pack_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256,
        "operational_config_freeze_sha256": FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.sha256,
        "runtime_observation_sha256": runtime_observation_sha256,
        "partial_root_manifest_sha256": partial_manifest["sha256"],
        "partial_review_inference_calls_reused": PARTIAL_REUSED_REVIEW_CALLS_V5,
        "new_review_inference_calls": RECOVERY_NEW_REVIEW_CALLS_V5,
        "total_review_inference_calls": TARGET_RESULT_COUNT_V5,
        "base_generation_reused": True,
        "candidate_ids": list(TARGET_CANDIDATE_IDS_V5),
        "task_ids": list(TARGET_TASK_IDS_V5),
        "result_count": len(results),
        "results": results,
    }
    report_bytes = _canonical_json_bytes(report)
    report_path = artifact_root / "consumed-selection-development-v5-self-review-recovery.json"
    report_path.write_bytes(report_bytes)
    report_sha256 = _sha256_bytes(report_bytes)
    output_manifest_sha256 = _write_recovery_output_manifest(artifact_root)
    report["report_sha256"] = report_sha256
    report["output_manifest_sha256"] = output_manifest_sha256
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recover targeted V5 without repeating its first ten completed review calls.")
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--partial-root", required=True, type=Path)
    parser.add_argument("--selection-pack", required=True, type=Path)
    parser.add_argument("--qualification-report", required=True, type=Path)
    parser.add_argument("--v4-targeted-root", required=True, type=Path)
    parser.add_argument("--v4-remainder-root", required=True, type=Path)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--docker-executable", default="docker")
    args = parser.parse_args(argv)
    try:
        report = run_targeted_v5_recovery(
            runtime_root=args.runtime_root,
            model_root=args.model_root,
            artifact_root=args.artifact_root,
            partial_root=args.partial_root,
            selection_pack_path=args.selection_pack,
            qualification_path=args.qualification_report,
            v4_targeted_root=args.v4_targeted_root,
            v4_remainder_root=args.v4_remainder_root,
            software_revision=args.software_revision,
            timeout_seconds=args.timeout_seconds,
            docker_executable=args.docker_executable,
        )
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"status=CONSUMED_SELECTION_DEVELOPMENT_V5_RECOVERY_FAIL\nerror={exc}")
        return 2

    parsed = sum(1 for item in report["results"] if item["parse_valid"])
    solved = sum(1 for item in report["results"] if item["solved"])
    recovered = sum(1 for item in report["results"] if not item["draft_solved"] and item["solved"])
    regressions = sum(1 for item in report["results"] if item["draft_solved"] and not item["solved"])
    print("status=CONSUMED_SELECTION_DEVELOPMENT_V5_RECOVERY_PASS")
    print(f"report_sha256={report['report_sha256']}")
    print(f"output_manifest_sha256={report['output_manifest_sha256']}")
    print(f"development_protocol_sha256={report['development_protocol_sha256']}")
    print(f"partial_root_manifest_sha256={report['partial_root_manifest_sha256']}")
    print(f"partial_review_inference_calls_reused={report['partial_review_inference_calls_reused']}")
    print(f"new_review_inference_calls={report['new_review_inference_calls']}")
    print(f"total_review_inference_calls={report['total_review_inference_calls']}")
    print(f"parsed_count={parsed}")
    print(f"solved_count={solved}")
    print(f"recovered_v4_failures={recovered}")
    print(f"regressed_v4_solves={regressions}")
    print(f"output={args.artifact_root / 'consumed-selection-development-v5-self-review-recovery.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
