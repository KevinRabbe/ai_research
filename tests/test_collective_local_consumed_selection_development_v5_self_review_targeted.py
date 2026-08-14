from plural_cognition.collective.consumed_selection_development_v5_self_review import (
    TARGET_CANDIDATE_IDS_V5,
    TARGET_RESULT_COUNT_V5,
    TARGET_TASK_IDS_V5,
    TARGET_V4_PARSED_COUNT_V5,
    TARGET_V4_SOLVED_COUNT_V5,
)
from plural_cognition.collective.local_consumed_selection_development_v5_self_review_targeted import (
    _targeted_v4_baseline,
)


def test_targeted_v4_baseline_helper_matches_predeclared_counts() -> None:
    records = {}
    solved_false = {
        ("qwen3-8b-q8", "repository-surgery-selection-multi-file-0001"),
        ("deepseek-coder-v2-lite-q5km", "repository-surgery-selection-error-handling-0002"),
        ("deepseek-coder-v2-lite-q5km", "repository-surgery-selection-multi-file-0001"),
    }
    parse_false = {
        ("deepseek-coder-v2-lite-q5km", "repository-surgery-selection-multi-file-0001"),
    }
    for candidate_id in TARGET_CANDIDATE_IDS_V5:
        for task_id in TARGET_TASK_IDS_V5:
            key = (candidate_id, task_id)
            records[key] = {
                "result": {
                    "parse_valid": key not in parse_false,
                    "solved": key not in solved_false,
                }
            }
    assert _targeted_v4_baseline(records) == (
        TARGET_RESULT_COUNT_V5,
        TARGET_V4_PARSED_COUNT_V5,
        TARGET_V4_SOLVED_COUNT_V5,
    ) == (12, 11, 9)
