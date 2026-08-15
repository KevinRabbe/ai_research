from __future__ import annotations

from collections import Counter

from plural_cognition.collective.candidate_pool_v2_full_file import gold_full_file_output_v2
from plural_cognition.collective.local_raw_calibration import validate_patch_against_blueprint
from plural_cognition.collective.repository_surgery import MutationKind
from plural_cognition.collective.repository_surgery_calibration_matrix import calibration_blueprints
from plural_cognition.collective.repository_surgery_selection_pack_v1 import selection_blueprints as selection_blueprints_v1
from plural_cognition.collective.repository_surgery_selection_pack_v2 import (
    build_solver_prompt_selection_v2,
    selection_blueprints_v2,
    solver_prompt_transport_selection_v2,
    validate_selection_pack_v2_freshness,
)
from plural_cognition.collective.candidate_pool_v2_full_file import extract_full_file_patch_v2


def test_v2_selection_pack_is_fresh_balanced_twelve_task_split() -> None:
    validate_selection_pack_v2_freshness()
    tasks = selection_blueprints_v2()
    assert len(tasks) == 12
    ids = tuple(item.task_id for item in tasks)
    assert ids == tuple(sorted(ids))
    assert not set(ids).intersection(item.task_id for item in calibration_blueprints())
    assert not set(ids).intersection(item.task_id for item in selection_blueprints_v1())
    assert tuple(item.generation_seed for item in tasks) == tuple(range(201, 213))
    counts = Counter(item.mutation_kind for item in tasks)
    for kind in (
        MutationKind.API_CONTRACT,
        MutationKind.BOUNDARY,
        MutationKind.ERROR_HANDLING,
        MutationKind.LOCAL_LOGIC,
        MutationKind.MULTI_FILE,
        MutationKind.STATE_MANAGEMENT,
    ):
        assert counts[kind] == 2


def test_v2_selection_prompts_use_only_whole_file_contract() -> None:
    for task in selection_blueprints_v2():
        prompt = build_solver_prompt_selection_v2(task)
        assert prompt.endswith(b"\n")
        assert b"FILE relative/file.py" in prompt
        assert b"<<<<<<< CONTENT" in prompt
        assert b">>>>>>> CONTENT" in prompt
        assert b"complete corrected file" in prompt
        assert b"unified diff" not in prompt.lower()
        assert b"```" not in prompt
        transported = solver_prompt_transport_selection_v2(task)
        assert transported == prompt[:-1]
        assert not transported.endswith(b"\n")


def test_v2_selection_gold_whole_file_outputs_round_trip_to_valid_repairs() -> None:
    for task in selection_blueprints_v2():
        raw = gold_full_file_output_v2(task)
        patch, mode = extract_full_file_patch_v2(raw, task)
        assert mode == "raw-full-file-replacement"
        validate_patch_against_blueprint(patch, task)


def test_v2_selection_multi_file_tasks_really_require_two_changed_files() -> None:
    tasks = [item for item in selection_blueprints_v2() if item.mutation_kind is MutationKind.MULTI_FILE]
    assert len(tasks) == 2
    for task in tasks:
        clean = dict(task.clean_files)
        buggy = dict(task.buggy_files)
        changed = [path for path in clean if clean[path] != buggy[path]]
        assert len(changed) == 2
        raw = gold_full_file_output_v2(task)
        assert raw.count(b"FILE ") == 2
