"""Deterministic repair for the failed candidate-pool v3 calibration-pack qualification.

The first v3 pack qualification attempt at ``FAILED_PACK_REVISION_V3`` stopped
before Docker grading or candidate inference because two API-contract protected
runtime inputs canonicalized to exactly the same bytes as their expected outputs.
``ProtectedCase`` intentionally forbids that aliasing.

This module preserves that failed evidence and repairs only the two protected
runtime inputs by adding ignored request metadata. Solver-visible prompts, buggy
and clean repositories, issues, public cases, gold repairs, task IDs, seeds, and
defect families remain unchanged. Qualification must use a new artifact root;
the failed ``c3q`` root is never reused or deleted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Sequence

from .candidate_pool_v3_full_file import gold_full_file_output_v3, solver_prompt_transport_v3
from .candidate_pool_v3_representation_protocol import (
    EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256,
    V3_DEVELOPMENT_CANDIDATE_IDS,
    validate_v3_representation_protocol,
)
from .content_store import FileContentStore
from .qualified_docker import QUALIFIED_DOCKER, probe_qualified_docker_configuration
from .repository_surgery_calibration_matrix import _evaluate_patch, _metric, build_matrix_material
from .repository_surgery_calibration_pack_v3 import (
    CALIBRATION_SEEDS_V3,
    CALIBRATION_TASK_IDS_V3,
    CalibrationPackEntryV3,
    CalibrationTaskQualificationV3,
    _canonical_json_bytes,
    calibration_blueprints_v3,
    validate_calibration_pack_v3_freshness,
)

FAILED_PACK_REVISION_V3 = "2fd0654aae7f4f8a336b509e3b6247833ee3b54f"
FAILED_QUALIFICATION_EXCEPTION_V3 = (
    "ValueError: runtime input and expected output must be distinct artifacts"
)
REPAIR_KIND_V3 = "protected-runtime-input-distinctness-metadata-v1"
REPAIRED_PACK_SCHEMA_V3 = "plural-cognition-repository-surgery-calibration-pack-v3-repair-v1"
REPAIRED_QUALIFICATION_SCHEMA_V3 = (
    "plural-cognition-repository-surgery-calibration-qualification-v3-repair-v1"
)
EXPECTED_ORIGINAL_COLLISION_CASES_V3 = (
    "repository-surgery-calibration-v3-api-contract-0001/case-01-explicit",
    "repository-surgery-calibration-v3-api-contract-0001/case-04-other",
)


def _json_line(payload: Any) -> bytes:
    return _canonical_json_bytes(payload) + b"\n"


def original_collision_case_ids_v3() -> tuple[str, ...]:
    collisions: list[str] = []
    for blueprint in calibration_blueprints_v3():
        for case_id, runtime_input, expected_output in blueprint.protected_cases:
            if _json_line(runtime_input) == _json_line(expected_output):
                collisions.append(f"{blueprint.task_id}/{case_id}")
    return tuple(collisions)


def repaired_calibration_blueprints_v3():
    blueprints = list(calibration_blueprints_v3())
    api = blueprints[0]
    repaired_cases = []
    for case_id, runtime_input, expected_output in api.protected_cases:
        new_input = dict(runtime_input)
        if case_id == "case-01-explicit":
            new_input["request_id"] = "explicit"
        elif case_id == "case-04-other":
            new_input["request_id"] = "other"
        repaired_cases.append((case_id, new_input, expected_output))
    blueprints[0] = replace(api, protected_cases=tuple(repaired_cases))
    return tuple(blueprints)


def repair_record_payload_v3() -> dict[str, Any]:
    return {
        "schema": "plural-cognition-repository-surgery-calibration-pack-v3-repair-record-v1",
        "failed_pack_revision": FAILED_PACK_REVISION_V3,
        "failed_exception": FAILED_QUALIFICATION_EXCEPTION_V3,
        "repair_kind": REPAIR_KIND_V3,
        "original_collision_cases": list(EXPECTED_ORIGINAL_COLLISION_CASES_V3),
        "candidate_model_calls_consumed_before_repair": 0,
        "selection_evidence_observed_before_repair": False,
        "failed_artifact_root_policy": "preserve-c3q-and-use-new-root",
        "solver_visible_task_semantics_changed": False,
        "protected_runtime_inputs_changed": True,
        "protected_expected_outputs_changed": False,
    }


def repair_record_sha256_v3() -> str:
    return hashlib.sha256(_canonical_json_bytes(repair_record_payload_v3())).hexdigest()


def validate_repaired_calibration_pack_v3() -> None:
    validate_v3_representation_protocol()
    validate_calibration_pack_v3_freshness()
    if original_collision_case_ids_v3() != EXPECTED_ORIGINAL_COLLISION_CASES_V3:
        raise RuntimeError(
            "unexpected original protected input/output collision set: "
            + repr(original_collision_case_ids_v3())
        )

    original = calibration_blueprints_v3()
    repaired = repaired_calibration_blueprints_v3()
    if len(original) != len(repaired) or tuple(x.task_id for x in repaired) != CALIBRATION_TASK_IDS_V3:
        raise RuntimeError("repaired v3 calibration task identities drifted")
    if tuple(x.generation_seed for x in repaired) != CALIBRATION_SEEDS_V3:
        raise RuntimeError("repaired v3 calibration seeds drifted")

    for before, after in zip(original, repaired, strict=True):
        if before.task_id != after.task_id:
            raise RuntimeError("repair changed task ID")
        if before.mutation_kind != after.mutation_kind:
            raise RuntimeError(f"repair changed mutation kind: {before.task_id}")
        if before.clean_files != after.clean_files or before.buggy_files != after.buggy_files:
            raise RuntimeError(f"repair changed repository bytes: {before.task_id}")
        if before.gold_patch != after.gold_patch:
            raise RuntimeError(f"repair changed gold patch: {before.task_id}")
        if before.issue_prompt != after.issue_prompt or before.public_cases != after.public_cases:
            raise RuntimeError(f"repair changed solver-visible task text/cases: {before.task_id}")
        if before.mutation_configuration != after.mutation_configuration:
            raise RuntimeError(f"repair changed mutation configuration: {before.task_id}")
        if solver_prompt_transport_v3(before) != solver_prompt_transport_v3(after):
            raise RuntimeError(f"repair changed v3 solver prompt: {before.task_id}")
        if gold_full_file_output_v3(before) != gold_full_file_output_v3(after):
            raise RuntimeError(f"repair changed v3 gold whole-file output: {before.task_id}")
        for case_id, runtime_input, expected_output in after.protected_cases:
            if _json_line(runtime_input) == _json_line(expected_output):
                raise RuntimeError(
                    f"protected runtime input still aliases expected output: {after.task_id}/{case_id}"
                )

    changed = []
    for before, after in zip(original, repaired, strict=True):
        for old_case, new_case in zip(before.protected_cases, after.protected_cases, strict=True):
            if old_case != new_case:
                changed.append(f"{before.task_id}/{old_case[0]}")
                if old_case[0] != new_case[0] or old_case[2] != new_case[2]:
                    raise RuntimeError("repair changed protected case identity or expectation")
    if tuple(changed) != EXPECTED_ORIGINAL_COLLISION_CASES_V3:
        raise RuntimeError(f"repair changed unexpected protected cases: {changed!r}")


@dataclass(frozen=True, slots=True)
class RepairedCalibrationQualificationReportV3:
    software_revision: str
    entries: tuple[CalibrationPackEntryV3, ...]
    qualifications: tuple[CalibrationTaskQualificationV3, ...]

    def pack_payload(self) -> dict[str, Any]:
        return {
            "schema": REPAIRED_PACK_SCHEMA_V3,
            "representation_protocol_sha256": EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256,
            "repair_record_sha256": repair_record_sha256_v3(),
            "failed_pack_revision": FAILED_PACK_REVISION_V3,
            "task_count": len(self.entries),
            "candidate_ids": list(V3_DEVELOPMENT_CANDIDATE_IDS),
            "tasks": [item.payload() for item in self.entries],
            "selection_evidence": False,
        }

    @property
    def pack_sha256(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.pack_payload())).hexdigest()

    def payload(self) -> dict[str, Any]:
        return {
            "schema": REPAIRED_QUALIFICATION_SCHEMA_V3,
            "software_revision": self.software_revision,
            "representation_protocol_sha256": EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256,
            "repair_record_sha256": repair_record_sha256_v3(),
            "failed_pack_revision": FAILED_PACK_REVISION_V3,
            "calibration_pack_sha256": self.pack_sha256,
            "qualified_docker_report_sha256": QUALIFIED_DOCKER.report_sha256,
            "task_count": len(self.entries),
            "candidate_ids": list(V3_DEVELOPMENT_CANDIDATE_IDS),
            "tasks": [item.payload() for item in self.entries],
            "qualifications": [item.payload() for item in self.qualifications],
            "candidate_model_inference_performed": False,
            "calibration_candidate_outcomes_observed": False,
            "selection_outcomes_observed": False,
            "selection_evidence": False,
            "failed_artifact_root_reused": False,
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.payload())).hexdigest()


def run_repaired_calibration_pack_v3_qualification(
    *, artifact_root: Path, software_revision: str, docker_executable: str = "docker"
) -> RepairedCalibrationQualificationReportV3:
    validate_repaired_calibration_pack_v3()
    artifact_root = Path(artifact_root)
    if artifact_root.exists() and any(artifact_root.iterdir()):
        raise ValueError("repaired artifact_root must be absent or empty")
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
    entries: list[CalibrationPackEntryV3] = []
    qualifications: list[CalibrationTaskQualificationV3] = []

    for blueprint in repaired_calibration_blueprints_v3():
        material = build_matrix_material(
            blueprint=blueprint,
            store=store,
            work_root=build_root / blueprint.task_id,
            software_revision=software_revision,
        )
        entries.append(
            CalibrationPackEntryV3(
                task_id=blueprint.task_id,
                mutation_kind=blueprint.mutation_kind.value,
                task_sha256=material.visible_task.sha256,
                generation_record_sha256=material.generation_record.sha256,
                evaluation_plan_sha256=material.evaluation_plan.sha256,
                solver_prompt_sha256=hashlib.sha256(
                    solver_prompt_transport_v3(blueprint)
                ).hexdigest(),
            )
        )
        baseline_submission_sha256 = store.put_bytes(
            _canonical_json_bytes(
                {
                    "schema": "project-authored-calibration-pack-baseline-v3-repair-v1",
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
        baseline_exact = _metric(baseline, "exact_accuracy")
        gold_exact = _metric(gold, "exact_accuracy")
        baseline_valid = _metric(baseline, "valid_rate")
        gold_valid = _metric(gold, "valid_rate")
        if baseline_exact >= 1.0:
            raise RuntimeError(
                f"repaired v3 calibration baseline is not observably defective: {blueprint.task_id}"
            )
        if gold_exact != 1.0 or gold_valid != 1.0 or not gold.qualified:
            raise RuntimeError(
                f"repaired v3 calibration gold repair did not fully qualify: {blueprint.task_id}"
            )
        qualifications.append(
            CalibrationTaskQualificationV3(
                task_id=blueprint.task_id,
                baseline_evaluation_sha256=baseline.sha256,
                gold_evaluation_sha256=gold.sha256,
                baseline_exact_accuracy=baseline_exact,
                gold_exact_accuracy=gold_exact,
                baseline_valid_rate=baseline_valid,
                gold_valid_rate=gold_valid,
            )
        )

    report = RepairedCalibrationQualificationReportV3(
        software_revision=software_revision,
        entries=tuple(entries),
        qualifications=tuple(qualifications),
    )
    (artifact_root / "calibration-pack-v3-repair.json").write_bytes(
        _canonical_json_bytes(report.pack_payload()) + b"\n"
    )
    (artifact_root / "calibration-qualification-v3-repair.json").write_bytes(
        _canonical_json_bytes(report.payload()) + b"\n"
    )
    (artifact_root / "calibration-pack-v3-repair-record.json").write_bytes(
        _canonical_json_bytes(repair_record_payload_v3()) + b"\n"
    )

    print("status=CALIBRATION_PACK_V3_REPAIR_QUALIFIED")
    print(f"failed_pack_revision={FAILED_PACK_REVISION_V3}")
    print(f"repair_record_sha256={repair_record_sha256_v3()}")
    print(f"representation_protocol_sha256={EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256}")
    print(f"calibration_pack_sha256={report.pack_sha256}")
    print(f"qualification_report_sha256={report.sha256}")
    print(f"qualified_docker_report_sha256={QUALIFIED_DOCKER.report_sha256}")
    print(f"task_count={len(report.entries)}")
    print("candidate_ids=" + ",".join(V3_DEVELOPMENT_CANDIDATE_IDS))
    print("candidate_model_inference_performed=False")
    print("calibration_candidate_outcomes_observed=False")
    print("selection_outcomes_observed=False")
    print("failed_artifact_root_reused=False")
    for item in report.qualifications:
        print(
            "task=" + item.task_id
            + f" baseline_exact={item.baseline_exact_accuracy:.6f}"
            + f" gold_exact={item.gold_exact_accuracy:.6f}"
            + f" baseline_valid={item.baseline_valid_rate:.6f}"
            + f" gold_valid={item.gold_valid_rate:.6f}"
        )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--docker-executable", default="docker")
    args = parser.parse_args(argv)
    run_repaired_calibration_pack_v3_qualification(
        artifact_root=Path(args.artifact_root),
        software_revision=args.software_revision,
        docker_executable=args.docker_executable,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
