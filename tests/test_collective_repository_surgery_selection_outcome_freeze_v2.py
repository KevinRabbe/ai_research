from plural_cognition.collective.bakeoff import PopulationSelectionStatus
from plural_cognition.collective.candidate_pool_v2_operational_freeze import FINAL_CANDIDATE_IDS_V2
from plural_cognition.collective.repository_surgery_selection_outcome_freeze_v2 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256_V2,
    FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_V2,
)


def test_v2_selection_outcome_freeze_matches_target_evidence() -> None:
    freeze = FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_V2
    freeze.validate_against_repository()
    assert FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256_V2 == (
        "b22e5c6fded1e9d0bd94fd4a8cd45bd4712ea9782d58a1f8820a6fdcb35d9517"
    )
    assert freeze.selection_suite_file_sha256 == (
        "ac77effa62f42cd6914b8a67765a2318b72281f59edc94e3a8e5cbc114c41fce"
    )
    assert freeze.selection_report_sha256 == (
        "713f25bc8635914bb8c491eb291f6355998995bb237d3d929a58d83a0db7a01c"
    )
    assert freeze.pair_count == 60
    assert freeze.parsed_count == 33
    assert freeze.solved_count == 30
    assert freeze.selection_calls_consumed == 60
    assert freeze.selection_evidence is True


def test_v2_selection_outcome_preserves_predeclared_negative_result() -> None:
    freeze = FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_V2
    assert freeze.min_valid_rate == 0.95
    assert freeze.population_size == 4
    assert freeze.selection_status is PopulationSelectionStatus.INSUFFICIENT_ELIGIBLE
    assert freeze.eligible_candidate_ids == ("qwen3-8b-q8",)
    assert freeze.strongest_candidate_id is None
    assert freeze.selected_candidate_ids == ()
    assert freeze.threshold_lowering_authorized is False
    assert freeze.rerun_authorized is False


def test_v2_selection_diagnostics_preserve_candidate_order_and_counts() -> None:
    diagnostics = FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_V2.diagnostics
    assert tuple(item.candidate_id for item in diagnostics) == FINAL_CANDIDATE_IDS_V2
    assert [(item.valid_count, item.pass_count) for item in diagnostics] == [
        (12, 10),
        (11, 10),
        (8, 8),
        (2, 2),
        (0, 0),
    ]
    assert [item.accelerator_time_ms for item in diagnostics] == [
        308774,
        127614,
        344101,
        138091,
        264873,
    ]
    assert sum(item.valid_count for item in diagnostics) == 33
    assert sum(item.pass_count for item in diagnostics) == 30
    assert all(item.total_tokens == 0 for item in diagnostics)


def test_v2_only_qwen3_meets_frozen_validity_gate() -> None:
    freeze = FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_V2
    eligible = tuple(
        item.candidate_id
        for item in freeze.diagnostics
        if item.valid_rate >= freeze.min_valid_rate
    )
    assert eligible == ("qwen3-8b-q8",)
    assert len(eligible) < freeze.population_size
