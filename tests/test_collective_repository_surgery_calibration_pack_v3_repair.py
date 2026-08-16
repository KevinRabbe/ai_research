import hashlib

from plural_cognition.collective.candidate_pool_v3_full_file import (
    gold_full_file_output_v3,
    solver_prompt_transport_v3,
)
from plural_cognition.collective.repository_surgery_calibration_pack_v3 import (
    CALIBRATION_SEEDS_V3,
    CALIBRATION_TASK_IDS_V3,
    _canonical_json_bytes,
    calibration_blueprints_v3,
)
from plural_cognition.collective.repository_surgery_calibration_pack_v3_repair import (
    EXPECTED_ORIGINAL_COLLISION_CASES_V3,
    FAILED_PACK_REVISION_V3,
    FAILED_QUALIFICATION_EXCEPTION_V3,
    REPAIR_KIND_V3,
    REPAIRED_PACK_SCHEMA_V3,
    REPAIRED_QUALIFICATION_SCHEMA_V3,
    RepairedCalibrationQualificationReportV3,
    original_collision_case_ids_v3,
    repair_record_payload_v3,
    repair_record_sha256_v3,
    repaired_calibration_blueprints_v3,
    validate_repaired_calibration_pack_v3,
)


def _json_line(payload):
    return _canonical_json_bytes(payload) + b"\n"


def test_failed_pack_collision_set_is_exact_and_reproducible() -> None:
    assert FAILED_PACK_REVISION_V3 == "2fd0654aae7f4f8a336b509e3b6247833ee3b54f"
    assert FAILED_QUALIFICATION_EXCEPTION_V3 == (
        "ValueError: runtime input and expected output must be distinct artifacts"
    )
    assert original_collision_case_ids_v3() == EXPECTED_ORIGINAL_COLLISION_CASES_V3
    assert EXPECTED_ORIGINAL_COLLISION_CASES_V3 == (
        "repository-surgery-calibration-v3-api-contract-0001/case-01-explicit",
        "repository-surgery-calibration-v3-api-contract-0001/case-04-other",
    )


def test_repair_changes_only_two_protected_runtime_inputs() -> None:
    original = calibration_blueprints_v3()
    repaired = repaired_calibration_blueprints_v3()

    assert tuple(item.task_id for item in repaired) == CALIBRATION_TASK_IDS_V3
    assert tuple(item.generation_seed for item in repaired) == CALIBRATION_SEEDS_V3

    changed = []
    for before, after in zip(original, repaired, strict=True):
        assert before.task_id == after.task_id
        assert before.mutation_kind == after.mutation_kind
        assert before.clean_files == after.clean_files
        assert before.buggy_files == after.buggy_files
        assert before.gold_patch == after.gold_patch
        assert before.issue_prompt == after.issue_prompt
        assert before.public_cases == after.public_cases
        assert before.mutation_configuration == after.mutation_configuration
        assert solver_prompt_transport_v3(before) == solver_prompt_transport_v3(after)
        assert gold_full_file_output_v3(before) == gold_full_file_output_v3(after)

        for old_case, new_case in zip(before.protected_cases, after.protected_cases, strict=True):
            if old_case != new_case:
                changed.append(f"{before.task_id}/{old_case[0]}")
                assert old_case[0] == new_case[0]
                assert old_case[2] == new_case[2]

    assert tuple(changed) == EXPECTED_ORIGINAL_COLLISION_CASES_V3


def test_repaired_protected_inputs_never_alias_expectations() -> None:
    validate_repaired_calibration_pack_v3()
    for blueprint in repaired_calibration_blueprints_v3():
        for _case_id, runtime_input, expected_output in blueprint.protected_cases:
            assert _json_line(runtime_input) != _json_line(expected_output)


def test_repair_record_is_canonical_and_zero_inference() -> None:
    payload = repair_record_payload_v3()
    assert payload["repair_kind"] == REPAIR_KIND_V3
    assert payload["failed_pack_revision"] == FAILED_PACK_REVISION_V3
    assert payload["candidate_model_calls_consumed_before_repair"] == 0
    assert payload["selection_evidence_observed_before_repair"] is False
    assert payload["failed_artifact_root_policy"] == "preserve-c3q-and-use-new-root"
    assert payload["solver_visible_task_semantics_changed"] is False
    assert payload["protected_runtime_inputs_changed"] is True
    assert payload["protected_expected_outputs_changed"] is False
    expected = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    assert repair_record_sha256_v3() == expected


def test_repaired_report_schema_preserves_nonselection_status() -> None:
    report = RepairedCalibrationQualificationReportV3(
        software_revision="a" * 40,
        entries=(),
        qualifications=(),
    )
    pack = report.pack_payload()
    qualification = report.payload()

    assert pack["schema"] == REPAIRED_PACK_SCHEMA_V3
    assert qualification["schema"] == REPAIRED_QUALIFICATION_SCHEMA_V3
    assert pack["selection_evidence"] is False
    assert qualification["candidate_model_inference_performed"] is False
    assert qualification["calibration_candidate_outcomes_observed"] is False
    assert qualification["selection_outcomes_observed"] is False
    assert qualification["selection_evidence"] is False
    assert qualification["failed_artifact_root_reused"] is False
