"""Deterministic Repository Surgery v0 calibration smoke experiment.

This is the first protected execution downstream of Docker qualification.  It
uses only project-authored repository/task/patch material.  No model-generated
code is involved.  The experiment proves the end-to-end task-generation ->
qualified sandbox -> protected observation -> privileged grading path before any
capable-model bakeoff starts.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Sequence

from .artifacts import EvaluationRecord
from .content_store import FileContentStore
from .docker_candidate import DockerRunnerConfiguration
from .docker_runner import DockerSandboxRunner
from .grading import (
    BlackBoxEvaluationPlan,
    ComparisonMode,
    ProtectedCase,
    grade_black_box,
    observation_from_sandbox_result,
    protected_expectation_set_sha256,
    protected_input_set_sha256,
)
from .qualified_docker import QUALIFIED_DOCKER, probe_qualified_docker_configuration
from .repository import materialize_repository_snapshot, snapshot_directory
from .repository_surgery import (
    MutationKind,
    PatchFormat,
    RepositorySurgeryGenerationRecord,
    RepositorySurgerySubmission,
    build_visible_repository_surgery_task,
)
from .sandbox import NetworkPolicy, ProtectedSandboxSpec, SandboxLimits, SandboxRequest
from .tasks import ProtectedEvaluatorSpec, SolverVisibleTask, TaskSplit

CALIBRATION_SMOKE_SCHEMA = "plural-cognition-repository-surgery-calibration-smoke-v1"
CALIBRATION_TASK_ID = "repository-surgery-calibration-boundary-0001"
CALIBRATION_EVALUATOR_ID = "repository-surgery-exact-stdout-v1"
CALIBRATION_COMMAND = ("/usr/local/bin/python3", "app.py")

_CLEAN_APP = b'''import json\nimport sys\n\ndef shipping_total(subtotal: int, premium: bool) -> int:\n    discount = 5 if premium and subtotal >= 50 else 0\n    return subtotal + 7 - discount\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    result = {"total": shipping_total(int(payload["subtotal"]), bool(payload["premium"]))}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n'''

_BUGGY_APP = _CLEAN_APP.replace(b"subtotal >= 50", b"subtotal > 50")

_GOLD_PATCH = b'''--- a/app.py\n+++ b/app.py\n@@ -4,3 +4,3 @@\n def shipping_total(subtotal: int, premium: bool) -> int:\n-    discount = 5 if premium and subtotal > 50 else 0\n+    discount = 5 if premium and subtotal >= 50 else 0\n     return subtotal + 7 - discount\n'''

_ISSUE_PROMPT = (
    "Fix the repository so shipping totals match the documented policy. "
    "Premium customers receive a 5-unit discount when the subtotal reaches "
    "50 or more. Non-premium customers never receive this discount. Preserve "
    "the JSON stdin/stdout interface and return a unified diff only.\n"
).encode("utf-8")

_PUBLIC_CASES = (
    {"input": {"premium": True, "subtotal": 49}, "expected": {"total": 56}},
    {"input": {"premium": True, "subtotal": 51}, "expected": {"total": 53}},
)

_PROTECTED_CASES = (
    ("case-01-below", {"premium": True, "subtotal": 49}, {"total": 56}),
    ("case-02-threshold", {"premium": True, "subtotal": 50}, {"total": 52}),
    ("case-03-above", {"premium": True, "subtotal": 51}, {"total": 53}),
    ("case-04-nonpremium", {"premium": False, "subtotal": 50}, {"total": 57}),
)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _json_line(payload: Any) -> bytes:
    return _canonical_json_bytes(payload) + b"\n"


def _sha256_json(payload: Any) -> str:
    return sha256(_canonical_json_bytes(payload)).hexdigest()


def _metric(record: EvaluationRecord, name: str) -> float:
    for metric in record.metrics:
        if metric.name == name:
            return float(metric.value)
    raise ValueError(f"evaluation lacks metric {name!r}")


@dataclass(frozen=True, slots=True)
class CalibrationMaterial:
    visible_task: SolverVisibleTask
    generation_record: RepositorySurgeryGenerationRecord
    evaluation_plan: BlackBoxEvaluationPlan
    gold_submission: RepositorySurgerySubmission
    limits: SandboxLimits


@dataclass(frozen=True, slots=True)
class CalibrationSmokeReport:
    software_revision: str
    task_sha256: str
    generation_record_sha256: str
    evaluation_plan_sha256: str
    baseline_evaluation_sha256: str
    gold_evaluation_sha256: str
    baseline_exact_accuracy: float
    gold_exact_accuracy: float

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": CALIBRATION_SMOKE_SCHEMA,
            "software_revision": self.software_revision,
            "qualified_docker_report_sha256": QUALIFIED_DOCKER.report_sha256,
            "qualified_docker_source_revision": QUALIFIED_DOCKER.source_revision,
            "qualified_docker_qualification_source_sha256": QUALIFIED_DOCKER.qualification_source_sha256,
            "qualified_docker_engine_sha256": QUALIFIED_DOCKER.engine_qualification_sha256,
            "qualified_docker_image": QUALIFIED_DOCKER.immutable_image,
            "task_sha256": self.task_sha256,
            "generation_record_sha256": self.generation_record_sha256,
            "evaluation_plan_sha256": self.evaluation_plan_sha256,
            "baseline_evaluation_sha256": self.baseline_evaluation_sha256,
            "gold_evaluation_sha256": self.gold_evaluation_sha256,
            "baseline_exact_accuracy": self.baseline_exact_accuracy,
            "gold_exact_accuracy": self.gold_exact_accuracy,
        }

    @property
    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes).hexdigest()


def build_calibration_material(
    *,
    store: FileContentStore,
    work_root: Path,
    software_revision: str,
) -> CalibrationMaterial:
    """Create one deterministic boundary-defect calibration task and gold repair."""

    work_root = Path(work_root)
    work_root.mkdir(parents=True, exist_ok=True)
    if any(work_root.iterdir()):
        raise ValueError("calibration work_root must be empty")

    clean_root = work_root / "clean"
    buggy_root = work_root / "buggy"
    clean_root.mkdir()
    buggy_root.mkdir()
    (clean_root / "app.py").write_bytes(_CLEAN_APP)
    (buggy_root / "app.py").write_bytes(_BUGGY_APP)

    clean_repository = snapshot_directory(clean_root, store)
    buggy_repository = snapshot_directory(buggy_root, store)
    if clean_repository.manifest_sha256 == buggy_repository.manifest_sha256:
        raise AssertionError("calibration mutation did not change repository identity")

    prompt_sha256 = store.put_bytes(_ISSUE_PROMPT)
    public_tests_sha256 = store.put_bytes(
        _canonical_json_bytes({"schema": "repository-surgery-public-cases-v1", "cases": _PUBLIC_CASES})
    )
    visible_task = build_visible_repository_surgery_task(
        task_id=CALIBRATION_TASK_ID,
        split=TaskSplit.CALIBRATION,
        buggy_repository_sha256=buggy_repository.manifest_sha256,
        issue_prompt_sha256=prompt_sha256,
        public_tests_sha256=public_tests_sha256,
        max_visible_bytes=65_536,
    )

    protected_cases: list[ProtectedCase] = []
    for case_id, input_payload, expected_payload in _PROTECTED_CASES:
        protected_cases.append(
            ProtectedCase(
                case_id=case_id,
                runtime_input_sha256=store.put_bytes(_json_line(input_payload)),
                expected_output_sha256=store.put_bytes(_json_line(expected_payload)),
            )
        )
    cases = tuple(protected_cases)

    evaluator_configuration_sha256 = _sha256_json(
        {
            "schema": "repository-surgery-exact-stdout-evaluator-v1",
            "comparison_mode": ComparisonMode.EXACT_BYTES.value,
            "command_argv": CALIBRATION_COMMAND,
            "pass_threshold": 1.0,
        }
    )
    evaluator = ProtectedEvaluatorSpec(
        task_id=visible_task.task.task_id,
        task_payload_sha256=visible_task.task.payload_sha256,
        evaluator_id=CALIBRATION_EVALUATOR_ID,
        evaluator_configuration_sha256=evaluator_configuration_sha256,
        evaluator_software_revision=software_revision,
        protected_inputs_sha256=protected_input_set_sha256(cases),
        protected_expectations_sha256=protected_expectation_set_sha256(cases),
        primary_metric="exact_accuracy",
        pass_threshold=1.0,
    )
    plan = BlackBoxEvaluationPlan(
        task=visible_task.task,
        evaluator=evaluator,
        cases=cases,
    )

    gold_patch_sha256 = store.put_bytes(_GOLD_PATCH)
    producer_artifact_sha256 = store.put_bytes(
        _canonical_json_bytes(
            {"schema": "project-authored-calibration-gold-v1", "task_id": CALIBRATION_TASK_ID}
        )
    )
    gold_submission = RepositorySurgerySubmission(
        task_id=visible_task.task.task_id,
        task_payload_sha256=visible_task.task.payload_sha256,
        producer_artifact_sha256=producer_artifact_sha256,
        patch_sha256=gold_patch_sha256,
        patch_format=PatchFormat.UNIFIED_DIFF,
        patch_size_bytes=len(_GOLD_PATCH),
    )
    stored_submission = store.put_bytes(gold_submission.canonical_bytes())
    if stored_submission != gold_submission.sha256:
        raise AssertionError("gold submission storage identity mismatch")

    mutation_configuration_sha256 = _sha256_json(
        {
            "schema": "repository-surgery-boundary-mutation-v1",
            "path": "app.py",
            "symbol": "shipping_total",
            "operator_from": ">=",
            "operator_to": ">",
            "threshold": 50,
        }
    )
    generation = RepositorySurgeryGenerationRecord(
        task_id=visible_task.task.task_id,
        task_payload_sha256=visible_task.task.payload_sha256,
        split=TaskSplit.CALIBRATION,
        generation_seed=1,
        mutation_kind=MutationKind.BOUNDARY,
        mutation_configuration_sha256=mutation_configuration_sha256,
        generator_software_revision=software_revision,
        clean_repository_sha256=clean_repository.manifest_sha256,
        buggy_repository_sha256=buggy_repository.manifest_sha256,
        issue_prompt_sha256=prompt_sha256,
        public_tests_sha256=public_tests_sha256,
        protected_inputs_sha256=evaluator.protected_inputs_sha256,
        protected_expectations_sha256=evaluator.protected_expectations_sha256,
        gold_patch_sha256=gold_patch_sha256,
    )
    if not generation.binds(visible_task):
        raise AssertionError("generation record does not bind visible calibration task")

    return CalibrationMaterial(
        visible_task=visible_task,
        generation_record=generation,
        evaluation_plan=plan,
        gold_submission=gold_submission,
        limits=SandboxLimits(
            wall_time_ms=2_000,
            cpu_time_ms=1_000,
            memory_bytes=67_108_864,
            writable_bytes=1_048_576,
            process_count=8,
            stdout_bytes=4_096,
            stderr_bytes=4_096,
        ),
    )


def _sandbox_spec(
    *,
    configuration: DockerRunnerConfiguration,
    limits: SandboxLimits,
) -> ProtectedSandboxSpec:
    return ProtectedSandboxSpec(
        runner_id=configuration.runner_id,
        runner_configuration_sha256=configuration.sha256,
        environment_image_sha256=configuration.environment_image_sha256,
        network_policy=NetworkPolicy.DISABLED,
        command_argv=CALIBRATION_COMMAND,
        environment=(),
        limits=limits,
    )


def _evaluate_patch(
    *,
    material: CalibrationMaterial,
    configuration: DockerRunnerConfiguration,
    store: FileContentStore,
    staging_root: Path,
    patch_sha256: str,
    submission_sha256: str,
    artifact_sha256: str,
    docker_executable: str,
) -> EvaluationRecord:
    spec = _sandbox_spec(configuration=configuration, limits=material.limits)
    runner = DockerSandboxRunner(
        spec=spec,
        configuration=configuration,
        store=store,
        staging_root=staging_root,
        docker_executable=docker_executable,
    )
    observations = []
    for case in material.evaluation_plan.cases:
        request = SandboxRequest(
            task=material.visible_task.task,
            submission_sha256=submission_sha256,
            buggy_repository_sha256=material.generation_record.buggy_repository_sha256,
            patch_sha256=patch_sha256,
            runtime_input_sha256=case.runtime_input_sha256,
            sandbox_spec_sha256=spec.sha256,
        )
        result = runner.run(request)
        observations.append(
            observation_from_sandbox_result(
                case_id=case.case_id,
                runtime_input_sha256=case.runtime_input_sha256,
                result=result,
                observed_output_sha256=result.stdout_sha256,
            )
        )
    return grade_black_box(
        plan=material.evaluation_plan,
        artifact_sha256=artifact_sha256,
        observations=tuple(observations),
        store=store,
    )


def run_calibration_smoke(
    *,
    artifact_root: Path,
    software_revision: str,
    docker_executable: str = "docker",
) -> CalibrationSmokeReport:
    """Execute buggy baseline and project-authored gold repair through qualified Docker."""

    artifact_root = Path(artifact_root)
    if artifact_root.exists() and any(artifact_root.iterdir()):
        raise ValueError("artifact_root must be absent or empty")
    artifact_root.mkdir(parents=True, exist_ok=True)
    store = FileContentStore(artifact_root / "store")
    material = build_calibration_material(
        store=store,
        work_root=artifact_root / "build",
        software_revision=software_revision,
    )
    configuration = probe_qualified_docker_configuration(
        software_revision=software_revision,
        docker_executable=docker_executable,
    )

    baseline_submission_sha256 = store.put_bytes(
        _canonical_json_bytes(
            {"schema": "project-authored-calibration-baseline-v1", "task_id": CALIBRATION_TASK_ID}
        )
    )
    empty_patch_sha256 = store.put_bytes(b"")
    baseline = _evaluate_patch(
        material=material,
        configuration=configuration,
        store=store,
        staging_root=artifact_root / "staging",
        patch_sha256=empty_patch_sha256,
        submission_sha256=baseline_submission_sha256,
        artifact_sha256=baseline_submission_sha256,
        docker_executable=docker_executable,
    )
    gold = _evaluate_patch(
        material=material,
        configuration=configuration,
        store=store,
        staging_root=artifact_root / "staging",
        patch_sha256=material.gold_submission.patch_sha256,
        submission_sha256=material.gold_submission.sha256,
        artifact_sha256=material.gold_submission.sha256,
        docker_executable=docker_executable,
    )

    baseline_accuracy = _metric(baseline, "exact_accuracy")
    gold_accuracy = _metric(gold, "exact_accuracy")
    if baseline.qualified is not False or baseline_accuracy >= 1.0:
        raise RuntimeError("calibration mutation is not observably defective")
    if gold.qualified is not True or gold_accuracy != 1.0:
        raise RuntimeError("project-authored gold repair did not fully restore protected behavior")

    report = CalibrationSmokeReport(
        software_revision=software_revision,
        task_sha256=material.visible_task.sha256,
        generation_record_sha256=material.generation_record.sha256,
        evaluation_plan_sha256=material.evaluation_plan.sha256,
        baseline_evaluation_sha256=baseline.sha256,
        gold_evaluation_sha256=gold.sha256,
        baseline_exact_accuracy=baseline_accuracy,
        gold_exact_accuracy=gold_accuracy,
    )
    (artifact_root / "calibration-smoke.json").write_bytes(report.canonical_bytes)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the project-authored Repository Surgery calibration smoke experiment."
    )
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--docker-executable", default="docker")
    args = parser.parse_args(argv)

    report = run_calibration_smoke(
        artifact_root=args.artifact_root,
        software_revision=args.software_revision,
        docker_executable=args.docker_executable,
    )
    print("status=CALIBRATION_SMOKE_PASS")
    print(f"report_sha256={report.sha256}")
    print(f"qualified_docker_report_sha256={QUALIFIED_DOCKER.report_sha256}")
    print(f"task_sha256={report.task_sha256}")
    print(f"generation_record_sha256={report.generation_record_sha256}")
    print(f"evaluation_plan_sha256={report.evaluation_plan_sha256}")
    print(f"baseline_exact_accuracy={report.baseline_exact_accuracy:.6f}")
    print(f"gold_exact_accuracy={report.gold_exact_accuracy:.6f}")
    print(f"output={args.artifact_root / 'calibration-smoke.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
