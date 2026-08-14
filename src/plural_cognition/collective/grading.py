"""Privileged black-box grading kept outside candidate execution sandboxes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Any, Sequence

from .artifacts import (
    EvaluationRecord,
    EvaluationVisibility,
    MetricValue,
    ResourceUsage,
    TaskIdentity,
)
from .content_store import ContentStore, validate_sha256
from .sandbox import SandboxResult
from .tasks import ProtectedEvaluatorSpec

BLACK_BOX_CASE_SCHEMA = "plural-cognition-black-box-case-v1"
BLACK_BOX_OBSERVATION_SCHEMA = "plural-cognition-black-box-observation-v1"
BLACK_BOX_PLAN_SCHEMA = "plural-cognition-black-box-plan-v1"


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _nonempty(value: str, field: str) -> None:
    if type(value) is not str or not value:
        raise ValueError(f"{field} must be a non-empty string")


class ComparisonMode(str, Enum):
    EXACT_BYTES = "exact-bytes-v1"


@dataclass(frozen=True, slots=True)
class ProtectedCase:
    """One privileged input/expectation pair.

    The runtime input may be supplied to candidate execution. The expected output
    hash stays in the privileged grading plan and never enters ``SandboxRequest``.
    """

    case_id: str
    runtime_input_sha256: str
    expected_output_sha256: str

    def __post_init__(self) -> None:
        _nonempty(self.case_id, "case_id")
        validate_sha256(self.runtime_input_sha256)
        validate_sha256(self.expected_output_sha256)
        if self.runtime_input_sha256 == self.expected_output_sha256:
            raise ValueError("runtime input and expected output must be distinct artifacts")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": BLACK_BOX_CASE_SCHEMA,
            "case_id": self.case_id,
            "runtime_input_sha256": self.runtime_input_sha256,
            "expected_output_sha256": self.expected_output_sha256,
        }


def protected_input_set_sha256(cases: Sequence[ProtectedCase]) -> str:
    return sha256(
        _canonical_json_bytes(
            [
                {
                    "case_id": case.case_id,
                    "runtime_input_sha256": case.runtime_input_sha256,
                }
                for case in cases
            ]
        )
    ).hexdigest()


def protected_expectation_set_sha256(cases: Sequence[ProtectedCase]) -> str:
    return sha256(
        _canonical_json_bytes(
            [
                {
                    "case_id": case.case_id,
                    "expected_output_sha256": case.expected_output_sha256,
                }
                for case in cases
            ]
        )
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class BlackBoxEvaluationPlan:
    """Privileged, immutable case set and deterministic comparison policy."""

    task: TaskIdentity
    evaluator: ProtectedEvaluatorSpec
    cases: tuple[ProtectedCase, ...]
    comparison_mode: ComparisonMode = ComparisonMode.EXACT_BYTES

    def __post_init__(self) -> None:
        if not isinstance(self.task, TaskIdentity):
            raise TypeError("task must be TaskIdentity")
        if not isinstance(self.evaluator, ProtectedEvaluatorSpec):
            raise TypeError("evaluator must be ProtectedEvaluatorSpec")
        if not self.cases:
            raise ValueError("black-box evaluation requires at least one case")
        if not isinstance(self.comparison_mode, ComparisonMode):
            raise TypeError("comparison_mode must be ComparisonMode")
        if (
            self.evaluator.task_id != self.task.task_id
            or self.evaluator.task_payload_sha256 != self.task.payload_sha256
        ):
            raise ValueError("evaluator does not bind the exact task")
        case_ids = tuple(case.case_id for case in self.cases)
        if case_ids != tuple(sorted(case_ids)) or len(case_ids) != len(set(case_ids)):
            raise ValueError("protected cases must be sorted by unique case_id")
        if self.comparison_mode is ComparisonMode.EXACT_BYTES:
            if self.evaluator.primary_metric != "exact_accuracy":
                raise ValueError(
                    "exact-bytes-v1 requires primary_metric='exact_accuracy'"
                )
            if not 0.0 <= float(self.evaluator.pass_threshold) <= 1.0:
                raise ValueError("exact_accuracy pass_threshold must be in [0, 1]")
        if protected_input_set_sha256(self.cases) != self.evaluator.protected_inputs_sha256:
            raise ValueError("protected input-set identity differs from evaluator spec")
        if (
            protected_expectation_set_sha256(self.cases)
            != self.evaluator.protected_expectations_sha256
        ):
            raise ValueError("protected expectation-set identity differs from evaluator spec")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": BLACK_BOX_PLAN_SCHEMA,
            "task": self.task.canonical_payload(),
            "evaluator": self.evaluator.canonical_payload(),
            "cases": [case.canonical_payload() for case in self.cases],
            "comparison_mode": self.comparison_mode.value,
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()


@dataclass(frozen=True, slots=True)
class CaseObservation:
    """Observed candidate output for one protected input, with no expected label."""

    case_id: str
    runtime_input_sha256: str
    sandbox_result_sha256: str
    observed_output_sha256: str
    execution_valid: bool

    def __post_init__(self) -> None:
        _nonempty(self.case_id, "case_id")
        validate_sha256(self.runtime_input_sha256)
        validate_sha256(self.sandbox_result_sha256)
        validate_sha256(self.observed_output_sha256)
        if type(self.execution_valid) is not bool:
            raise TypeError("execution_valid must be bool")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": BLACK_BOX_OBSERVATION_SCHEMA,
            "case_id": self.case_id,
            "runtime_input_sha256": self.runtime_input_sha256,
            "sandbox_result_sha256": self.sandbox_result_sha256,
            "observed_output_sha256": self.observed_output_sha256,
            "execution_valid": self.execution_valid,
        }

    @property
    def sha256(self) -> str:
        return sha256(_canonical_json_bytes(self.canonical_payload())).hexdigest()


def observation_from_sandbox_result(
    *,
    case_id: str,
    runtime_input_sha256: str,
    result: SandboxResult,
    observed_output_sha256: str,
) -> CaseObservation:
    """Bind an isolated execution result to one output artifact.

    Output extraction/canonicalization is a separate frozen adapter. This helper
    only records its content hash and whether the sandbox completed normally.
    """

    if not isinstance(result, SandboxResult):
        raise TypeError("result must be SandboxResult")
    return CaseObservation(
        case_id=case_id,
        runtime_input_sha256=runtime_input_sha256,
        sandbox_result_sha256=result.sha256,
        observed_output_sha256=observed_output_sha256,
        execution_valid=result.completed_normally and result.exit_code == 0,
    )


def grade_black_box(
    *,
    plan: BlackBoxEvaluationPlan,
    artifact_sha256: str,
    observations: Sequence[CaseObservation],
    store: ContentStore,
    grader_resources: ResourceUsage = ResourceUsage(verifier_calls=1),
) -> EvaluationRecord:
    """Compare frozen observed outputs to protected expectations outside sandbox.

    Invalid executions count as failures and remain in the denominator. No case is
    silently dropped. The initial v0 comparison is exact byte equality after a
    separately frozen output-canonicalization adapter has produced each artifact.
    """

    if not isinstance(plan, BlackBoxEvaluationPlan):
        raise TypeError("plan must be BlackBoxEvaluationPlan")
    validate_sha256(artifact_sha256)
    if not isinstance(grader_resources, ResourceUsage):
        raise TypeError("grader_resources must be ResourceUsage")

    expected_by_id = {case.case_id: case for case in plan.cases}
    observed_by_id: dict[str, CaseObservation] = {}
    for observation in observations:
        if not isinstance(observation, CaseObservation):
            raise TypeError("observations must contain CaseObservation instances")
        if observation.case_id in observed_by_id:
            raise ValueError(f"duplicate observation for case {observation.case_id!r}")
        observed_by_id[observation.case_id] = observation
    if set(observed_by_id) != set(expected_by_id):
        missing = set(expected_by_id).difference(observed_by_id)
        extra = set(observed_by_id).difference(expected_by_id)
        raise ValueError(
            f"observation matrix mismatch: missing={len(missing)}, extra={len(extra)}"
        )

    correct = 0
    valid = 0
    for case in plan.cases:
        observation = observed_by_id[case.case_id]
        if observation.runtime_input_sha256 != case.runtime_input_sha256:
            raise ValueError(
                f"runtime input identity differs for case {case.case_id!r}"
            )
        if not observation.execution_valid:
            continue
        valid += 1
        observed = store.get_bytes(observation.observed_output_sha256)
        expected = store.get_bytes(case.expected_output_sha256)
        if plan.comparison_mode is ComparisonMode.EXACT_BYTES:
            if observed == expected:
                correct += 1
        else:
            raise AssertionError("unsupported comparison mode bypassed validation")

    case_count = len(plan.cases)
    exact_accuracy = correct / case_count
    valid_rate = valid / case_count
    qualified = exact_accuracy >= float(plan.evaluator.pass_threshold)

    return EvaluationRecord(
        artifact_sha256=artifact_sha256,
        task=plan.task,
        evaluator_id=plan.evaluator.evaluator_id,
        evaluator_configuration_sha256=plan.evaluator.evaluator_configuration_sha256,
        evaluator_software_revision=plan.evaluator.evaluator_software_revision,
        visibility=EvaluationVisibility.PROTECTED,
        metrics=(
            MetricValue("exact_accuracy", exact_accuracy),
            MetricValue("valid_rate", valid_rate),
        ),
        qualified=qualified,
        resources=grader_resources,
    )
