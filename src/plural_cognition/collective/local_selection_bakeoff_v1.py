"""Execute the frozen five-candidate Repository Surgery selection bakeoff.

This is the first candidate-model execution on the target-qualified selection
pack.  It does not construct or tune selection tasks.  Before inference it
verifies the immutable selection-pack/qualification artifacts, regenerates the
content-bound visible materials from the frozen source revision, writes the
complete BakeoffPlan, and then executes the exact final local operational
configuration once per candidate/task pair.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
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
from .content_store import FileContentStore
from .local_model_load_preflight import (
    _run_load,
    _verify_model_file,
    _verify_runtime_archives,
)
from .local_models import LOCAL_MODEL_SOURCE_FREEZE_V2
from .local_operational_freeze_v1 import (
    FINAL_CANDIDATE_IDS,
    FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1,
    FINAL_RAW_MIND_PROTOCOL,
    FINAL_RESOURCE_BUDGET_SHA256,
)
from .local_raw_calibration import validate_patch_against_blueprint
from .local_raw_calibration_v2 import _runtime_observation_resilient
from .local_raw_calibration_v6 import extract_assistant_content_v6
from .local_raw_calibration_v8 import build_solver_prompt_v8, extract_structured_edit_patch
from .qualified_docker import probe_qualified_docker_configuration
from .repository_surgery import PatchFormat, RepositorySurgerySubmission
from .repository_surgery_calibration_matrix import _evaluate_patch, _metric
from .repository_surgery_selection_freeze_v1 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_V1,
    FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256,
)
from .repository_surgery_selection_pack_v1 import (
    SelectionMaterial,
    build_selection_material,
    selection_blueprints,
)

SELECTION_BAKEOFF_REPORT_SCHEMA = "plural-cognition-local-selection-bakeoff-v1"
SELECTION_INVALID_RESULT_SCHEMA = "plural-cognition-selection-invalid-candidate-output-v1"
SELECTION_OUTPUT_MANIFEST_SCHEMA = "plural-cognition-selection-output-channel-manifest-v1"
DEFAULT_TIMEOUT_SECONDS = 900
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _quantization_label(candidate_id: str) -> str:
    labels = {
        "qwen3-8b-q8": "Q8_0",
        "qwen2.5-coder-14b-q5km": "Q5_K_M",
        "gemma4-12b-it-qat-q4": "QAT-Q4",
        "devstral-24b-q4km": "Q4_K_M",
        "deepseek-coder-v2-lite-q5km": "Q5_K_M",
    }
    return labels[candidate_id]


def _candidate_models() -> tuple[CandidateModel, ...]:
    freeze = LOCAL_MODEL_SOURCE_FREEZE_V2
    config_by_id = {
        item.candidate_id: item for item in FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.configs
    }
    return tuple(
        CandidateModel(
            candidate_id=candidate_id,
            mind=config_by_id[candidate_id].mind_identity(),
            deployment_class=DeploymentClass.LOCAL,
            architecture_class=freeze.candidate(candidate_id).source_repository,
            context_tokens=FINAL_RAW_MIND_PROTOCOL.context_tokens,
            quantization=_quantization_label(candidate_id),
        )
        for candidate_id in FINAL_CANDIDATE_IDS
    )


def _solver_prompt(blueprint: Any) -> bytes:
    raw = build_solver_prompt_v8(blueprint)
    if not raw.endswith(b"\n"):
        raise RuntimeError("frozen V8 prompt builder no longer ends in one LF")
    prompt = raw[:-1]
    if prompt.endswith(b"\n"):
        raise RuntimeError("frozen V4 prompt transport did not remove exactly one terminal LF")
    return prompt


def _load_command(
    *, cli: Path, model_path: Path, prompt: bytes, capture: Path
) -> tuple[str, ...]:
    p = FINAL_RAW_MIND_PROTOCOL
    return (
        str(cli),
        "-m", str(model_path),
        "-c", str(p.context_tokens),
        "-n", str(p.predict_tokens),
        "-ngl", p.gpu_layers,
        "-dev", p.device,
        "-fit", p.fit,
        "-sm", p.split_mode,
        "-mg", str(p.main_gpu),
        "-ctk", p.cache_type_k,
        "-ctv", p.cache_type_v,
        "-lm", p.load_mode,
        "--offline",
        "--temp", str(p.temperature),
        "--seed", str(p.seed),
        "-t", str(p.cpu_threads),
        "-tb", str(p.cpu_threads_batch),
        "-b", str(p.batch_tokens),
        "-ub", str(p.microbatch_tokens),
        "-fa", p.flash_attention_mode,
        "-cnv",
        "--simple-io",
        "--output-file", str(capture),
        "--no-escape",
        "--no-display-prompt",
        "--log-colors", "off",
        "--no-log-timestamps",
        "--log-verbosity", str(p.log_verbosity),
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


def _verify_frozen_artifacts(selection_pack_path: Path, qualification_path: Path) -> dict[str, Any]:
    freeze = FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_V1
    if not selection_pack_path.is_file() or not qualification_path.is_file():
        raise RuntimeError("frozen selection-pack or qualification artifact is missing")
    if _sha256_file(selection_pack_path) != freeze.selection_pack_sha256:
        raise RuntimeError("frozen selection-pack artifact SHA-256 drifted")
    if _sha256_file(qualification_path) != freeze.qualification_report_sha256:
        raise RuntimeError("frozen selection qualification artifact SHA-256 drifted")
    pack = json.loads(selection_pack_path.read_text(encoding="ascii"))
    qualification = json.loads(qualification_path.read_text(encoding="ascii"))
    if pack.get("operational_config_freeze_sha256") != freeze.operational_config_freeze_sha256:
        raise RuntimeError("selection pack operational freeze binding drifted")
    if qualification.get("selection_pack_sha256") != freeze.selection_pack_sha256:
        raise RuntimeError("selection qualification no longer binds frozen pack")
    if qualification.get("qualified_docker_report_sha256") != freeze.qualified_docker_report_sha256:
        raise RuntimeError("selection qualification Docker identity drifted")
    return pack


def _materials(
    *, store: FileContentStore, build_root: Path, frozen_pack: dict[str, Any]
) -> tuple[SelectionMaterial, ...]:
    freeze = FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_V1
    expected = {item["task_id"]: item for item in frozen_pack["tasks"]}
    materials: list[SelectionMaterial] = []
    for blueprint in selection_blueprints():
        material = build_selection_material(
            blueprint=blueprint,
            store=store,
            work_root=build_root / blueprint.task_id,
            software_revision=freeze.source_revision,
        )
        entry = expected.get(blueprint.task_id)
        if entry is None:
            raise RuntimeError(f"frozen pack lacks task: {blueprint.task_id}")
        actual = {
            "task_sha256": material.visible_task.sha256,
            "generation_record_sha256": material.generation_record.sha256,
            "evaluation_plan_sha256": material.evaluation_plan.sha256,
        }
        for key, value in actual.items():
            if entry.get(key) != value:
                raise RuntimeError(f"frozen selection material drifted for {blueprint.task_id}: {key}")
        materials.append(material)
    if len(materials) != freeze.task_count or len(expected) != freeze.task_count:
        raise RuntimeError("frozen selection material count drifted")
    return tuple(materials)


def _plan(materials: Sequence[SelectionMaterial]) -> BakeoffPlan:
    return BakeoffPlan(
        tasks=tuple(item.visible_task.task for item in materials),
        candidates=_candidate_models(),
        raw_protocol_sha256=FINAL_RAW_MIND_PROTOCOL.sha256,
        resource_budget_sha256=FINAL_RESOURCE_BUDGET_SHA256,
        min_valid_rate=0.95,
        population_size=4,
        require_strongest_member=True,
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


@dataclass(frozen=True, slots=True)
class LocalSelectionTaskObservation:
    candidate_id: str
    task_id: str
    task_sha256: str
    prompt_sha256: str
    producer_configuration_sha256: str
    raw_artifact_sha256: str
    raw_output_sha256: str
    transcript_sha256: str
    raw_stderr_sha256: str
    reasoning_sha256: str | None
    parse_valid: bool
    parse_mode: str | None
    parse_error: str | None
    patch_sha256: str | None
    submission_sha256: str | None
    evaluation_sha256: str
    exact_accuracy: float
    evaluator_valid_rate: float
    solved: bool
    token_counts_observed: bool
    input_tokens: int
    output_tokens: int
    elapsed_seconds: float
    baseline_gpu_used_mib: int
    peak_gpu_used_mib: int
    peak_process_rss_bytes: int | None
    offloaded_layers: int
    total_layers: int

    def canonical_payload(self) -> dict[str, Any]:
        return asdict(self)


def _write_output_manifest(root: Path) -> None:
    output_root = root / "llama-output"
    entries: list[dict[str, Any]] = []
    if output_root.is_dir():
        for path in sorted(output_root.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_file():
                raw = path.read_bytes()
                entries.append({
                    "path": path.relative_to(root).as_posix(),
                    "size_bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                })
    payload = {
        "schema": SELECTION_OUTPUT_MANIFEST_SCHEMA,
        "selection_pack_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256,
        "entries": entries,
    }
    (root / "output-channel-manifest.json").write_bytes(_canonical_json_bytes(payload))


def run_selection_bakeoff(
    *,
    runtime_root: Path,
    model_root: Path,
    artifact_root: Path,
    selection_pack_path: Path,
    qualification_path: Path,
    software_revision: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    docker_executable: str = "docker",
) -> dict[str, Any]:
    if artifact_root.exists():
        raise ValueError(f"artifact_root already exists: {artifact_root}")
    if type(timeout_seconds) is not int or timeout_seconds < 1:
        raise ValueError("timeout_seconds must be a positive integer")
    FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.validate_against()
    FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_V1.validate_against_repository()
    frozen_pack = _verify_frozen_artifacts(selection_pack_path, qualification_path)

    _verify_runtime_archives(runtime_root)
    cli = runtime_root / "bin" / "llama-cli.exe"
    runtime_observation = _runtime_observation_resilient(cli)
    runtime_observation_bytes = _canonical_json_bytes(asdict(runtime_observation))
    runtime_observation_sha256 = hashlib.sha256(runtime_observation_bytes).hexdigest()
    for candidate_id in FINAL_CANDIDATE_IDS:
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
    materials = _materials(store=store, build_root=build_root, frozen_pack=frozen_pack)
    plan = _plan(materials)
    (artifact_root / "runtime-observation.json").write_bytes(runtime_observation_bytes)
    (artifact_root / "bakeoff-plan.json").write_bytes(plan.canonical_bytes())

    config_by_id = {
        item.candidate_id: item for item in FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.configs
    }
    observations: list[LocalSelectionTaskObservation] = []
    selection_results: list[CandidateTaskResult] = []
    material_by_task = {item.blueprint.task_id: item for item in materials}

    for candidate_id in FINAL_CANDIDATE_IDS:
        source = LOCAL_MODEL_SOURCE_FREEZE_V2.candidate(candidate_id)
        config = config_by_id[candidate_id]
        model_path = model_root / candidate_id / source.filename
        for blueprint in selection_blueprints():
            material = material_by_task[blueprint.task_id]
            prompt = _solver_prompt(blueprint)
            prompt_sha256 = store.put_bytes(prompt)
            candidate_output_root = output_root / candidate_id
            candidate_output_root.mkdir(parents=True, exist_ok=True)
            capture = candidate_output_root / f"{prompt_sha256}.transcript.txt"
            if capture.exists():
                raise RuntimeError(f"selection transcript already exists: {capture}")
            command = _load_command(cli=cli, model_path=model_path, prompt=prompt, capture=capture)
            load, process_stdout, stderr = _run_load(command, timeout_seconds=timeout_seconds)
            if not capture.is_file():
                raise RuntimeError(f"llama selection transcript is missing: {capture}")
            transcript = capture.read_bytes()
            assistant, reasoning = extract_assistant_content_v6(transcript=transcript, prompt=prompt)
            process_stdout_path = capture.with_suffix(".process-stdout.bin")
            assistant_path = capture.with_suffix(".assistant.txt")
            process_stdout_path.write_bytes(process_stdout)
            assistant_path.write_bytes(assistant)
            reasoning_sha256: str | None = None
            if reasoning is not None:
                reasoning_path = capture.with_suffix(".reasoning.txt")
                reasoning_path.write_bytes(reasoning)
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
                run_id=f"selection:{candidate_id}:{blueprint.task_id}",
                producer_id=candidate_id,
                producer_configuration_sha256=config.sha256,
                protocol_sha256=FINAL_RAW_MIND_PROTOCOL.sha256,
                software_revision=software_revision,
                content_sha256=raw_output_sha256,
                resources=resources,
            )
            if store.put_bytes(raw_artifact.canonical_bytes()) != raw_artifact.sha256:
                raise AssertionError("selection raw artifact storage identity mismatch")

            parse_valid = False
            parse_mode: str | None = None
            parse_error: str | None = None
            patch_sha256: str | None = None
            submission_sha256: str | None = None
            exact_accuracy = 0.0
            evaluator_valid_rate = 0.0
            solved = False
            evaluation_sha256: str
            try:
                patch, parse_mode = extract_structured_edit_patch(assistant)
                validate_patch_against_blueprint(patch, blueprint)
            except ValueError as exc:
                parse_error = str(exc)
                invalid = {
                    "schema": SELECTION_INVALID_RESULT_SCHEMA,
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
                    raise AssertionError("selection submission storage identity mismatch")
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
                    raise AssertionError("selection evaluation storage identity mismatch")
                exact_accuracy = _metric(evaluation, "exact_accuracy")
                evaluator_valid_rate = _metric(evaluation, "valid_rate")
                solved = bool(evaluation.qualified)

            selection_results.append(CandidateTaskResult(
                candidate_id=candidate_id,
                task=material.visible_task.task,
                valid=parse_valid,
                passed=solved,
                raw_artifact_sha256=raw_artifact.sha256,
                evaluation_sha256=evaluation_sha256,
                resources=resources,
            ))
            observations.append(LocalSelectionTaskObservation(
                candidate_id=candidate_id,
                task_id=blueprint.task_id,
                task_sha256=material.visible_task.sha256,
                prompt_sha256=prompt_sha256,
                producer_configuration_sha256=config.sha256,
                raw_artifact_sha256=raw_artifact.sha256,
                raw_output_sha256=raw_output_sha256,
                transcript_sha256=hashlib.sha256(transcript).hexdigest(),
                raw_stderr_sha256=raw_stderr_sha256,
                reasoning_sha256=reasoning_sha256,
                parse_valid=parse_valid,
                parse_mode=parse_mode,
                parse_error=parse_error,
                patch_sha256=patch_sha256,
                submission_sha256=submission_sha256,
                evaluation_sha256=evaluation_sha256,
                exact_accuracy=exact_accuracy,
                evaluator_valid_rate=evaluator_valid_rate,
                solved=solved,
                token_counts_observed=token_counts_observed,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                elapsed_seconds=load.elapsed_seconds,
                baseline_gpu_used_mib=load.baseline_gpu_used_mib,
                peak_gpu_used_mib=load.peak_gpu_used_mib,
                peak_process_rss_bytes=load.peak_process_rss_bytes,
                offloaded_layers=load.offloaded_layers,
                total_layers=load.total_layers,
            ))

    if staging_root.exists() and any(staging_root.iterdir()):
        raise RuntimeError("selection bakeoff left Docker staging residue")
    selection = select_population(plan, selection_results)
    report = {
        "schema": SELECTION_BAKEOFF_REPORT_SCHEMA,
        "software_revision": software_revision,
        "selection_pack_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256,
        "selection_pack_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_V1.selection_pack_sha256,
        "qualification_report_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_V1.qualification_report_sha256,
        "operational_config_freeze_sha256": FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.sha256,
        "runtime_observation_sha256": runtime_observation_sha256,
        "bakeoff_plan_sha256": plan.sha256,
        "bakeoff_plan": plan.canonical_payload(),
        "result_count": len(observations),
        "results": [item.canonical_payload() for item in observations],
        "population_selection": _population_payload(selection),
    }
    report_bytes = _canonical_json_bytes(report)
    (artifact_root / "selection-bakeoff.json").write_bytes(report_bytes)
    _write_output_manifest(artifact_root)
    report["report_sha256"] = hashlib.sha256(report_bytes).hexdigest()
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Execute the frozen five-candidate selection bakeoff.")
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--selection-pack", required=True, type=Path)
    parser.add_argument("--qualification-report", required=True, type=Path)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--docker-executable", default="docker")
    args = parser.parse_args(argv)
    try:
        report = run_selection_bakeoff(
            runtime_root=args.runtime_root,
            model_root=args.model_root,
            artifact_root=args.artifact_root,
            selection_pack_path=args.selection_pack,
            qualification_path=args.qualification_report,
            software_revision=args.software_revision,
            timeout_seconds=args.timeout_seconds,
            docker_executable=args.docker_executable,
        )
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"status=SELECTION_BAKEOFF_FAIL\nerror={exc}")
        return 2

    selection = report["population_selection"]
    print("status=SELECTION_BAKEOFF_PASS")
    print(f"report_sha256={report['report_sha256']}")
    print(f"bakeoff_plan_sha256={report['bakeoff_plan_sha256']}")
    print(f"selection_pack_freeze_sha256={report['selection_pack_freeze_sha256']}")
    print(f"result_count={report['result_count']}")
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
    print(f"output={args.artifact_root / 'selection-bakeoff.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
