"""Run development-only V2 line-span protocol on the consumed V1 selection split.

This runner is explicitly not a population-selection experiment. It reuses the consumed
V1 tasks only to measure whether a changed candidate serialization/anchoring protocol
removes observed invalid-output failures. Protected evaluation remains unchanged.
Any later selection claim requires a fresh untouched selection pack.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from .artifacts import CollectiveStage, ResourceUsage, StageArtifact
from .consumed_selection_development_v2 import (
    DEVELOPMENT_PROTOCOL_SHA256_V2,
    build_solver_prompt_v2,
    development_protocol_payload_v2,
    extract_line_span_patch,
)
from .content_store import FileContentStore
from .local_model_load_preflight import _run_load
from .local_models import LOCAL_MODEL_SOURCE_FREEZE_V2
from .local_operational_freeze_v1 import (
    FINAL_CANDIDATE_IDS,
    FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1,
)
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
from .repository_surgery_selection_freeze_v1 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256,
)
from .repository_surgery_selection_outcome_freeze_v1 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256,
)
from .repository_surgery_selection_pack_v1 import selection_blueprints

REPORT_SCHEMA = "plural-cognition-consumed-selection-development-v2"
OUTPUT_MANIFEST_SCHEMA = "plural-cognition-consumed-selection-development-output-manifest-v2"
DEFAULT_TIMEOUT_SECONDS = 900


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _development_configuration_sha256(candidate_id: str) -> str:
    final = FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.config(candidate_id)
    return hashlib.sha256(
        _canonical_json_bytes(
            {
                "final_candidate_configuration_sha256": final.sha256,
                "development_protocol_sha256": DEVELOPMENT_PROTOCOL_SHA256_V2,
            }
        )
    ).hexdigest()


def _solver_prompt(blueprint: Any) -> bytes:
    raw = build_solver_prompt_v2(blueprint)
    if not raw.endswith(b"\n"):
        raise RuntimeError("development prompt builder no longer ends in one LF")
    prompt = raw[:-1]
    if prompt.endswith(b"\n"):
        raise RuntimeError("development prompt transport did not remove exactly one terminal LF")
    return prompt


def _write_output_manifest(root: Path) -> None:
    entries: list[dict[str, Any]] = []
    output_root = root / "llama-output"
    if output_root.is_dir():
        for path in sorted(output_root.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_file():
                raw = path.read_bytes()
                entries.append(
                    {
                        "path": path.relative_to(root).as_posix(),
                        "size_bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    }
                )
    payload = {
        "schema": OUTPUT_MANIFEST_SCHEMA,
        "development_protocol_sha256": DEVELOPMENT_PROTOCOL_SHA256_V2,
        "consumed_selection_outcome_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256,
        "entries": entries,
    }
    (root / "output-channel-manifest.json").write_bytes(_canonical_json_bytes(payload))


def run_consumed_selection_development(
    *,
    runtime_root: Path,
    model_root: Path,
    artifact_root: Path,
    selection_pack_path: Path,
    qualification_path: Path,
    software_revision: str,
    candidate_ids: Sequence[str] = FINAL_CANDIDATE_IDS,
    task_ids: Sequence[str] | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    docker_executable: str = "docker",
) -> dict[str, Any]:
    if artifact_root.exists():
        raise ValueError(f"artifact_root already exists: {artifact_root}")
    if type(timeout_seconds) is not int or timeout_seconds < 1:
        raise ValueError("timeout_seconds must be a positive integer")
    candidate_ids = tuple(candidate_ids)
    if not candidate_ids or len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate_ids must be non-empty and unique")
    unknown_candidates = set(candidate_ids) - set(FINAL_CANDIDATE_IDS)
    if unknown_candidates:
        raise ValueError(f"unknown frozen candidate ids: {sorted(unknown_candidates)}")

    all_blueprints = selection_blueprints()
    task_by_id = {item.task_id: item for item in all_blueprints}
    selected_task_ids = tuple(task_by_id) if task_ids is None else tuple(task_ids)
    if not selected_task_ids or len(selected_task_ids) != len(set(selected_task_ids)):
        raise ValueError("task_ids must be non-empty and unique")
    unknown_tasks = set(selected_task_ids) - set(task_by_id)
    if unknown_tasks:
        raise ValueError(f"unknown consumed selection task ids: {sorted(unknown_tasks)}")
    blueprints = tuple(task_by_id[item] for item in selected_task_ids)

    FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.validate_against()
    frozen_pack = _verify_frozen_artifacts(selection_pack_path, qualification_path)
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
    configuration = probe_qualified_docker_configuration(
        software_revision=software_revision,
        docker_executable=docker_executable,
    )
    all_materials = _materials(store=store, build_root=build_root, frozen_pack=frozen_pack)
    material_by_task = {item.blueprint.task_id: item for item in all_materials}
    (artifact_root / "runtime-observation.json").write_bytes(runtime_observation_bytes)
    (artifact_root / "development-protocol.json").write_bytes(
        _canonical_json_bytes(development_protocol_payload_v2())
    )

    config_by_id = {
        item.candidate_id: item for item in FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.configs
    }
    results: list[dict[str, Any]] = []
    for candidate_id in candidate_ids:
        source = LOCAL_MODEL_SOURCE_FREEZE_V2.candidate(candidate_id)
        final_config = config_by_id[candidate_id]
        development_config_sha256 = _development_configuration_sha256(candidate_id)
        model_path = model_root / candidate_id / source.filename
        for blueprint in blueprints:
            material = material_by_task[blueprint.task_id]
            prompt = _solver_prompt(blueprint)
            prompt_sha256 = store.put_bytes(prompt)
            candidate_output_root = output_root / candidate_id
            candidate_output_root.mkdir(parents=True, exist_ok=True)
            capture = candidate_output_root / f"{prompt_sha256}.transcript.txt"
            command = _load_command(cli=cli, model_path=model_path, prompt=prompt, capture=capture)
            load, process_stdout, stderr = _run_load(command, timeout_seconds=timeout_seconds)
            if not capture.is_file():
                raise RuntimeError(f"development transcript is missing: {capture}")
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
                run_id=f"consumed-development-v2:{candidate_id}:{blueprint.task_id}",
                producer_id=candidate_id,
                producer_configuration_sha256=development_config_sha256,
                protocol_sha256=DEVELOPMENT_PROTOCOL_SHA256_V2,
                software_revision=software_revision,
                content_sha256=raw_output_sha256,
                resources=resources,
            )
            if store.put_bytes(raw_artifact.canonical_bytes()) != raw_artifact.sha256:
                raise AssertionError("development raw artifact storage identity mismatch")

            parse_valid = False
            parse_mode: str | None = None
            parse_error: str | None = None
            patch_sha256: str | None = None
            submission_sha256: str | None = None
            exact_accuracy = 0.0
            evaluator_valid_rate = 0.0
            solved = False
            try:
                patch, parse_mode = extract_line_span_patch(assistant, blueprint)
                validate_patch_against_blueprint(patch, blueprint)
            except ValueError as exc:
                parse_error = str(exc)
                invalid = {
                    "schema": "plural-cognition-consumed-selection-development-invalid-v2",
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
                    raise AssertionError("development submission storage identity mismatch")
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
                    raise AssertionError("development evaluation storage identity mismatch")
                exact_accuracy = _metric(evaluation, "exact_accuracy")
                evaluator_valid_rate = _metric(evaluation, "valid_rate")
                solved = bool(evaluation.qualified)

            results.append(
                {
                    "candidate_id": candidate_id,
                    "task_id": blueprint.task_id,
                    "task_sha256": material.visible_task.sha256,
                    "prompt_sha256": prompt_sha256,
                    "final_candidate_configuration_sha256": final_config.sha256,
                    "development_configuration_sha256": development_config_sha256,
                    "raw_artifact_sha256": raw_artifact.sha256,
                    "raw_output_sha256": raw_output_sha256,
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
                    "elapsed_seconds": load.elapsed_seconds,
                    "baseline_gpu_used_mib": load.baseline_gpu_used_mib,
                    "peak_gpu_used_mib": load.peak_gpu_used_mib,
                    "peak_process_rss_bytes": load.peak_process_rss_bytes,
                    "offloaded_layers": load.offloaded_layers,
                    "total_layers": load.total_layers,
                }
            )

    if staging_root.exists() and any(staging_root.iterdir()):
        raise RuntimeError("consumed selection development left Docker staging residue")
    report = {
        "schema": REPORT_SCHEMA,
        "scientific_status": "development-only-consumed-split-not-selection-evidence",
        "software_revision": software_revision,
        "development_protocol_sha256": DEVELOPMENT_PROTOCOL_SHA256_V2,
        "consumed_selection_outcome_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256,
        "selection_pack_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256,
        "operational_config_freeze_sha256": FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.sha256,
        "runtime_observation_sha256": runtime_observation_sha256,
        "candidate_ids": list(candidate_ids),
        "task_ids": list(selected_task_ids),
        "result_count": len(results),
        "results": results,
    }
    report_bytes = _canonical_json_bytes(report)
    (artifact_root / "consumed-selection-development-v2.json").write_bytes(report_bytes)
    _write_output_manifest(artifact_root)
    report["report_sha256"] = hashlib.sha256(report_bytes).hexdigest()
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run V2 line-span development on the consumed V1 selection split.")
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--selection-pack", required=True, type=Path)
    parser.add_argument("--qualification-report", required=True, type=Path)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--candidate", action="append", choices=FINAL_CANDIDATE_IDS)
    parser.add_argument("--task", action="append")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--docker-executable", default="docker")
    args = parser.parse_args(argv)
    try:
        report = run_consumed_selection_development(
            runtime_root=args.runtime_root,
            model_root=args.model_root,
            artifact_root=args.artifact_root,
            selection_pack_path=args.selection_pack,
            qualification_path=args.qualification_report,
            software_revision=args.software_revision,
            candidate_ids=tuple(args.candidate) if args.candidate else FINAL_CANDIDATE_IDS,
            task_ids=tuple(args.task) if args.task else None,
            timeout_seconds=args.timeout_seconds,
            docker_executable=args.docker_executable,
        )
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"status=CONSUMED_SELECTION_DEVELOPMENT_V2_FAIL\nerror={exc}")
        return 2
    parsed = sum(1 for item in report["results"] if item["parse_valid"])
    solved = sum(1 for item in report["results"] if item["solved"])
    print("status=CONSUMED_SELECTION_DEVELOPMENT_V2_PASS")
    print(f"report_sha256={report['report_sha256']}")
    print(f"development_protocol_sha256={report['development_protocol_sha256']}")
    print(f"candidate_count={len(report['candidate_ids'])}")
    print(f"task_count={len(report['task_ids'])}")
    print(f"result_count={report['result_count']}")
    print(f"parsed_count={parsed}")
    print(f"solved_count={solved}")
    print(f"output={args.artifact_root / 'consumed-selection-development-v2.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
