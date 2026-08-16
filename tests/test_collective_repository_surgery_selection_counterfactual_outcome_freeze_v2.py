from plural_cognition.collective.repository_surgery_selection_counterfactual_outcome_freeze_v2 import (
    EXPECTED_COUNTERFACTUAL_OUTCOME_FREEZE_SHA256_V2,
    LEVEL_DIAGNOSTICS,
    V3_DEVELOPMENT_CANDIDATE_IDS,
    counterfactual_outcome_freeze_payload_v2,
    validate_counterfactual_outcome_freeze_v2,
)


def test_counterfactual_outcome_freeze_is_immutable_development_evidence() -> None:
    validate_counterfactual_outcome_freeze_v2()
    payload = counterfactual_outcome_freeze_payload_v2()

    assert EXPECTED_COUNTERFACTUAL_OUTCOME_FREEZE_SHA256_V2 == (
        "8e03ebe5ac9e1d9c3f99e95523183bb94398bcfc75561340b4e40df03ddc5251"
    )
    assert payload["invalid_pair_count"] == 27
    assert payload["candidate_model_inference_performed"] is False
    assert payload["selection_outcome_mutated"] is False
    assert payload["selection_rerun"] is False
    assert payload["threshold_lowered"] is False
    assert payload["frozen_v2_selection_result_changed"] is False


def test_minimal_non_bare_level_yields_exact_four_candidate_development_set() -> None:
    level, diagnostics = LEVEL_DIAGNOSTICS[2]
    assert level == "prompt-path-tolerant"

    eligible = tuple(
        candidate_id
        for candidate_id, valid_count, _solved_count, _flag in diagnostics
        if valid_count / 12 >= 0.95
    )
    assert eligible == V3_DEVELOPMENT_CANDIDATE_IDS
    assert tuple((item[0], item[1], item[2]) for item in diagnostics[:4]) == (
        ("qwen3-8b-q8", 12, 10),
        ("qwen2.5-coder-14b-q5km", 12, 11),
        ("devstral-24b-q4km", 12, 12),
        ("gpt-oss-20b-mxfp4", 12, 12),
    )


def test_v3_decision_rejects_bare_file_and_relative_path_rewrite() -> None:
    decision = counterfactual_outcome_freeze_payload_v2()["v3_design_decision"]
    assert decision["keep_structured_whole_file_replacement"] is True
    assert decision["accept_optional_colon_after_file_keyword"] is True
    assert decision["accept_blank_lines_between_file_blocks"] is True
    assert decision["fix_prompt_path_example"] is True
    assert decision["production_relative_prefix_rewrite"] is False
    assert decision["bare_file_mode"] is False
