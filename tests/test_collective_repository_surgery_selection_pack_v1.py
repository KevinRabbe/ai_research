from __future__ import annotations

from pathlib import Path

from plural_cognition.collective.content_store import FileContentStore
from plural_cognition.collective.local_operational_freeze_v1 import (
    FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1,
)
from plural_cognition.collective.local_raw_calibration import validate_patch_against_blueprint
from plural_cognition.collective.repository_surgery import MutationKind
from plural_cognition.collective.repository_surgery_calibration_matrix import calibration_blueprints
from plural_cognition.collective.repository_surgery_selection_pack_v1 import (
    SELECTION_TASK_COUNT,
    build_selection_material,
    selection_blueprints,
)
from plural_cognition.collective.tasks import TaskSplit


def test_selection_pack_is_balanced_and_disjoint_from_calibration() -> None:
    items = selection_blueprints()
    assert len(items) == SELECTION_TASK_COUNT == 12
    ids = tuple(item.task_id for item in items)
    assert ids == tuple(sorted(ids))
    assert len(set(ids)) == 12
    assert set(ids).isdisjoint(item.task_id for item in calibration_blueprints())

    expected = {
        MutationKind.API_CONTRACT,
        MutationKind.BOUNDARY,
        MutationKind.ERROR_HANDLING,
        MutationKind.LOCAL_LOGIC,
        MutationKind.MULTI_FILE_BEHAVIOR,
        MutationKind.STATE_MANAGEMENT,
    }
    counts = {kind: 0 for kind in expected}
    for item in items:
        counts[item.mutation_kind] += 1
    assert counts == {kind: 2 for kind in expected}


def test_selection_gold_patches_apply_strictly_without_model_output_repair() -> None:
    for blueprint in selection_blueprints():
        validate_patch_against_blueprint(blueprint.gold_patch, blueprint)


def test_selection_material_binds_selection_split_and_final_operational_freeze(
    tmp_path: Path,
) -> None:
    store = FileContentStore(tmp_path / "store")
    material = build_selection_material(
        blueprint=selection_blueprints()[0],
        store=store,
        work_root=tmp_path / "work",
        software_revision="1" * 40,
    )
    assert material.visible_task.split is TaskSplit.SELECTION
    assert material.generation_record.split is TaskSplit.SELECTION
    assert material.generation_record.binds(material.visible_task)
    assert material.evaluation_plan.evaluator.binds(material.visible_task)
    assert FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.sha256 == (
        "448f72a61f320017138b5222cfed4673d001478e17bb7bc21185e04e8874066f"
    )


def test_selection_prompts_do_not_contain_output_protocol_tuning() -> None:
    forbidden = (b"unified diff", b"markdown", b"json object", b"edits")
    for blueprint in selection_blueprints():
        lowered = blueprint.issue_prompt.lower()
        assert not any(token in lowered for token in forbidden)
