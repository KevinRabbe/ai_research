from __future__ import annotations

import hashlib
from collections import Counter

from plural_cognition.collective import repository_surgery_selection_pack_v3 as v3
from plural_cognition.collective.candidate_pool_v3_full_file import (
    OUTPUT_CONTRACT_V3,
    extract_full_file_patch_v3,
    gold_full_file_output_v3,
    solver_prompt_transport_v3,
)
from plural_cognition.collective.repository_surgery import MutationKind
from plural_cognition.collective.repository_surgery_calibration_matrix import calibration_blueprints
from plural_cognition.collective.repository_surgery_calibration_pack_v3_repair import repaired_calibration_blueprints_v3
from plural_cognition.collective.repository_surgery_selection_pack_v1 import selection_blueprints as selection_blueprints_v1
from plural_cognition.collective.repository_surgery_selection_pack_v2 import selection_blueprints_v2


def test_v3_selection_pack_exact_balanced_fresh_matrix() -> None:
    tasks = v3.selection_blueprints_v3()
    assert len(tasks) == 12
    assert tuple(item.task_id for item in tasks) == tuple(sorted(item.task_id for item in tasks))
    assert tuple(item.generation_seed for item in tasks) == tuple(range(401, 413))
    counts = Counter(item.mutation_kind for item in tasks)
    assert counts == {
        MutationKind.API_CONTRACT: 2,
        MutationKind.BOUNDARY: 2,
        MutationKind.ERROR_HANDLING: 2,
        MutationKind.LOCAL_LOGIC: 2,
        MutationKind.MULTI_FILE_BEHAVIOR: 2,
        MutationKind.STATE_MANAGEMENT: 2,
    }
    legacy = (
        *calibration_blueprints(),
        *selection_blueprints_v1(),
        *selection_blueprints_v2(),
        *repaired_calibration_blueprints_v3(),
    )
    assert {item.task_id for item in tasks}.isdisjoint(item.task_id for item in legacy)
    assert {item.generation_seed for item in tasks}.isdisjoint(item.generation_seed for item in legacy)
    assert {v3._content_fingerprint(item) for item in tasks}.isdisjoint(
        v3._content_fingerprint(item) for item in legacy
    )


def test_v3_selection_pack_binds_exact_frozen_population_and_thresholds() -> None:
    assert v3.V3_FROZEN_POPULATION_CANDIDATE_IDS == (
        "qwen2.5-coder-14b-q5km",
        "devstral-24b-q4km",
        "gpt-oss-20b-mxfp4",
        "qwen3-14b-q5km",
    )
    assert v3.V3_SELECTION_POPULATION_SIZE == 4
    assert v3.V3_SELECTION_MIN_VALID_RATE == 0.95
    assert v3.EXPECTED_EXPANSION_CALIBRATION_OUTCOME_FREEZE_SHA256_V3 == (
        "d39b2d3da6d156485e957e8e37f7eb2e961364e45c936fd15b673f67ecc61f12"
    )


def test_v3_selection_gold_outputs_parse_to_exact_gold_patches() -> None:
    for blueprint in v3.selection_blueprints_v3():
        prompt = solver_prompt_transport_v3(blueprint)
        assert b"ALLOWED_FILE_PATHS" in prompt
        assert b"relative/file.py" not in prompt
        assert b"FILE relative/" not in prompt
        for path, _raw in blueprint.buggy_files:
            assert f"- {path}".encode("utf-8") in prompt
        gold_output = gold_full_file_output_v3(blueprint)
        patch, parse_mode = extract_full_file_patch_v3(gold_output, blueprint)
        assert parse_mode == OUTPUT_CONTRACT_V3
        assert patch == blueprint.gold_patch
        assert hashlib.sha256(patch).hexdigest() == hashlib.sha256(blueprint.gold_patch).hexdigest()


def test_v3_selection_multi_file_gold_changes_both_files() -> None:
    multi = [item for item in v3.selection_blueprints_v3() if item.mutation_kind is MutationKind.MULTI_FILE_BEHAVIOR]
    assert len(multi) == 2
    for blueprint in multi:
        assert len(blueprint.clean_files) == 2
        assert len(blueprint.buggy_files) == 2
        changed = [
            path
            for (path, clean), (_, buggy) in zip(blueprint.clean_files, blueprint.buggy_files, strict=True)
            if clean != buggy
        ]
        assert len(changed) == 2
        output = gold_full_file_output_v3(blueprint).decode("utf-8")
        for path in changed:
            assert f"FILE {path}\n<<<<<<< CONTENT\n" in output


def test_v3_selection_freshness_validator_and_schemas() -> None:
    v3.validate_selection_pack_v3_freshness()
    assert v3.SELECTION_PACK_SCHEMA_V3 == "plural-cognition-repository-surgery-selection-pack-v3"
    assert v3.SELECTION_QUALIFICATION_SCHEMA_V3 == "plural-cognition-repository-surgery-selection-qualification-v3"
    assert v3.SELECTION_QUALIFICATION_ARTIFACT_ROOT_V3 == "artifacts/capable-collective/s3q"


def test_v3_selection_qualification_payload_cannot_claim_model_outcomes() -> None:
    entries = tuple(
        v3.SelectionPackEntryV3(
            task_id=blueprint.task_id,
            mutation_kind=blueprint.mutation_kind.value,
            generation_seed=blueprint.generation_seed,
            task_sha256=f"{index + 1:064x}",
            generation_record_sha256=f"{index + 101:064x}",
            evaluation_plan_sha256=f"{index + 201:064x}",
            solver_prompt_sha256=f"{index + 301:064x}",
            gold_output_sha256=f"{index + 401:064x}",
            gold_patch_sha256=f"{index + 501:064x}",
        )
        for index, blueprint in enumerate(v3.selection_blueprints_v3())
    )
    qualifications = tuple(
        v3.SelectionTaskQualificationV3(
            task_id=item.task_id,
            baseline_evaluation_sha256=f"{index + 601:064x}",
            gold_evaluation_sha256=f"{index + 701:064x}",
            baseline_exact_accuracy=0.0,
            gold_exact_accuracy=1.0,
            baseline_valid_rate=1.0,
            gold_valid_rate=1.0,
            gold_parse_mode=OUTPUT_CONTRACT_V3,
            parsed_gold_patch_sha256=item.gold_patch_sha256,
        )
        for index, item in enumerate(entries)
    )
    report = v3.SelectionQualificationReportV3(
        software_revision="a" * 40,
        entries=entries,
        qualifications=qualifications,
    )
    payload = report.payload()
    assert payload["candidate_model_inference_performed"] is False
    assert payload["selection_outcomes_observed"] is False
    assert payload["selection_evidence"] is False
    assert payload["candidate_ids"] == [
        "qwen2.5-coder-14b-q5km",
        "devstral-24b-q4km",
        "gpt-oss-20b-mxfp4",
        "qwen3-14b-q5km",
    ]
    assert payload["task_count"] == 12
    assert report.pack_payload()["min_valid_rate"] == 0.95
    assert report.pack_payload()["population_size"] == 4
