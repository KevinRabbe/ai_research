from plural_cognition.collective.bakeoff import PopulationSelectionStatus
from plural_cognition.collective.local_operational_freeze_v1 import FINAL_CANDIDATE_IDS
from plural_cognition.collective.repository_surgery_selection_outcome_freeze_v1 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256,
    FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_V1,
)


def test_selection_outcome_freeze_matches_target_evidence() -> None:
    freeze = FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_V1
    freeze.validate_against_repository()
    assert FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256 == (
        "e579e01b0c1d710a4ca303896da84801ef27d9502b66782c88f384129fbe4eb5"
    )
    assert freeze.report_sha256 == (
        "cfb56dd84564db7de09be590c93107cf7d2c7e76f8971eabbe41a2f8926826fd"
    )
    assert freeze.bakeoff_plan_sha256 == (
        "88183d2393942608c5953740cefb5ebfc6be5c493f323b9c8b8daffa75b58e69"
    )
    assert freeze.output_manifest_sha256 == (
        "fa80dcc9fa8939d0d5585dee2912757860dd2596c75bd9a94274320fdf51f2d2"
    )
    assert freeze.result_count == 60
    assert freeze.parsed_count == 45
    assert freeze.solved_count == 44


def test_selection_outcome_preserves_predeclared_negative_result() -> None:
    freeze = FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_V1
    assert freeze.min_valid_rate == 0.95
    assert freeze.population_size == 4
    assert freeze.selection_status is PopulationSelectionStatus.INSUFFICIENT_ELIGIBLE
    assert freeze.eligible_candidate_ids == ("deepseek-coder-v2-lite-q5km",)
    assert freeze.strongest_candidate_id is None
    assert freeze.selected_candidate_ids == ()


def test_selection_diagnostics_preserve_frozen_candidate_order_and_counts() -> None:
    diagnostics = FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_V1.diagnostics
    assert tuple(item.candidate_id for item in diagnostics) == FINAL_CANDIDATE_IDS
    assert [(item.valid_count, item.pass_count) for item in diagnostics] == [
        (9, 9),
        (11, 11),
        (2, 2),
        (11, 11),
        (12, 11),
    ]
    assert sum(item.valid_count for item in diagnostics) == 45
    assert sum(item.pass_count for item in diagnostics) == 44
    assert all(item.total_tokens == 0 for item in diagnostics)
