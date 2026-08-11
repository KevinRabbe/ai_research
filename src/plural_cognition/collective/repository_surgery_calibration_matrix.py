"""Deterministic multi-defect Repository Surgery v0 calibration matrix.

This expands the first boundary-only smoke into several project-authored defect
classes while preserving the same qualified Docker + privileged grading path.
No model-generated code is executed here.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
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
from .repository import snapshot_directory
from .repository_surgery import (
    MutationKind,
    PatchFormat,
    RepositorySurgeryGenerationRecord,
    RepositorySurgerySubmission,
    build_visible_repository_surgery_task,
)
from .sandbox import NetworkPolicy, ProtectedSandboxSpec, SandboxLimits, SandboxRequest
from .tasks import ProtectedEvaluatorSpec, SolverVisibleTask, TaskSplit

CALIBRATION_MATRIX_SCHEMA = "plural-cognition-repository-surgery-calibration-matrix-v1"
CALIBRATION_EVALUATOR_ID = "repository-surgery-exact-stdout-v1"
CALIBRATION_COMMAND = ("/usr/local/bin/python3", "app.py")


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
class CalibrationBlueprint:
    task_id: str
    mutation_kind: MutationKind
    generation_seed: int
    clean_files: tuple[tuple[str, bytes], ...]
    buggy_files: tuple[tuple[str, bytes], ...]
    gold_patch: bytes
    issue_prompt: bytes
    public_cases: tuple[dict[str, Any], ...]
    protected_cases: tuple[tuple[str, dict[str, Any], dict[str, Any]], ...]
    mutation_configuration: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.task_id:
            raise ValueError("task_id must be non-empty")
        if not isinstance(self.mutation_kind, MutationKind):
            raise TypeError("mutation_kind must be MutationKind")
        if type(self.generation_seed) is not int:
            raise TypeError("generation_seed must be int")
        for field in ("clean_files", "buggy_files"):
            files = getattr(self, field)
            paths = tuple(path for path, _ in files)
            if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
                raise ValueError(f"{field} paths must be sorted and unique")
            if any(type(data) is not bytes for _, data in files):
                raise TypeError(f"{field} contents must be bytes")
        if tuple(path for path, _ in self.clean_files) != tuple(
            path for path, _ in self.buggy_files
        ):
            raise ValueError("clean and buggy file sets must have identical paths")
        if self.clean_files == self.buggy_files:
            raise ValueError("calibration blueprint must contain a real mutation")
        if type(self.gold_patch) is not bytes or not self.gold_patch:
            raise ValueError("gold_patch must be non-empty bytes")
        if type(self.issue_prompt) is not bytes or not self.issue_prompt:
            raise ValueError("issue_prompt must be non-empty bytes")
        case_ids = tuple(case_id for case_id, _, _ in self.protected_cases)
        if case_ids != tuple(sorted(case_ids)) or len(case_ids) != len(set(case_ids)):
            raise ValueError("protected case ids must be sorted and unique")
        if not case_ids:
            raise ValueError("protected cases must not be empty")


@dataclass(frozen=True, slots=True)
class CalibrationMatrixMaterial:
    blueprint: CalibrationBlueprint
    visible_task: SolverVisibleTask
    generation_record: RepositorySurgeryGenerationRecord
    evaluation_plan: BlackBoxEvaluationPlan
    gold_submission: RepositorySurgerySubmission
    limits: SandboxLimits


@dataclass(frozen=True, slots=True)
class CalibrationMatrixTaskReport:
    task_id: str
    mutation_kind: str
    task_sha256: str
    generation_record_sha256: str
    evaluation_plan_sha256: str
    baseline_evaluation_sha256: str
    gold_evaluation_sha256: str
    baseline_exact_accuracy: float
    gold_exact_accuracy: float
    baseline_valid_rate: float
    gold_valid_rate: float

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "mutation_kind": self.mutation_kind,
            "task_sha256": self.task_sha256,
            "generation_record_sha256": self.generation_record_sha256,
            "evaluation_plan_sha256": self.evaluation_plan_sha256,
            "baseline_evaluation_sha256": self.baseline_evaluation_sha256,
            "gold_evaluation_sha256": self.gold_evaluation_sha256,
            "baseline_exact_accuracy": self.baseline_exact_accuracy,
            "gold_exact_accuracy": self.gold_exact_accuracy,
            "baseline_valid_rate": self.baseline_valid_rate,
            "gold_valid_rate": self.gold_valid_rate,
        }


@dataclass(frozen=True, slots=True)
class CalibrationMatrixReport:
    software_revision: str
    tasks: tuple[CalibrationMatrixTaskReport, ...]

    def __post_init__(self) -> None:
        task_ids = tuple(item.task_id for item in self.tasks)
        if task_ids != tuple(sorted(task_ids)) or len(task_ids) != len(set(task_ids)):
            raise ValueError("matrix task reports must be sorted by unique task_id")
        if not self.tasks:
            raise ValueError("matrix report must contain tasks")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": CALIBRATION_MATRIX_SCHEMA,
            "software_revision": self.software_revision,
            "qualified_docker_report_sha256": QUALIFIED_DOCKER.report_sha256,
            "qualified_docker_source_revision": QUALIFIED_DOCKER.source_revision,
            "qualified_docker_qualification_source_sha256": QUALIFIED_DOCKER.qualification_source_sha256,
            "qualified_docker_engine_sha256": QUALIFIED_DOCKER.engine_qualification_sha256,
            "qualified_docker_image": QUALIFIED_DOCKER.immutable_image,
            "task_count": len(self.tasks),
            "tasks": [item.canonical_payload() for item in self.tasks],
        }

    @property
    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes).hexdigest()


def calibration_blueprints() -> tuple[CalibrationBlueprint, ...]:
    boundary_clean = b'''import json\nimport sys\n\ndef shipping_total(subtotal: int, premium: bool) -> int:\n    discount = 5 if premium and subtotal >= 50 else 0\n    return subtotal + 7 - discount\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    result = {"total": shipping_total(int(payload["subtotal"]), bool(payload["premium"]))}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n'''
    boundary_buggy = boundary_clean.replace(b"subtotal >= 50", b"subtotal > 50")

    local_clean = b'''import json\nimport sys\n\ndef compute_score(items: int, bonus: bool) -> int:\n    base = items * 3\n    return base + (2 if bonus else 0)\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    result = {"score": compute_score(int(payload["items"]), bool(payload["bonus"]))}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n'''
    local_buggy = local_clean.replace(b"items * 3", b"items + 3")

    api_clean = b'''import json\nimport sys\n\ndef scaled(value: int, scale: int) -> int:\n    return value * scale\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    scale = int(payload.get("scale", 1))\n    result = {"value": scaled(int(payload["value"]), scale)}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n'''
    api_buggy = api_clean.replace(b'payload.get("scale", 1)', b'payload["scale"]')

    multi_app = b'''import json\nimport sys\nfrom rates import delivery_fee\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    total = int(payload["subtotal"]) + delivery_fee(str(payload["region"]))\n    sys.stdout.write(json.dumps({"total": total}, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n'''
    multi_rates_clean = b'''def delivery_fee(region: str) -> int:\n    return 5 if region == "EU" else 3\n'''
    multi_rates_buggy = multi_rates_clean.replace(b"return 5 if", b"return 4 if")

    state_clean = b'''import json\nimport sys\n\nclass Cart:\n    def __init__(self) -> None:\n        self.total = 0\n\n    def add(self, amount: int) -> int:\n        self.total += amount\n        return self.total\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    cart = Cart()\n    totals = [cart.add(int(amount)) for amount in payload["amounts"]]\n    sys.stdout.write(json.dumps({"totals": totals}, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n'''
    state_buggy = state_clean.replace(b"self.total += amount", b"self.total = amount")

    error_clean = b'''import json\nimport sys\n\ndef divide(value: int, divisor: int) -> int:\n    if divisor == 0:\n        raise ValueError("divisor must not be zero")\n    return value // divisor\n\ndef main() -> None:\n    payload = json.loads(sys.stdin.read())\n    try:\n        result = {"ok": True, "quotient": divide(int(payload["value"]), int(payload["divisor"]))}\n    except (KeyError, TypeError, ValueError):\n        result = {"error": "invalid-input", "ok": False}\n    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\\n")\n\nif __name__ == "__main__":\n    main()\n'''
    error_buggy = error_clean.replace(
        b'    if divisor == 0:\n        raise ValueError("divisor must not be zero")\n',
        b"",
    )

    blueprints = (
        CalibrationBlueprint(
            task_id="repository-surgery-calibration-api-contract-0001",
            mutation_kind=MutationKind.API_CONTRACT,
            generation_seed=3,
            clean_files=(("app.py", api_clean),),
            buggy_files=(("app.py", api_buggy),),
            gold_patch=b'''--- a/app.py\n+++ b/app.py\n@@ -7,3 +7,3 @@\n def main() -> None:\n     payload = json.loads(sys.stdin.read())\n-    scale = int(payload["scale"])\n+    scale = int(payload.get("scale", 1))\n''',
            issue_prompt=(
                "Fix the JSON API contract. The input field 'scale' is optional and defaults to 1; "
                "'value' is required. Preserve the JSON stdin/stdout interface and return a unified diff only.\n"
            ).encode("utf-8"),
            public_cases=(
                {"input": {"scale": 2, "value": 4}, "expected": {"value": 8}},
                {"input": {"scale": 3, "value": 5}, "expected": {"value": 15}},
            ),
            protected_cases=(
                ("case-01-explicit", {"scale": 2, "value": 4}, {"value": 8}),
                ("case-02-default", {"value": 9}, {"value": 9}),
                ("case-03-explicit-one", {"scale": 1, "value": 7}, {"value": 7}),
                ("case-04-negative", {"value": -3}, {"value": -3}),
            ),
            mutation_configuration={
                "schema": "repository-surgery-api-contract-mutation-v1",
                "path": "app.py",
                "field": "scale",
                "contract": "optional-default-one",
                "mutation": "required-index-access",
            },
        ),
        CalibrationBlueprint(
            task_id="repository-surgery-calibration-boundary-0001",
            mutation_kind=MutationKind.BOUNDARY,
            generation_seed=1,
            clean_files=(("app.py", boundary_clean),),
            buggy_files=(("app.py", boundary_buggy),),
            gold_patch=b'''--- a/app.py\n+++ b/app.py\n@@ -4,3 +4,3 @@\n def shipping_total(subtotal: int, premium: bool) -> int:\n-    discount = 5 if premium and subtotal > 50 else 0\n+    discount = 5 if premium and subtotal >= 50 else 0\n     return subtotal + 7 - discount\n''',
            issue_prompt=(
                "Fix the repository so shipping totals match the documented policy. Premium customers "
                "receive a 5-unit discount when the subtotal reaches 50 or more. Non-premium customers "
                "never receive this discount. Preserve the JSON stdin/stdout interface and return a unified diff only.\n"
            ).encode("utf-8"),
            public_cases=(
                {"input": {"premium": True, "subtotal": 49}, "expected": {"total": 56}},
                {"input": {"premium": True, "subtotal": 51}, "expected": {"total": 53}},
            ),
            protected_cases=(
                ("case-01-below", {"premium": True, "subtotal": 49}, {"total": 56}),
                ("case-02-threshold", {"premium": True, "subtotal": 50}, {"total": 52}),
                ("case-03-above", {"premium": True, "subtotal": 51}, {"total": 53}),
                ("case-04-nonpremium", {"premium": False, "subtotal": 50}, {"total": 57}),
            ),
            mutation_configuration={
                "schema": "repository-surgery-boundary-mutation-v1",
                "path": "app.py",
                "symbol": "shipping_total",
                "operator_from": ">=",
                "operator_to": ">",
                "threshold": 50,
            },
        ),
        CalibrationBlueprint(
            task_id="repository-surgery-calibration-error-handling-0001",
            mutation_kind=MutationKind.ERROR_HANDLING,
            generation_seed=6,
            clean_files=(("app.py", error_clean),),
            buggy_files=(("app.py", error_buggy),),
            gold_patch=b'''--- a/app.py\n+++ b/app.py\n@@ -3,2 +3,4 @@\n \n def divide(value: int, divisor: int) -> int:\n+    if divisor == 0:\n+        raise ValueError("divisor must not be zero")\n     return value // divisor\n''',
            issue_prompt=(
                "Fix invalid-input handling. A zero divisor must produce the same structured "
                "invalid-input JSON response as other rejected inputs instead of crashing. Preserve "
                "valid integer division behavior and return a unified diff only.\n"
            ).encode("utf-8"),
            public_cases=(
                {"input": {"divisor": 2, "value": 8}, "expected": {"ok": True, "quotient": 4}},
            ),
            protected_cases=(
                ("case-01-valid", {"divisor": 2, "value": 8}, {"ok": True, "quotient": 4}),
                ("case-02-zero", {"divisor": 0, "value": 8}, {"error": "invalid-input", "ok": False}),
                ("case-03-negative", {"divisor": -2, "value": 9}, {"ok": True, "quotient": -5}),
                ("case-04-one", {"divisor": 1, "value": 3}, {"ok": True, "quotient": 3}),
            ),
            mutation_configuration={
                "schema": "repository-surgery-error-handling-mutation-v1",
                "path": "app.py",
                "symbol": "divide",
                "removed_guard": "divisor-zero",
            },
        ),
        CalibrationBlueprint(
            task_id="repository-surgery-calibration-local-logic-0001",
            mutation_kind=MutationKind.LOCAL_LOGIC,
            generation_seed=2,
            clean_files=(("app.py", local_clean),),
            buggy_files=(("app.py", local_buggy),),
            gold_patch=b'''--- a/app.py\n+++ b/app.py\n@@ -4,3 +4,3 @@\n def compute_score(items: int, bonus: bool) -> int:\n-    base = items + 3\n+    base = items * 3\n     return base + (2 if bonus else 0)\n''',
            issue_prompt=(
                "Fix score computation. Each item contributes exactly 3 points and the optional bonus "
                "adds 2 points once. Preserve the JSON stdin/stdout interface and return a unified diff only.\n"
            ).encode("utf-8"),
            public_cases=(
                {"input": {"bonus": False, "items": 1}, "expected": {"score": 3}},
                {"input": {"bonus": True, "items": 2}, "expected": {"score": 8}},
            ),
            protected_cases=(
                ("case-01-one", {"bonus": False, "items": 1}, {"score": 3}),
                ("case-02-two-bonus", {"bonus": True, "items": 2}, {"score": 8}),
                ("case-03-zero", {"bonus": False, "items": 0}, {"score": 0}),
                ("case-04-five-bonus", {"bonus": True, "items": 5}, {"score": 17}),
            ),
            mutation_configuration={
                "schema": "repository-surgery-local-logic-mutation-v1",
                "path": "app.py",
                "symbol": "compute_score",
                "operator_from": "multiply",
                "operator_to": "add",
                "operand": 3,
            },
        ),
        CalibrationBlueprint(
            task_id="repository-surgery-calibration-multi-file-0001",
            mutation_kind=MutationKind.MULTI_FILE_BEHAVIOR,
            generation_seed=4,
            clean_files=(("app.py", multi_app), ("rates.py", multi_rates_clean)),
            buggy_files=(("app.py", multi_app), ("rates.py", multi_rates_buggy)),
            gold_patch=b'''--- a/rates.py\n+++ b/rates.py\n@@ -1,2 +1,2 @@\n def delivery_fee(region: str) -> int:\n-    return 4 if region == "EU" else 3\n+    return 5 if region == "EU" else 3\n''',
            issue_prompt=(
                "Fix delivery fee behavior across the repository. EU deliveries add 5 units; all other "
                "regions add 3. Preserve the app.py JSON stdin/stdout interface and return a unified diff only.\n"
            ).encode("utf-8"),
            public_cases=(
                {"input": {"region": "US", "subtotal": 20}, "expected": {"total": 23}},
            ),
            protected_cases=(
                ("case-01-us", {"region": "US", "subtotal": 20}, {"total": 23}),
                ("case-02-eu", {"region": "EU", "subtotal": 20}, {"total": 25}),
                ("case-03-eu-zero", {"region": "EU", "subtotal": 0}, {"total": 5}),
                ("case-04-other", {"region": "APAC", "subtotal": 9}, {"total": 12}),
            ),
            mutation_configuration={
                "schema": "repository-surgery-multi-file-mutation-v1",
                "path": "rates.py",
                "symbol": "delivery_fee",
                "region": "EU",
                "rate_from": 5,
                "rate_to": 4,
            },
        ),
        CalibrationBlueprint(
            task_id="repository-surgery-calibration-state-management-0001",
            mutation_kind=MutationKind.STATE_MANAGEMENT,
            generation_seed=5,
            clean_files=(("app.py", state_clean),),
            buggy_files=(("app.py", state_buggy),),
            gold_patch=b'''--- a/app.py\n+++ b/app.py\n@@ -8,3 +8,3 @@\n     def add(self, amount: int) -> int:\n-        self.total = amount\n+        self.total += amount\n         return self.total\n''',
            issue_prompt=(
                "Fix cart state accumulation. Each add operation must return the cumulative total after "
                "including the new amount. Preserve the JSON stdin/stdout interface and return a unified diff only.\n"
            ).encode("utf-8"),
            public_cases=(
                {"input": {"amounts": [4]}, "expected": {"totals": [4]}},
            ),
            protected_cases=(
                ("case-01-single", {"amounts": [4]}, {"totals": [4]}),
                ("case-02-two", {"amounts": [4, 3]}, {"totals": [4, 7]}),
                ("case-03-three", {"amounts": [1, 2, 5]}, {"totals": [1, 3, 8]}),
                ("case-04-zero", {"amounts": [5, 0, 2]}, {"totals": [5, 5, 7]}),
            ),
            mutation_configuration={
                "schema": "repository-surgery-state-management-mutation-v1",
                "path": "app.py",
                "symbol": "Cart.add",
                "mutation": "overwrite-instead-of-accumulate",
            },
        ),
    )
    task_ids = tuple(item.task_id for item in blueprints)
    if task_ids != tuple(sorted(task_ids)):
        raise AssertionError("calibration blueprints must be sorted by task_id")
    kinds = tuple(item.mutation_kind for item in blueprints)
    if len(kinds) != len(set(kinds)):
        raise AssertionError("calibration blueprints must use unique mutation kinds")
    return blueprints


def _write_tree(root: Path, files: tuple[tuple[str, bytes], ...]) -> None:
    root.mkdir(parents=True)
    for relative, data in files:
        parts = PurePosixPath(relative).parts
        destination = root.joinpath(*parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)


def build_matrix_material(
    *,
    blueprint: CalibrationBlueprint,
    store: FileContentStore,
    work_root: Path,
    software_revision: str,
) -> CalibrationMatrixMaterial:
    work_root = Path(work_root)
    work_root.mkdir(parents=True, exist_ok=True)
    if any(work_root.iterdir()):
        raise ValueError("matrix task work_root must be empty")

    clean_root = work_root / "clean"
    buggy_root = work_root / "buggy"
    _write_tree(clean_root, blueprint.clean_files)
    _write_tree(buggy_root, blueprint.buggy_files)
    clean_repository = snapshot_directory(clean_root, store)
    buggy_repository = snapshot_directory(buggy_root, store)
    if clean_repository.manifest_sha256 == buggy_repository.manifest_sha256:
        raise AssertionError("matrix mutation did not change repository identity")

    prompt_sha256 = store.put_bytes(blueprint.issue_prompt)
    public_tests_sha256 = store.put_bytes(
        _canonical_json_bytes(
            {"schema": "repository-surgery-public-cases-v1", "cases": blueprint.public_cases}
        )
    )
    visible_task = build_visible_repository_surgery_task(
        task_id=blueprint.task_id,
        split=TaskSplit.CALIBRATION,
        buggy_repository_sha256=buggy_repository.manifest_sha256,
        issue_prompt_sha256=prompt_sha256,
        public_tests_sha256=public_tests_sha256,
        max_visible_bytes=65_536,
    )

    cases = tuple(
        ProtectedCase(
            case_id=case_id,
            runtime_input_sha256=store.put_bytes(_json_line(input_payload)),
            expected_output_sha256=store.put_bytes(_json_line(expected_payload)),
        )
        for case_id, input_payload, expected_payload in blueprint.protected_cases
    )
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
    plan = BlackBoxEvaluationPlan(task=visible_task.task, evaluator=evaluator, cases=cases)

    gold_patch_sha256 = store.put_bytes(blueprint.gold_patch)
    producer_artifact_sha256 = store.put_bytes(
        _canonical_json_bytes(
            {"schema": "project-authored-calibration-matrix-gold-v1", "task_id": blueprint.task_id}
        )
    )
    gold_submission = RepositorySurgerySubmission(
        task_id=visible_task.task.task_id,
        task_payload_sha256=visible_task.task.payload_sha256,
        producer_artifact_sha256=producer_artifact_sha256,
        patch_sha256=gold_patch_sha256,
        patch_format=PatchFormat.UNIFIED_DIFF,
        patch_size_bytes=len(blueprint.gold_patch),
    )
    if store.put_bytes(gold_submission.canonical_bytes()) != gold_submission.sha256:
        raise AssertionError("gold submission storage identity mismatch")

    generation = RepositorySurgeryGenerationRecord(
        task_id=visible_task.task.task_id,
        task_payload_sha256=visible_task.task.payload_sha256,
        split=TaskSplit.CALIBRATION,
        generation_seed=blueprint.generation_seed,
        mutation_kind=blueprint.mutation_kind,
        mutation_configuration_sha256=_sha256_json(blueprint.mutation_configuration),
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
        raise AssertionError("generation record does not bind matrix visible task")

    return CalibrationMatrixMaterial(
        blueprint=blueprint,
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
    *, configuration: DockerRunnerConfiguration, limits: SandboxLimits
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
    material: CalibrationMatrixMaterial,
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


def run_calibration_matrix(
    *,
    artifact_root: Path,
    software_revision: str,
    docker_executable: str = "docker",
) -> CalibrationMatrixReport:
    artifact_root = Path(artifact_root)
    if artifact_root.exists() and any(artifact_root.iterdir()):
        raise ValueError("artifact_root must be absent or empty")
    artifact_root.mkdir(parents=True, exist_ok=True)
    store = FileContentStore(artifact_root / "store")
    build_root = artifact_root / "build"
    build_root.mkdir()
    staging_root = artifact_root / "staging"
    configuration = probe_qualified_docker_configuration(
        software_revision=software_revision,
        docker_executable=docker_executable,
    )

    empty_patch_sha256 = store.put_bytes(b"")
    task_reports: list[CalibrationMatrixTaskReport] = []
    for blueprint in calibration_blueprints():
        material = build_matrix_material(
            blueprint=blueprint,
            store=store,
            work_root=build_root / blueprint.task_id,
            software_revision=software_revision,
        )
        baseline_submission_sha256 = store.put_bytes(
            _canonical_json_bytes(
                {
                    "schema": "project-authored-calibration-matrix-baseline-v1",
                    "task_id": blueprint.task_id,
                }
            )
        )
        baseline = _evaluate_patch(
            material=material,
            configuration=configuration,
            store=store,
            staging_root=staging_root,
            patch_sha256=empty_patch_sha256,
            submission_sha256=baseline_submission_sha256,
            artifact_sha256=baseline_submission_sha256,
            docker_executable=docker_executable,
        )
        gold = _evaluate_patch(
            material=material,
            configuration=configuration,
            store=store,
            staging_root=staging_root,
            patch_sha256=material.gold_submission.patch_sha256,
            submission_sha256=material.gold_submission.sha256,
            artifact_sha256=material.gold_submission.sha256,
            docker_executable=docker_executable,
        )

        baseline_accuracy = _metric(baseline, "exact_accuracy")
        gold_accuracy = _metric(gold, "exact_accuracy")
        baseline_valid = _metric(baseline, "valid_rate")
        gold_valid = _metric(gold, "valid_rate")
        if baseline.qualified is not False or baseline_accuracy >= 1.0:
            raise RuntimeError(f"{blueprint.task_id}: mutation is not observably defective")
        if gold.qualified is not True or gold_accuracy != 1.0 or gold_valid != 1.0:
            raise RuntimeError(f"{blueprint.task_id}: gold repair did not fully restore behavior")

        task_reports.append(
            CalibrationMatrixTaskReport(
                task_id=blueprint.task_id,
                mutation_kind=blueprint.mutation_kind.value,
                task_sha256=material.visible_task.sha256,
                generation_record_sha256=material.generation_record.sha256,
                evaluation_plan_sha256=material.evaluation_plan.sha256,
                baseline_evaluation_sha256=baseline.sha256,
                gold_evaluation_sha256=gold.sha256,
                baseline_exact_accuracy=baseline_accuracy,
                gold_exact_accuracy=gold_accuracy,
                baseline_valid_rate=baseline_valid,
                gold_valid_rate=gold_valid,
            )
        )

    if staging_root.exists() and any(staging_root.iterdir()):
        raise RuntimeError("calibration matrix left staging residue")

    report = CalibrationMatrixReport(
        software_revision=software_revision,
        tasks=tuple(task_reports),
    )
    (artifact_root / "calibration-matrix.json").write_bytes(report.canonical_bytes)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic multi-defect Repository Surgery calibration through qualified Docker."
    )
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--docker-executable", default="docker")
    args = parser.parse_args(argv)

    report = run_calibration_matrix(
        artifact_root=args.artifact_root,
        software_revision=args.software_revision,
        docker_executable=args.docker_executable,
    )
    print("status=CALIBRATION_MATRIX_PASS")
    print(f"report_sha256={report.sha256}")
    print(f"qualified_docker_report_sha256={QUALIFIED_DOCKER.report_sha256}")
    print(f"task_count={len(report.tasks)}")
    for item in report.tasks:
        print(
            "task="
            f"{item.task_id} kind={item.mutation_kind} "
            f"baseline={item.baseline_exact_accuracy:.6f} "
            f"gold={item.gold_exact_accuracy:.6f} "
            f"baseline_valid={item.baseline_valid_rate:.6f} "
            f"gold_valid={item.gold_valid_rate:.6f}"
        )
    print(f"output={args.artifact_root / 'calibration-matrix.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
