from plural_cognition.collective.consumed_selection_development_v4 import (
    CANDIDATE_OUTPUT_INTERPRETER_V4,
    DEVELOPMENT_PROTOCOL_SHA256_V4,
    OUTPUT_CONTRACT_V4,
)
from plural_cognition.collective.consumed_selection_development_v4_outcome_freeze import (
    FINAL_CONSUMED_SELECTION_DEVELOPMENT_V4_OUTCOME_FREEZE_SHA256,
)
from plural_cognition.collective.consumed_selection_development_v5_self_review import (
    DEVELOPMENT_PROTOCOL_SHA256_V5,
    TARGET_CANDIDATE_IDS_V5,
    TARGET_MIN_REVIEWED_PARSED_COUNT_V5,
    TARGET_MIN_REVIEWED_SOLVED_COUNT_V5,
    TARGET_REQUIRED_RECOVERED_FAILURE_COUNT_V5,
    TARGET_RESULT_COUNT_V5,
    TARGET_TASK_IDS_V5,
    TARGET_V4_PARSED_COUNT_V5,
    TARGET_V4_SOLVED_COUNT_V5,
    build_self_review_prompt_v5,
    development_protocol_payload_v5,
    extract_reviewed_patch_v5,
)
from plural_cognition.collective.repository_surgery_selection_pack_v1 import selection_blueprints


def _blueprint(task_id: str):
    return {item.task_id: item for item in selection_blueprints()}[task_id]


def test_v5_protocol_binds_frozen_v4_and_predeclared_gate() -> None:
    payload = development_protocol_payload_v5()
    assert payload["v4_development_protocol_sha256"] == DEVELOPMENT_PROTOCOL_SHA256_V4
    assert payload["v4_outcome_freeze_sha256"] == FINAL_CONSUMED_SELECTION_DEVELOPMENT_V4_OUTCOME_FREEZE_SHA256
    assert payload["base_draft_regenerated"] is False
    assert payload["reviewer_identity"] == "same-candidate-as-draft"
    assert payload["review_inference_calls_per_pair"] == 1
    assert payload["output_contract"] == OUTPUT_CONTRACT_V4
    assert payload["candidate_output_interpreter"] == CANDIDATE_OUTPUT_INTERPRETER_V4
    assert tuple(payload["target_candidate_ids"]) == TARGET_CANDIDATE_IDS_V5
    assert tuple(payload["target_task_ids"]) == TARGET_TASK_IDS_V5
    assert payload["target_result_count"] == TARGET_RESULT_COUNT_V5 == 12
    assert payload["target_v4_parsed_count"] == TARGET_V4_PARSED_COUNT_V5 == 11
    assert payload["target_v4_solved_count"] == TARGET_V4_SOLVED_COUNT_V5 == 9
    gate = payload["continuation_gate"]
    assert gate["minimum_reviewed_parsed_count"] == TARGET_MIN_REVIEWED_PARSED_COUNT_V5 == 12
    assert gate["minimum_reviewed_solved_count"] == TARGET_MIN_REVIEWED_SOLVED_COUNT_V5 == 11
    assert gate["minimum_recovered_v4_failure_count"] == TARGET_REQUIRED_RECOVERED_FAILURE_COUNT_V5 == 2
    assert gate["forbid_regression_on_v4_solved_pairs"] is True
    assert payload["draft_interpreter_feedback_visible_to_reviewer"] is False
    assert payload["protected_evaluator_visible_to_reviewer"] is False
    assert payload["population_selection_evidence"] is False
    assert len(DEVELOPMENT_PROTOCOL_SHA256_V5) == 64


def test_review_prompt_contains_raw_draft_but_no_outcome_feedback() -> None:
    blueprint = _blueprint("repository-surgery-selection-multi-file-0001")
    draft = b'FILE fees.py\n<<<<<<< CONTENT\ndef regional_fee(region: str) -> int:\n    return 5 if region == "CA" else 2\n>>>>>>> CONTENT'
    prompt = build_self_review_prompt_v5(blueprint, draft)
    assert prompt.endswith(b"\n")
    assert draft in prompt
    assert b"SELF_REVIEW_STAGE:" in prompt
    assert b"PREVIOUS_DRAFT START" in prompt
    assert b"same task" in prompt
    assert b"parse_error" not in prompt
    assert b"exact_accuracy" not in prompt
    assert b"evaluator_valid_rate" not in prompt
    assert b"draft_solved" not in prompt


def test_reviewed_output_uses_unchanged_v4_interpreter() -> None:
    blueprint = _blueprint("repository-surgery-selection-error-handling-0002")
    clean = dict(blueprint.clean_files)["app.py"].decode("utf-8")
    raw = ("FILE app.py\n<<<<<<< CONTENT\n" + clean[:-1] + "\n>>>>>>> CONTENT").encode("utf-8")
    patch, mode = extract_reviewed_patch_v5(raw, blueprint)
    assert patch == blueprint.gold_patch
    assert mode == "raw-full-file-replacement-after-self-review"


def test_target_is_failure_heavy_plus_same_family_control() -> None:
    assert TARGET_TASK_IDS_V5 == (
        "repository-surgery-selection-error-handling-0002",
        "repository-surgery-selection-multi-file-0001",
        "repository-surgery-selection-multi-file-0002",
    )
    assert TARGET_CANDIDATE_IDS_V5 == (
        "qwen3-8b-q8",
        "qwen2.5-coder-14b-q5km",
        "devstral-24b-q4km",
        "deepseek-coder-v2-lite-q5km",
    )
