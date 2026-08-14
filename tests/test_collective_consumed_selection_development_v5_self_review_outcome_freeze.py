from plural_cognition.collective.consumed_selection_development_v5_self_review_outcome_freeze import (
    EXPECTED_V5_SELF_REVIEW_OUTCOME_FREEZE_SHA256,
    FINAL_CONSUMED_SELECTION_DEVELOPMENT_V5_SELF_REVIEW_OUTCOME_FREEZE_SHA256,
    V5_DEVELOPMENT_PROTOCOL_SHA256,
    V5_FAILED_RECOVERY_ROOT_MANIFEST_SHA256,
    V5_ORIGINAL_SOFTWARE_REVISION,
    V5_PARTIAL_ROOT_MANIFEST_SHA256,
    V5_RECOVERY_OUTPUT_MANIFEST_SHA256,
    V5_RECOVERY_REPORT_SHA256,
    V5_RECOVERY_SOFTWARE_REVISION,
    consumed_selection_development_v5_self_review_outcome_payload,
)


def test_v5_self_review_outcome_freeze_identity_is_exact() -> None:
    assert (
        FINAL_CONSUMED_SELECTION_DEVELOPMENT_V5_SELF_REVIEW_OUTCOME_FREEZE_SHA256
        == EXPECTED_V5_SELF_REVIEW_OUTCOME_FREEZE_SHA256
        == "738d1e633c767f09f5d11c46e71eb7e552adfe424b93b826f3834380af7af58d"
    )


def test_v5_self_review_outcome_freeze_binds_recovered_evidence() -> None:
    payload = consumed_selection_development_v5_self_review_outcome_payload()
    assert payload["scientific_status"] == "development-only-consumed-split-self-review-not-selection-evidence"
    assert payload["original_v5_software_revision"] == V5_ORIGINAL_SOFTWARE_REVISION
    assert payload["recovery_software_revision"] == V5_RECOVERY_SOFTWARE_REVISION
    assert payload["development_protocol_sha256"] == V5_DEVELOPMENT_PROTOCOL_SHA256
    assert payload["v5_recovery_report_sha256"] == V5_RECOVERY_REPORT_SHA256
    assert payload["v5_recovery_output_manifest_sha256"] == V5_RECOVERY_OUTPUT_MANIFEST_SHA256
    assert payload["partial_v5_root_manifest_sha256"] == V5_PARTIAL_ROOT_MANIFEST_SHA256
    assert payload["failed_recovery_root_manifest_sha256"] == V5_FAILED_RECOVERY_ROOT_MANIFEST_SHA256
    assert payload["partial_review_inference_calls_reused"] == 10
    assert payload["new_review_inference_calls"] == 2
    assert payload["total_review_inference_calls"] == 12
    assert payload["result_count"] == 12


def test_v5_self_review_outcome_freeze_preserves_predeclared_rejection() -> None:
    payload = consumed_selection_development_v5_self_review_outcome_payload()
    assert payload["v4_targeted_parsed_count"] == 11
    assert payload["v4_targeted_solved_count"] == 9
    assert payload["v5_reviewed_parsed_count"] == 12
    assert payload["v5_reviewed_solved_count"] == 10
    assert payload["parse_delta"] == 1
    assert payload["solved_delta"] == 1
    assert payload["recovered_v4_failure_count"] == 1
    assert payload["regressed_v4_solve_count"] == 0
    assert payload["review_outputs_changed_count"] == 4
    assert payload["continuation_gate"] == "reject"
    assert payload["continuation_gate_rule"] == {
        "minimum_reviewed_parsed_count": 12,
        "minimum_reviewed_solved_count": 11,
        "minimum_recovered_v4_failure_count": 2,
        "maximum_regressed_v4_solve_count": 0,
    }


def test_v5_self_review_outcome_freeze_records_candidate_and_failure_structure() -> None:
    payload = consumed_selection_development_v5_self_review_outcome_payload()
    candidates = {item["candidate_id"]: item for item in payload["candidates"]}
    assert candidates["qwen3-8b-q8"]["v5_reviewed_solved_count"] == 3
    assert candidates["qwen2.5-coder-14b-q5km"]["v5_reviewed_solved_count"] == 3
    assert candidates["devstral-24b-q4km"]["v5_reviewed_solved_count"] == 3
    assert candidates["deepseek-coder-v2-lite-q5km"]["v5_reviewed_parsed_count"] == 3
    assert candidates["deepseek-coder-v2-lite-q5km"]["v5_reviewed_solved_count"] == 1
    failures = payload["failure_or_partial_results"]
    assert len(failures) == 2
    assert {item["task_id"] for item in failures} == {
        "repository-surgery-selection-error-handling-0002",
        "repository-surgery-selection-multi-file-0001",
    }
    assert all(item["reviewed_parse_valid"] for item in failures)
    assert all(not item["reviewed_solved"] for item in failures)
    assert all(item["exact_accuracy_milli"] == 500 for item in failures)


def test_v5_self_review_outcome_freeze_records_no_repeat_recovery() -> None:
    recovery = consumed_selection_development_v5_self_review_outcome_payload()["orchestration_recovery"]
    assert recovery == {
        "base_generation_reused": True,
        "original_completed_review_calls_reused": 10,
        "final_missing_review_calls_run_exactly_once": 2,
        "failed_long_path_recovery_new_inference_calls": 0,
        "failed_short_path_preflight_new_inference_calls": 0,
    }
