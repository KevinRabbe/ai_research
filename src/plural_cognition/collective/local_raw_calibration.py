"""Calibration-only raw local-model Repository Surgery measurement.

This module intentionally operates only on the existing project-authored
Repository Surgery calibration matrix.  It does not construct or inspect
selection/confirmation tasks and it does not instantiate the final operational
configuration freeze.

Model-generated patches are never executed on the ordinary host.  A parsed
patch is evaluated only through the already-qualified Docker runner and the
privileged black-box calibration evaluator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

from .artifacts import CollectiveStage, ResourceUsage, StageArtifact
from .content_store import FileContentStore
from .local_model_load_preflight import (
    _run_load,
    _runtime_observation,
    _verify_model_file,
    _verify_runtime_archives,
)
from .local_models import LOCAL_MODEL_SOURCE_FREEZE_V2, FrozenModelSource
from .qualified_docker import probe_qualified_docker_configuration
from .repository_surgery import PatchFormat, RepositorySurgerySubmission
from .repository_surgery_calibration_matrix import (
    CalibrationBlueprint,
    _evaluate_patch,
    _metric,
    build_matrix_material,
    calibration_blueprints,
)

CALIBRATION_SCHEMA = "plural-cognition-local-raw-capability-calibration-v1"
CALIBRATION_PROTOCOL_SCHEMA = "plural-cognition-local-raw-calibration-protocol-v1"
CALIBRATION_CONTEXT_TOKENS = 4096
CALIBRATION_PREDICT_TOKENS = 2048
CALIBRATION_TIMEOUT_SECONDS = 600
CALIBRATION_LOG_VERBOSITY = 4
MAX_PATCH_BYTES = 65_536


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_json(payload: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def calibration_protocol_payload() -> dict[str, Any]:
    """Return the provisional calibration protocol identity.

    These settings are deliberately not the final selection configuration.
    Calibration evidence may justify changing them before the operational
    configuration freeze is instantiated.
    """

    return {
        "schema": CALIBRATION_PROTOCOL_SCHEMA,
        "task_split": "calibration-only",
        "context_tokens": CALIBRATION_CONTEXT_TOKENS,
        "predict_tokens": CALIBRATION_PREDICT_TOKENS,
        "gpu_layers": "all",
        "device": "CUDA0",
        "fit": "off",
        "split_mode": "none",
        "main_gpu": 0,
        "cache_type_k": "f16",
        "cache_type_v": "f16",
        "load_mode": "mmap",
        "offline": True,
        "temperature": 0.0,
        "seed": 1,
        "single_turn": True,
        "conversation_mode": True,
        "log_verbosity": CALIBRATION_LOG_VERBOSITY,
        "max_attempts": 1,
        "cross_mind_communication": False,
        "evaluator_access": False,
        "mutable_memory": False,
        "plural_synthesis": False,
        "output_contract": "single-unified-diff-or-one-diff-fence-v1",
        "max_patch_bytes": MAX_PATCH_BYTES,
    }


CALIBRATION_PROTOCOL_SHA256 = _sha256_json(calibration_protocol_payload())


def _candidate_probe_configuration_sha256(candidate: FrozenModelSource) -> str:
    freeze = LOCAL_MODEL_SOURCE_FREEZE_V2
    return _sha256_json(
        {
            "schema": "plural-cognition-local-calibration-probe-config-v1",
            "model_source_freeze_sha256": freeze.sha256,
            "candidate_source_sha256": candidate.sha256,
            "runtime_sha256": freeze.runtime.sha256,
            "protocol_sha256": CALIBRATION_PROTOCOL_SHA256,
        }
    )


def build_solver_prompt(blueprint: CalibrationBlueprint) -> bytes:
    """Build solver-visible calibration input without protected/gold material."""

    files: list[str] = []
    for path, data in blueprint.buggy_files:
        text = data.decode("utf-8")
        files.append(f"===== FILE: {path} =====\n{text}===== END FILE =====")
    public = json.dumps(
        list(blueprint.public_cases),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    issue = blueprint.issue_prompt.decode("utf-8").strip()
    prompt = (
        "You are repairing a small repository. Work only from the issue, repository "
        "files, and public examples below. Return exactly one unified diff that can "
        "be applied from the repository root. Do not return explanation or markdown "
        "unless you use one single ```diff fenced block containing only the patch.\n\n"
        f"ISSUE:\n{issue}\n\n"
        + "\n\n".join(files)
        + f"\n\nPUBLIC_EXAMPLES_JSON:\n{public}\n"
    )
    return prompt.encode("utf-8")


def _safe_patch_path(value: str, prefix: str) -> bool:
    if not value.startswith(prefix):
        return False
    relative = value[len(prefix) :]
    if not relative or "\\" in relative or relative.startswith("/"):
        return False
    path = PurePosixPath(relative)
    return not path.is_absolute() and ".." not in path.parts and "." not in path.parts


def _validate_patch_headers(patch: bytes) -> None:
    try:
        text = patch.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("patch is not UTF-8") from exc
    if "\x00" in text:
        raise ValueError("patch contains NUL")
    lines = text.splitlines()
    old_headers = [line for line in lines if line.startswith("--- ")]
    new_headers = [line for line in lines if line.startswith("+++ ")]
    if not old_headers or len(old_headers) != len(new_headers):
        raise ValueError("patch must contain paired unified-diff file headers")
    for old, new in zip(old_headers, new_headers, strict=True):
        old_path = old[4:].split("\t", 1)[0].split(" ", 1)[0]
        new_path = new[4:].split("\t", 1)[0].split(" ", 1)[0]
        if not _safe_patch_path(old_path, "a/") or not _safe_patch_path(new_path, "b/"):
            raise ValueError("patch contains an unsafe or non-repository path")
    if not any(line.startswith("@@") for line in lines):
        raise ValueError("patch contains no unified-diff hunk")


def extract_unified_diff(raw: bytes) -> tuple[bytes, str]:
    """Extract one bounded unified diff from a raw model response, fail closed."""

    if type(raw) is not bytes:
        raise TypeError("raw must be bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("model output is not UTF-8") from exc
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise ValueError("model output is empty")

    parse_mode = "raw-diff"
    if text.startswith("```diff\n"):
        if not text.endswith("\n```") or text.count("```") != 2:
            raise ValueError("diff fence must be the only fenced block")
        text = text[len("```diff\n") : -len("\n```")].strip()
        parse_mode = "diff-fence"
    elif "```" in text:
        raise ValueError("model output contains unsupported markdown fencing")

    if not text.startswith("--- "):
        raise ValueError("model output does not begin with a unified diff")
    patch = (text + "\n").encode("utf-8")
    if len(patch) > MAX_PATCH_BYTES:
        raise ValueError("model patch exceeds calibration patch-size ceiling")
    _validate_patch_headers(patch)
    return patch, parse_mode


def _load_command(
    *,
    cli: Path,
    model_path: Path,
    prompt: bytes,
    timeout_seconds: int,
) -> tuple[str, ...]:
    del timeout_seconds  # timeout is enforced by _run_load, not passed to llama-cli
    prompt_text = prompt.decode("utf-8")
    return (
        str(cli),
        "-m",
        str(model_path),
        "-c",
        str(CALIBRATION_CONTEXT_TOKENS),
        "-n",
        str(CALIBRATION_PREDICT_TOKENS),
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
        "-cnv",
        "--no-display-prompt",
        "--log-colors",
        "off",
        "--no-log-timestamps",
        "--log-verbosity",
        str(CALIBRATION_LOG_VERBOSITY),
        "--perf",
        "-st",
        "-p",
        prompt_text,
    )


@dataclass(frozen=True, slots=True)
class CalibrationTaskResult:
    candidate_id: str
    task_id: str
    task_sha256: str
    prompt_sha256: str
    raw_artifact_sha256: str
    raw_output_sha256: str
    raw_stdout_bytes: int
    raw_stderr_sha256: str
    parse_valid: bool
    parse_mode: str | None
    parse_error: str | None
    patch_sha256: str | None
    evaluation_sha256: str | None
    exact_accuracy: float
    evaluator_valid_rate: float
    solved: bool
    elapsed_seconds: float
    peak_gpu_used_mib: int
    peak_process_rss_bytes: int | None
    offloaded_layers: int
    total_layers: int

    def canonical_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CandidateCalibrationSummary:
    candidate_id: str
    task_count: int
    parse_valid_count: int
    solved_count: int
    mean_exact_accuracy: float
    peak_gpu_used_mib: int
    peak_process_rss_bytes: int | None

    def canonical_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LocalRawCalibrationReport:
    software_revision: str
    model_source_freeze_sha256: str
    runtime_sha256: str
    protocol_sha256: str
    candidate_ids: tuple[str, ...]
    task_ids: tuple[str, ...]
    results: tuple[CalibrationTaskResult, ...]
    summaries: tuple[CandidateCalibrationSummary, ...]

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": CALIBRATION_SCHEMA,
            "software_revision": self.software_revision,
            "model_source_freeze_sha256": self.model_source_freeze_sha256,
            "runtime_sha256": self.runtime_sha256,
            "protocol": calibration_protocol_payload(),
            "protocol_sha256": self.protocol_sha256,
            "candidate_ids": list(self.candidate_ids),
            "task_ids": list(self.task_ids),
            "results": [item.canonical_payload() for item in self.results],
            "summaries": [item.canonical_payload() for item in self.summaries],
        }

    @property
    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes).hexdigest()


def _summary(
    candidate_id: str, results: Sequence[CalibrationTaskResult]
) -> CandidateCalibrationSummary:
    own = tuple(item for item in results if item.candidate_id == candidate_id)
    if not own:
        raise ValueError(f"candidate has no calibration results: {candidate_id}")
    rss_values = [item.peak_process_rss_bytes for item in own if item.peak_process_rss_bytes is not None]
    return CandidateCalibrationSummary(
        candidate_id=candidate_id,
        task_count=len(own),
        parse_valid_count=sum(item.parse_valid for item in own),
        solved_count=sum(item.solved for item in own),
        mean_exact_accuracy=sum(item.exact_accuracy for item in own) / len(own),
        peak_gpu_used_mib=max(item.peak_gpu_used_mib for item in own),
        peak_process_rss_bytes=max(rss_values) if rss_values else None,
    )


def run_calibration(
    *,
    runtime_root: Path,
    model_root: Path,
    artifact_root: Path,
    software_revision: str,
    candidate_ids: Sequence[str],
    timeout_seconds: int = CALIBRATION_TIMEOUT_SECONDS,
    docker_executable: str = "docker",
) -> LocalRawCalibrationReport:
    if artifact_root.exists():
        raise ValueError(f"artifact_root already exists: {artifact_root}")
    if type(timeout_seconds) is not int or timeout_seconds < 1:
        raise ValueError("timeout_seconds must be a positive integer")

    freeze = LOCAL_MODEL_SOURCE_FREEZE_V2
    selected = tuple(candidate_ids)
    if not selected:
        raise ValueError("at least one candidate is required")
    if len(selected) != len(set(selected)):
        raise ValueError("candidate IDs must be unique")
    candidates = tuple(freeze.candidate(candidate_id) for candidate_id in selected)

    _verify_runtime_archives(runtime_root)
    cli = runtime_root / "bin" / "llama-cli.exe"
    runtime_observation = _runtime_observation(cli)
    for candidate in candidates:
        model_path = model_root / candidate.candidate_id / candidate.filename
        _verify_model_file(model_path, candidate)

    artifact_root.mkdir(parents=True)
    store = FileContentStore(artifact_root / "store")
    build_root = artifact_root / "build"
    build_root.mkdir()
    staging_root = artifact_root / "staging"
    configuration = probe_qualified_docker_configuration(
        software_revision=software_revision,
        docker_executable=docker_executable,
    )

    materials = {}
    for blueprint in calibration_blueprints():
        materials[blueprint.task_id] = build_matrix_material(
            blueprint=blueprint,
            store=store,
            work_root=build_root / blueprint.task_id,
            software_revision=software_revision,
        )

    results: list[CalibrationTaskResult] = []
    for candidate in candidates:
        model_path = model_root / candidate.candidate_id / candidate.filename
        producer_configuration_sha256 = _candidate_probe_configuration_sha256(candidate)
        for blueprint in calibration_blueprints():
            material = materials[blueprint.task_id]
            prompt = build_solver_prompt(blueprint)
            prompt_sha256 = store.put_bytes(prompt)
            command = _load_command(
                cli=cli,
                model_path=model_path,
                prompt=prompt,
                timeout_seconds=timeout_seconds,
            )
            load, stdout, stderr = _run_load(command, timeout_seconds=timeout_seconds)
            raw_output_sha256 = store.put_bytes(stdout)
            raw_stderr_sha256 = store.put_bytes(stderr)
            resources = ResourceUsage(
                inference_calls=1,
                wall_time_ms=max(0, round(load.elapsed_seconds * 1000)),
                accelerator_time_ms=max(0, round(load.elapsed_seconds * 1000)),
                peak_accelerator_bytes=load.peak_gpu_used_mib * 1024 * 1024,
                peak_ram_bytes=load.peak_process_rss_bytes or 0,
            )
            raw_artifact = StageArtifact(
                stage=CollectiveStage.RAW_MIND_OUTPUT,
                task=material.visible_task.task,
                run_id=f"calibration:{candidate.candidate_id}:{blueprint.task_id}",
                producer_id=candidate.candidate_id,
                producer_configuration_sha256=producer_configuration_sha256,
                protocol_sha256=CALIBRATION_PROTOCOL_SHA256,
                software_revision=software_revision,
                content_sha256=raw_output_sha256,
                resources=resources,
            )
            store.put_bytes(raw_artifact.canonical_bytes())

            parse_valid = False
            parse_mode: str | None = None
            parse_error: str | None = None
            patch_sha256: str | None = None
            evaluation_sha256: str | None = None
            exact_accuracy = 0.0
            evaluator_valid_rate = 0.0
            solved = False
            try:
                patch, parse_mode = extract_unified_diff(stdout)
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
                    raise AssertionError("submission storage identity mismatch")
                evaluation = _evaluate_patch(
                    material=material,
                    configuration=configuration,
                    store=store,
                    staging_root=staging_root,
                    patch_sha256=patch_sha256,
                    submission_sha256=submission.sha256,
                    artifact_sha256=raw_artifact.sha256,
                    docker_executable=docker_executable,
                )
                evaluation_sha256 = store.put_bytes(evaluation.canonical_bytes())
                if evaluation_sha256 != evaluation.sha256:
                    raise AssertionError("evaluation storage identity mismatch")
                exact_accuracy = _metric(evaluation, "exact_accuracy")
                evaluator_valid_rate = _metric(evaluation, "valid_rate")
                solved = bool(evaluation.qualified)
            except ValueError as exc:
                parse_error = str(exc)

            results.append(
                CalibrationTaskResult(
                    candidate_id=candidate.candidate_id,
                    task_id=blueprint.task_id,
                    task_sha256=material.visible_task.sha256,
                    prompt_sha256=prompt_sha256,
                    raw_artifact_sha256=raw_artifact.sha256,
                    raw_output_sha256=raw_output_sha256,
                    raw_stdout_bytes=len(stdout),
                    raw_stderr_sha256=raw_stderr_sha256,
                    parse_valid=parse_valid,
                    parse_mode=parse_mode,
                    parse_error=parse_error,
                    patch_sha256=patch_sha256,
                    evaluation_sha256=evaluation_sha256,
                    exact_accuracy=exact_accuracy,
                    evaluator_valid_rate=evaluator_valid_rate,
                    solved=solved,
                    elapsed_seconds=load.elapsed_seconds,
                    peak_gpu_used_mib=load.peak_gpu_used_mib,
                    peak_process_rss_bytes=load.peak_process_rss_bytes,
                    offloaded_layers=load.offloaded_layers,
                    total_layers=load.total_layers,
                )
            )

    if staging_root.exists() and any(staging_root.iterdir()):
        raise RuntimeError("calibration left Docker staging residue")

    report = LocalRawCalibrationReport(
        software_revision=software_revision,
        model_source_freeze_sha256=freeze.sha256,
        runtime_sha256=freeze.runtime.sha256,
        protocol_sha256=CALIBRATION_PROTOCOL_SHA256,
        candidate_ids=selected,
        task_ids=tuple(blueprint.task_id for blueprint in calibration_blueprints()),
        results=tuple(results),
        summaries=tuple(_summary(candidate_id, results) for candidate_id in selected),
    )
    (artifact_root / "runtime-observation.json").write_bytes(
        _canonical_json_bytes(asdict(runtime_observation))
    )
    (artifact_root / "raw-calibration.json").write_bytes(report.canonical_bytes)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure frozen local capable models only on Repository Surgery calibration material."
    )
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--candidate", action="append", dest="candidate_ids")
    parser.add_argument("--timeout-seconds", type=int, default=CALIBRATION_TIMEOUT_SECONDS)
    parser.add_argument("--docker-executable", default="docker")
    args = parser.parse_args(argv)
    candidate_ids = args.candidate_ids or list(LOCAL_MODEL_SOURCE_FREEZE_V2.candidate_ids)
    try:
        report = run_calibration(
            runtime_root=args.runtime_root,
            model_root=args.model_root,
            artifact_root=args.artifact_root,
            software_revision=args.software_revision,
            candidate_ids=candidate_ids,
            timeout_seconds=args.timeout_seconds,
            docker_executable=args.docker_executable,
        )
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"status=LOCAL_RAW_CALIBRATION_FAIL\nerror={exc}")
        return 2

    print("status=LOCAL_RAW_CALIBRATION_PASS")
    print(f"report_sha256={report.sha256}")
    print(f"protocol_sha256={report.protocol_sha256}")
    print(f"candidate_count={len(report.candidate_ids)}")
    print(f"task_count={len(report.task_ids)}")
    for summary in report.summaries:
        print(
            f"candidate={summary.candidate_id} "
            f"parsed={summary.parse_valid_count}/{summary.task_count} "
            f"solved={summary.solved_count}/{summary.task_count} "
            f"mean_exact_accuracy={summary.mean_exact_accuracy:.3f} "
            f"peak_gpu_used_mib={summary.peak_gpu_used_mib}"
        )
    print(f"output={args.artifact_root / 'raw-calibration.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
