from plural_cognition.collective.consumed_selection_development_v4_outcome_freeze import (
    EXPECTED_V4_OUTCOME_FREEZE_SHA256,
    FINAL_CONSUMED_SELECTION_DEVELOPMENT_V4_OUTCOME_FREEZE_SHA256,
    consumed_selection_development_v4_outcome_payload,
)


def test_v4_outcome_freeze_identity_is_exact() -> None:
    assert FINAL_CONSUMED_SELECTION_DEVELOPMENT_V4_OUTCOME_FREEZE_SHA256 == EXPECTED_V4_OUTCOME_FREEZE_SHA256
    assert EXPECTED_V4_OUTCOME_FREEZE_SHA256 == "93c0d0bd15092e3a7c5d7664461f8542b6d203ff0c64132ad0517183bd370e9a"


def test_v4_outcome_freeze_preserves_scientific_boundary_and_gate() -> None:
    payload = consumed_selection_development_v4_outcome_payload()
    assert payload["scientific_status"] == "development-only-consumed-split-not-selection-evidence"
    assert payload["combined_result_count"] == 48
    assert payload["combined_unique_pair_count"] == 48
    assert payload["combined_task_count"] == 12
    assert payload["v1_parsed_count"] == 43
    assert payload["v1_solved_count"] == 42
    assert payload["v4_parsed_count"] == 47
    assert payload["v4_solved_count"] == 45
    assert payload["continuation_gate"] == "reject"


def test_v4_outcome_freeze_binds_exact_candidate_diagnostics() -> None:
    payload = consumed_selection_development_v4_outcome_payload()
    observed = {
        item["candidate_id"]: (
            item["v1_parsed_count"],
            item["v1_solved_count"],
            item["v4_parsed_count"],
            item["v4_solved_count"],
        )
        for item in payload["candidates"]
    }
    assert observed == {
        "qwen3-8b-q8": (9, 9, 12, 11),
        "qwen2.5-coder-14b-q5km": (11, 11, 12, 12),
        "devstral-24b-q4km": (11, 11, 12, 12),
        "deepseek-coder-v2-lite-q5km": (12, 11, 11, 10),
    }


def test_v4_outcome_freeze_binds_three_failure_or_partial_observations() -> None:
    payload = consumed_selection_development_v4_outcome_payload()
    failures = payload["failure_or_partial_results"]
    assert len(failures) == 3
    assert {(item["candidate_id"], item["task_id"]) for item in failures} == {
        ("deepseek-coder-v2-lite-q5km", "repository-surgery-selection-error-handling-0002"),
        ("qwen3-8b-q8", "repository-surgery-selection-multi-file-0001"),
        ("deepseek-coder-v2-lite-q5km", "repository-surgery-selection-multi-file-0001"),
    }
    deepseek_multifile = next(
        item for item in failures
        if item["candidate_id"] == "deepseek-coder-v2-lite-q5km"
        and item["task_id"] == "repository-surgery-selection-multi-file-0001"
    )
    assert deepseek_multifile["parse_valid"] is False
    assert deepseek_multifile["parse_error"] == "V4 file block leaves file unchanged: app.py"
