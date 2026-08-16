import subprocess

from plural_cognition.collective.candidate_pool_v3_representation_protocol import (
    EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256,
    V3_DEVELOPMENT_CANDIDATE_IDS,
    V3_REPRESENTATION_SOURCE_GIT_BLOB_SHA1,
    V3_REPRESENTATION_SOURCE_REVISION,
    candidate_pool_v3_representation_protocol_payload,
    validate_v3_representation_protocol,
)


def test_v3_representation_protocol_freeze_and_scientific_boundaries() -> None:
    validate_v3_representation_protocol()
    payload = candidate_pool_v3_representation_protocol_payload()

    assert EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256 == (
        "28243c1a330bbc51734aa9083f98ee8a2257c17f6290c71ec9bbb4404bca3c61"
    )
    assert tuple(payload["development_candidate_ids"]) == V3_DEVELOPMENT_CANDIDATE_IDS
    assert len(V3_DEVELOPMENT_CANDIDATE_IDS) == 4

    representation = payload["representation"]
    assert representation["accept_optional_file_colon"] is True
    assert representation["accept_blank_lines_between_blocks"] is True
    assert representation["content_delimiters_required"] is True
    assert representation["exact_solver_visible_paths_required"] is True
    assert representation["relative_prefix_rewrite"] is False
    assert representation["bare_file_mode"] is False
    assert representation["fuzzy_matching"] is False
    assert representation["candidate_output_repair"] is False

    development = payload["fresh_development_calibration"]
    assert development["task_count_per_candidate"] == 6
    assert development["required_parse_valid_count"] == 6
    assert development["minimum_solved_count"] == 4
    assert development["tasks_must_be_new"] is True
    assert development["v2_calibration_tasks_reused"] is False
    assert development["v2_selection_tasks_reused"] is False
    assert development["selection_evidence"] is False

    selection = payload["future_selection"]
    assert selection["fresh_untouched_task_count"] == 12
    assert selection["min_valid_rate"] == 0.95
    assert selection["population_size"] == 4
    assert selection["one_selection_run"] is True
    assert selection["threshold_lowering_after_outcomes"] is False

    assert payload["candidate_model_inference_performed"] is False
    assert payload["selection_evidence_observed"] is False


def test_v3_representation_blob_identity_is_exact() -> None:
    observed = subprocess.run(
        [
            "git",
            "rev-parse",
            "HEAD:src/plural_cognition/collective/candidate_pool_v3_full_file.py",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert V3_REPRESENTATION_SOURCE_REVISION == (
        "b9169434ecb3db7b7995e47e5679d95da4cbe24b"
    )
    assert observed == V3_REPRESENTATION_SOURCE_GIT_BLOB_SHA1
