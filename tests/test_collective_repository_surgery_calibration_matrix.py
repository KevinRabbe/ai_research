from __future__ import annotations

import pytest

from plural_cognition.collective.content_store import FileContentStore
from plural_cognition.collective.docker_bootstrap import apply_unified_diff
from plural_cognition.collective.repository import (
    load_repository_snapshot,
    materialize_repository_snapshot,
    snapshot_directory,
)
from plural_cognition.collective.repository_surgery import MutationKind
from plural_cognition.collective.repository_surgery_calibration_matrix import (
    CalibrationMatrixReport,
    CalibrationMatrixTaskReport,
    build_matrix_material,
    calibration_blueprints,
)
from plural_cognition.collective.tasks import TaskSplit

REVISION = "a" * 40


def _task_report(task_id: str) -> CalibrationMatrixTaskReport:
    return CalibrationMatrixTaskReport(
        task_id=task_id,
        mutation_kind=MutationKind.BOUNDARY.value,
        task_sha256="1" * 64,
        generation_record_sha256="2" * 64,
        evaluation_plan_sha256="3" * 64,
        baseline_evaluation_sha256="4" * 64,
        gold_evaluation_sha256="5" * 64,
        baseline_exact_accuracy=0.75,
        gold_exact_accuracy=1.0,
        baseline_valid_rate=1.0,
        gold_valid_rate=1.0,
    )


def test_calibration_matrix_blueprints_cover_distinct_defect_classes() -> None:
    blueprints = calibration_blueprints()
    assert tuple(item.task_id for item in blueprints) == tuple(
        sorted(item.task_id for item in blueprints)
    )
    assert {item.mutation_kind for item in blueprints} == {
        MutationKind.BOUNDARY,
        MutationKind.LOCAL_LOGIC,
        MutationKind.API_CONTRACT,
        MutationKind.MULTI_FILE_BEHAVIOR,
        MutationKind.STATE_MANAGEMENT,
        MutationKind.ERROR_HANDLING,
    }
    assert len(blueprints) == 6
    assert len({item.generation_seed for item in blueprints}) == len(blueprints)


def test_each_matrix_task_is_bound_and_gold_patch_restores_clean_tree(tmp_path) -> None:
    store = FileContentStore(tmp_path / "store")
    for blueprint in calibration_blueprints():
        material = build_matrix_material(
            blueprint=blueprint,
            store=store,
            work_root=tmp_path / "build" / blueprint.task_id,
            software_revision=REVISION,
        )

        assert material.visible_task.split is TaskSplit.CALIBRATION
        assert material.generation_record.mutation_kind is blueprint.mutation_kind
        assert material.generation_record.binds(material.visible_task)
        assert material.evaluation_plan.task == material.visible_task.task
        assert material.evaluation_plan.evaluator.pass_threshold == 1.0
        assert len(material.evaluation_plan.cases) == 4
        assert material.generation_record.clean_repository_sha256 != material.generation_record.buggy_repository_sha256

        rendered_visible = str(material.visible_task.canonical_payload())
        assert material.generation_record.protected_expectations_sha256 not in rendered_visible
        assert material.generation_record.gold_patch_sha256 not in rendered_visible

        buggy = load_repository_snapshot(
            material.generation_record.buggy_repository_sha256,
            store,
        )
        repaired_root = tmp_path / "repaired" / blueprint.task_id
        materialize_repository_snapshot(buggy, repaired_root, store)
        apply_unified_diff(
            repaired_root,
            store.get_bytes(material.gold_submission.patch_sha256),
        )
        repaired = snapshot_directory(repaired_root, store)
        assert repaired.manifest_sha256 == material.generation_record.clean_repository_sha256


def test_matrix_material_is_deterministic_for_same_revision(tmp_path) -> None:
    blueprint = calibration_blueprints()[0]
    store_a = FileContentStore(tmp_path / "store-a")
    store_b = FileContentStore(tmp_path / "store-b")
    first = build_matrix_material(
        blueprint=blueprint,
        store=store_a,
        work_root=tmp_path / "first",
        software_revision=REVISION,
    )
    second = build_matrix_material(
        blueprint=blueprint,
        store=store_b,
        work_root=tmp_path / "second",
        software_revision=REVISION,
    )

    assert first.visible_task.sha256 == second.visible_task.sha256
    assert first.generation_record.sha256 == second.generation_record.sha256
    assert first.evaluation_plan.sha256 == second.evaluation_plan.sha256
    assert first.gold_submission.sha256 == second.gold_submission.sha256


def test_matrix_report_requires_sorted_unique_tasks() -> None:
    a = _task_report("a")
    b = _task_report("b")
    report = CalibrationMatrixReport(software_revision=REVISION, tasks=(a, b))
    assert report.canonical_payload()["task_count"] == 2
    assert len(report.sha256) == 64

    with pytest.raises(ValueError, match="sorted"):
        CalibrationMatrixReport(software_revision=REVISION, tasks=(b, a))
    with pytest.raises(ValueError, match="sorted"):
        CalibrationMatrixReport(software_revision=REVISION, tasks=(a, a))
