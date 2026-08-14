"""Run V5 same-mind self-review over immutable V4 consumed-development drafts.

The runner performs no base-generation call. It verifies and reuses the frozen V4
assistant sidecars, gives each draft back only to the same candidate together with the
same solver-visible task material, performs exactly one review inference, and evaluates
only the reviewed final answer through the unchanged protected Docker evaluator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from .artifacts import CollectiveStage, ResourceUsage, StageArtifact
from .consumed_selection_development_v4_outcome_freeze import (
    V4_DEVELOPMENT_PROTOCOL_SHA256,
    V4_REMAINDER_OUTPUT_MANIFEST_SHA256,
    V4_REMAINDER_REPORT_SHA256,
    V4_SOFTWARE_REVISION,
    V4_TARGETED_OUTPUT_MANIFEST_SHA256,
    V4_TARGETED_REPORT_SHA256,
)
from .consumed_selection_development_v5_self_review import (
    DEVELOPMENT_PROTOCOL_SHA256_V5,
    TARGET_CANDIDATE_IDS_V5,
    TARGET_TASK_IDS_V5,
    build_self_review_prompt_v5,
    development_protocol_payload_v5,
    extract_reviewed_patch_v5,
)
from .content_store import FileContentStore
from .local_model_load_preflight import _run_load
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
    _verify_model_file,
    _verify_runtime_archives,
)
from .qualified_docker import probe_qualified_docker_configuration
from .repository_surgery import PatchFormat, RepositorySurgerySubmission
from .repository_surgery_calibration_matrix import _evaluate_patch
from .repository_surgery_selection_freeze_v1 import FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256
from .repository_surgery_selection_outcome_freeze_v1 import FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256
from .repository_surgery_selection_pack_v1 import selection_blueprints

REPORT_SCHEMA_V5 = "plural-cognition-consumed-selection-development-v5-self-review"
OUTPUT_MANIFEST_SCHEMA_V5 = "plural-cognition-consumed-selection-development-output-manifest-v5-self-review"
DEFAULT_TIMEOUT_SECONDS = 900


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _development_configuration_sha256(candidate_id: str) -> str:
    config_by_id = {item.candidate_id: item for item in FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.configs}
    final = config_by_id[candidate_id]
    return hashlib.sha256(
        _canonical_json_bytes(
            {
                "final_candidate_configuration_sha256": final.sha256,
                "development_protocol_sha256": DEVELOPMENT_PROTOCOL_SHA256_V5,
            }
        )
    ).hexdigest()


def _review_prompt(blueprint: Any, draft_output: bytes) -> bytes:
    raw = build_self_review_prompt_v5(blueprint, draft_output)
    if not raw.endswith(b"\n"):
        raise RuntimeError("development V5 review prompt builder no longer ends in one LF")
    prompt = raw[:-1]
    if prompt.endswith(b"\n"):
        raise RuntimeError("development V5 review prompt transport did not remove exactly one terminal LF")
    return prompt


def _load_report(root: Path, expected_sha256: str) -> dict[str, Any]:
    path = root / "consumed-selection-development-v4.json"
    if not path.is_file():
        raise ValueError(f"frozen V4 report missing: {path}")
    observed = _sha256_file(path)
    if observed != expected_sha256:
        raise ValueError(f"frozen V4 report drift: {path}: {observed}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "plural-cognition-consumed-selection-development-v4":
        raise ValueError(f"unexpected V4 report schema: {path}")
    if payload.get("scientific_status") != "development-only-consumed-split-not-selection-evidence":
        raise ValueError(f"unexpected V4 scientific status: {path}")
    if payload.get("software_revision") != V4_SOFTWARE_REVISION:
        raise ValueError(f"unexpected V4 software revision: {path}")
    if payload.get("development_protocol_sha256") != V4_DEVELOPMENT_PROTOCOL_SHA256:
        raise ValueError(f"unexpected V4 development protocol: {path}")
    return payload


def _load_manifest(root: Path, expected_sha256: str) -> dict[str, dict[str, Any]]:
    path = root / "output-channel-manifest.json"
    if not path.is_file():
        raise ValueError(f"frozen V4 output manifest missing: {path}")
    observed = _sha256_file(path)
    if observed != expected_sha256:
        raise ValueError(f"frozen V4 output manifest drift: {path}: {observed}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError(f"invalid V4 output manifest entries: {path}")
    return {str(item["path"]): item for item in entries}


def _load_frozen_v4_drafts(targeted_root: Path, remainder_root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    targeted = _load_report(targeted_root, V4_TARGETED_REPORT_SHA256)
    remainder = _load_report(remainder_root, V4_REMAINDER_REPORT_SHA256)
    targeted_manifest = _load_manifest(targeted_root, V4_TARGETED_OUTPUT_MANIFEST_SHA256)
    remainder_manifest = _load_manifest(remainder_root, V4_REMAINDER_OUTPUT_MANIFEST_SHA256)

    records: dict[tuple[str, str], dict[str, Any]] = {}
    for root, report, manifest in (
        (targeted_root, targeted, targeted_manifest),
        (remainder_root, remainder, remainder_manifest),
    ):
        for item in report.get("results", []):
            key = (str(item["candidate_id"]), str(item["task_id"]))
            if key in records:
                raise ValueError(f"duplicate frozen V4 candidate/task pair: {key}")
            prompt_sha256 = str(item["prompt_sha256"])
            sidecar = root / "llama-output" / key[0] / f"{prompt_sha256}.transcript.assistant.txt"
            if not sidecar.is_file():
                raise ValueError(f"frozen V4 assistant sidecar missing: {sidecar}")
            raw = sidecar.read_bytes()
            raw_sha256 = hashlib.sha256(raw).hexdigest()
            if raw_sha256 != item.get("raw_output_sha256"):
                raise ValueError(f"frozen V4 assistant sidecar hash mismatch: {sidecar}")
            relative = sidecar.relative_to(root).as_posix()
            manifest_item = manifest.get(relative)
            if manifest_item is None or manifest_item.get("sha256") != raw_sha256 or manifest_item.get("size_bytes") != len(raw):
                raise ValueError(f"frozen V4 assistant sidecar is not bound by output manifest: {sidecar}")
            records[key] = {
                "root": root,
                "result": item,
                "draft_output": raw,
                "draft_output_sha256": raw_sha256,
            }

    if len(records) != 48:
        raise ValueError(f"frozen V4 combined matrix must contain 48 unique pairs, found {len(records)}")
    return records


def _write_output_manifest(root: Path) -> None:
    entries: list[dict[str, Any]] = []
    output_root = root / "llama-output"
    if output_root.is_dir():
        for path in sorted(output_root.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_file():
                raw = path.read_bytes()
                entries.append({"path": path.relative_to(root).as_posix(), "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    payload = {
        "schema": OUTPUT_MANIFEST_SCHEMA_V5,
        "development_protocol_sha256": DEVELOPMENT_PROTOCOL_SHA256_V5,
        "consumed_selection_outcome_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256,
        "entries": entries,
    }
    (root / "output-channel-manifest.json").write_bytes(_canonical_json_bytes(payload))


def run_consumed_selection_development_v5_self_review(
    *,
    runtime_root: Path,
    model_root: Path,
    artifact_root: Path,
    selection_pack_path: Path,
    qualification_path: Path,
    v4_targeted_root: Path,
    v4_remainder_root: Path,
    software_revision: str,
    candidate_ids: Sequence[str] = TARGET_CANDIDATE_IDS_V5,
    task_ids: Sequence[str] = TARGET_TASK_IDS_V5,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    docker_executable: str = "docker",
) -> dict[str, Any]:
    if artifact_root.exists():
        raise ValueError(f"artifact_root already exists: {artifact_root}")
    if type(timeout_seconds) is not int or timeout_seconds < 1:
        raise ValueError("timeout_seconds must be a positive integer")
    candidate_ids = tuple(candidate_ids)
    task_ids = tuple(task_ids)
    if not candidate_ids or len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate_ids must be non-empty and unique")
    if not task_ids or len(task_ids) != len(set(task_ids)):
        raise ValueError("task_ids must be non-empty and unique")
    if set(candidate_ids) - set(TARGET_CANDIDATE_IDS_V5):
        raise ValueError("V5 review runner only supports the predeclared four non-Gemma candidates")

    all_blueprints = selection_blueprints()
    task_by_id = {item.task_id: item for item in all_blueprints}
    unknown_tasks = set(task_ids) - set(task_by_id)
    if unknown_tasks:
        raise ValueError(f"unknown consumed selection task ids: {sorted(unknown_tasks)}")
    blueprints = tuple(task_by_id[item] for item in task_ids)

    FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.validate_against()
    frozen_pack = _verify_frozen_artifacts(selection_pack_path, qualification_path)
    frozen_v4 = _load_frozen_v4_drafts(v4_targeted_root, v4_remainder_root)
    for candidate_id in candidate_ids:
        for task_id in task_ids:
            if (candidate_id, task_id) not in frozen_v4:
                raise ValueError(f"required frozen V4 draft pair is missing: {(candidate_id, task_id)}")

    _verify_runtime_archives(runtime_root)
    cli = runtime_root / "bin" / "llama-cli.exe"
    runtime_observation = _runtime_observation_resilient(cli)
    runtime_observation_bytes = _canonical_json_bytes(asdict(runtime_observation))
    runtime_observation_sha256 = hashlib.sha256(runtime_observation_bytes).hexdigest()
    for candidate_id in candidate_ids:
        candidate = LOCAL_MODEL_SOURCE_FREEZE_V2.candidate(candidate_id)
        _verify_model_file(model_root / candidate_id / candidate.filename, candidate)

    artifact_root.mkdir(parents=True)
    store = FileContentStore(artifact_root / "store")
    build_root = artifact_root / "build"
    build_root.mkdir()
    staging_root = artifact_root / "staging"
    output_root = artifact_root / "llama-output"
    configuration = probe_qualified_docker_configuration(software_revision=software_revision, docker_executable=docker_executable)
    all_materials = _materials(store=store, build_root=build_root, frozen_pack=frozen_pack)
    material_by_task = {item.blueprint.task_id: item for item in all_materials}
    (artifact_root / "runtime-observation.json").write_bytes(runtime_observation_bytes)
    (artifact_root / "development-protocol.json").write_bytes(_canonical_json_bytes(development_protocol_payload_v5()))

    config_by_id = {item.candidate_id: item for item in FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.configs}
    results: list[dict[str, Any]] = []
    for candidate_id in candidate_ids:
        source = LOCAL_MODEL_SOURCE_FREEZE_V2.candidate(candidate_id)
        final_config = config_by_id[candidate_id]
        development_config_sha256 = _development_configuration_sha256(candidate_id)
        model_path = model_root / candidate_id / source.filename
        for blueprint in blueprints:
            material = material_by_task[blueprint.task_id]
            frozen = frozen_v4[(candidate_id, blueprint.task_id)]
            draft_result = frozen["result"]
            draft_output = frozen["draft_output"]
            prompt = _review_prompt(blueprint, draft_output)
            prompt_sha256 = store.put_bytes(prompt)
            candidate_output_root = output_root / candidate_id
            candidate_output_root.mkdir(parents=True, exist_ok=True)
            capture = candidate_output_root / f"{prompt_sha256}.transcript.txt"
            command = _load_command(cli=cli, model_path=model_path, prompt=prompt, capture=capture)
            load, process_stdout, stderr = _run_load(command, timeout_seconds=timeout_seconds)
            if not capture.is_file():
                raise RuntimeError(f"development V5 transcript is missing: {capture}")
            transcript = capture.read_bytes()
            assistant, reasoning = extract_assistant_content_v6(transcript=transcript, prompt=prompt)
            capture.with_suffix(".process-stdout.bin").write_bytes(process_stdout)
            capture.with_suffix(".assistant.txt").write_bytes(assistant)
            reasoning_sha256: str | None = None
            if reasoning is not None:
                capture.with_suffix(".reasoning.txt").write_bytes(reasoning)
                reasoning_sha256 = hashlib.sha256(reasoning).hexdigest()

            input_tokens, output_tokens, token_counts_observed = _token_counts(stderr)
            resources = ResourceUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                inference_calls=1,
                wall_time_ms=max(0, round(load.elapsed_seconds * 1000)),
                accelerator_time_ms=max(0, round(load.elapsed_seconds * 1000)),
                peak_accelerator_bytes=load.peak_gpu_used_mib * 1024 * 1024,
                peak_ram_bytes=load.peak_process_rss_bytes or 0,
            )
            raw_output_sha256 = store.put_bytes(assistant)
            raw_stderr_sha256 = store.put_bytes(stderr)
            raw_artifact = StageArtifact(
                stage=CollectiveStage.RAW_MIND_OUTPUT,
                task=material.visible_task.task,
                run_id=f"consumed-development-v5-self-review:{candidate_id}:{blueprint.task_id}",
                producer_id=candidate_id,
                producer_configuration_sha256=development_config_sha256,
                protocol_sha256=DEVELOPMENT_PROTOCOL_SHA256_V5,
                software_revision=software_revision,
                content_sha256=raw_output_sha256,
                resources=resources,
            )
            if store.put_bytes(raw_artifact.canonical_bytes()) != raw_artifact.sha256:
                raise AssertionError("development V5 raw artifact storage identity mismatch")

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
                    "schema": "plural-cognition-consumed-selection-development-invalid-v5-self-review",
                    "candidate_id": candidate_id,
                    "task_id": blueprint.task_id,
                    "raw_artifact_sha256": raw_artifact.sha256,
                    "parse_error": parse_error,
                }
                evaluation_sha256 = store.put_bytes(_canonical_json_bytes(invalid))
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
                    raise AssertionError("development V5 submission storage identity mismatch")
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
                    raise AssertionError("development V5 evaluation storage identity mismatch")
                exact_accuracy = _metric(evaluation, "exact_accuracy")
                evaluator_valid_rate = _metric(evaluation, "valid_rate")
                solved = bool(evaluation.qualified)

            results.append(
                {
                    "candidate_id": candidate_id,
                    "task_id": blueprint.task_id,
                    "task_sha256": material.visible_task.sha256,
                    "draft_reused_from_v4": True,
                    "draft_prompt_sha256": draft_result["prompt_sha256"],
                    "draft_raw_output_sha256": frozen["draft_output_sha256"],
                    "draft_parse_valid": bool(draft_result["parse_valid"]),
                    "draft_solved": bool(draft_result["solved"]),
                    "review_prompt_sha256": prompt_sha256,
                    "final_candidate_configuration_sha256": final_config.sha256,
                    "development_configuration_sha256": development_config_sha256,
                    "raw_artifact_sha256": raw_artifact.sha256,
                    "raw_output_sha256": raw_output_sha256,
                    "output_changed_from_draft": raw_output_sha256 != frozen["draft_output_sha256"],
                    "transcript_sha256": hashlib.sha256(transcript).hexdigest(),
                    "raw_stderr_sha256": raw_stderr_sha256,
                    "reasoning_sha256": reasoning_sha256,
                    "parse_valid": parse_valid,
                    "parse_mode": parse_mode,
                    "parse_error": parse_error,
                    "patch_sha256": patch_sha256,
                    "submission_sha256": submission_sha256,
                    "evaluation_sha256": evaluation_sha256,
                    "exact_accuracy": exact_accuracy,
                    "evaluator_valid_rate": evaluator_valid_rate,
                    "solved": solved,
                    "token_counts_observed": token_counts_observed,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "review_inference_calls": 1,
                    "base_generation_inference_calls": 0,
                    "elapsed_seconds": load.elapsed_seconds,
                    "baseline_gpu_used_mib": load.baseline_gpu_used_mib,
                    "peak_gpu_used_mib": load.peak_gpu_used_mib,
                    "peak_process_rss_bytes": load.peak_process_rss_bytes,
                    "offloaded_layers": load.offloaded_layers,
                    "total_layers": load.total_layers,
                }
            )

    if staging_root.exists() and any(staging_root.iterdir()):
        raise RuntimeError("consumed selection development V5 left Docker staging residue")
    report = {
        "schema": REPORT_SCHEMA_V5,
        "scientific_status": "development-only-consumed-split-self-review-not-selection-evidence",
        "software_revision": software_revision,
        "development_protocol_sha256": DEVELOPMENT_PROTOCOL_SHA256_V5,
        "consumed_selection_outcome_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256,
        "selection_pack_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256,
        "operational_config_freeze_sha256": FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.sha256,
        "runtime_observation_sha256": runtime_observation_sha256,
        "v4_targeted_report_sha256": V4_TARGETED_REPORT_SHA256,
        "v4_remainder_report_sha256": V4_REMAINDER_REPORT_SHA256,
        "base_generation_reused": True,
        "new_inference_calls": len(results),
        "candidate_ids": list(candidate_ids),
        "task_ids": list(task_ids),
        "result_count": len(results),
        "results": results,
    }
    report_bytes = _canonical_json_bytes(report)
    (artifact_root / "consumed-selection-development-v5-self-review.json").write_bytes(report_bytes)
    _write_output_manifest(artifact_root)
    report["report_sha256"] = hashlib.sha256(report_bytes).hexdigest()
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run V5 same-mind review over frozen V4 consumed-development drafts.")
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--selection-pack", required=True, type=Path)
    parser.add_argument("--qualification-report", required=True, type=Path)
    parser.add_argument("--v4-targeted-root", required=True, type=Path)
    parser.add_argument("--v4-remainder-root", required=True, type=Path)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--candidate", action="append", choices=TARGET_CANDIDATE_IDS_V5)
    parser.add_argument("--task", action="append")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--docker-executable", default="docker")
    args = parser.parse_args(argv)
    try:
        report = run_consumed_selection_development_v5_self_review(
            runtime_root=args.runtime_root,
            model_root=args.model_root,
            artifact_root=args.artifact_root,
            selection_pack_path=args.selection_pack,
            qualification_path=args.qualification_report,
            v4_targeted_root=args.v4_targeted_root,
            v4_remainder_root=args.v4_remainder_root,
            software_revision=args.software_revision,
            candidate_ids=tuple(args.candidate) if args.candidate else TARGET_CANDIDATE_IDS_V5,
            task_ids=tuple(args.task) if args.task else TARGET_TASK_IDS_V5,
            timeout_seconds=args.timeout_seconds,
            docker_executable=args.docker_executable,
        )
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"status=CONSUMED_SELECTION_DEVELOPMENT_V5_SELF_REVIEW_FAIL\nerror={exc}")
        return 2
    parsed = sum(1 for item in report["results"] if item["parse_valid"])
    solved = sum(1 for item in report["results"] if item["solved"])
    print("status=CONSUMED_SELECTION_DEVELOPMENT_V5_SELF_REVIEW_PASS")
    print(f"report_sha256={report['report_sha256']}")
    print(f"development_protocol_sha256={report['development_protocol_sha256']}")
    print(f"candidate_count={len(report['candidate_ids'])}")
    print(f"task_count={len(report['task_ids'])}")
    print(f"result_count={report['result_count']}")
    print(f"new_inference_calls={report['new_inference_calls']}")
    print(f"parsed_count={parsed}")
    print(f"solved_count={solved}")
    print(f"output={args.artifact_root / 'consumed-selection-development-v5-self-review.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
