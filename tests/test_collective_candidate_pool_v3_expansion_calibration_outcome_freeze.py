from __future__ import annotations

import hashlib
import json

from plural_cognition.collective import (
    candidate_pool_v3_expansion_calibration_outcome_freeze as outcome,
)


def test_v3_expansion_calibration_outcome_freeze_binds_positive_first_scout() -> None:
    payload = outcome.candidate_pool_v3_expansion_calibration_outcome_freeze_payload()

    assert payload["software_revision"] == (
        "ac7f15152d12e56a3062aa72276dc8b9292c14b7"
    )
    assert payload["suite_file_sha256"] == (
        "bb628f97e9775b997369449bffe1a128ff11f3c05fa4bbc023b462fb2aac7c68"
    )
    assert payload["report_sha256"] == (
        "6c54e6b3b57752dbde1bacc9f2bd2b5fdb6264a26bcdb63692d7510dabf7aa2a"
    )
    assert payload["pair_count"] == 6
    assert payload["new_inference_attempt_count"] == 6
    assert payload["candidate_model_calls_consumed"] == 6
    assert payload["evaluated_candidate_ids"] == ["qwen3-14b-q5km"]
    assert payload["unevaluated_candidate_ids"] == [
        "ministral-3-14b-instruct-2512-q5km",
        "ministral-3-8b-instruct-2512-q5km",
    ]
    assert payload["passing_candidate_id"] == "qwen3-14b-q5km"
    assert payload["stopped_after_first_gate_pass"] is True
    assert payload["summary"] == {
        "candidate_id": "qwen3-14b-q5km",
        "task_count": 6,
        "parse_valid_count": 6,
        "solved_count": 5,
        "passed_calibration_gate": True,
        "peak_gpu_used_mib": 15338,
    }
    assert sum(item["parse_valid"] for item in payload["pair_reports"]) == 6
    assert sum(item["solved"] for item in payload["pair_reports"]) == 5
    assert payload["selection_evidence"] is False


def test_v3_expansion_calibration_outcome_freezes_exact_four_member_population() -> None:
    payload = outcome.candidate_pool_v3_expansion_calibration_outcome_freeze_payload()

    assert payload["existing_eligible_candidate_ids"] == [
        "qwen2.5-coder-14b-q5km",
        "devstral-24b-q4km",
        "gpt-oss-20b-mxfp4",
    ]
    assert payload["new_eligible_candidate_ids"] == ["qwen3-14b-q5km"]
    assert payload["frozen_population_candidate_ids"] == [
        "qwen2.5-coder-14b-q5km",
        "devstral-24b-q4km",
        "gpt-oss-20b-mxfp4",
        "qwen3-14b-q5km",
    ]
    assert payload["eligible_candidate_count"] == 4
    assert payload["required_population_size"] == 4
    assert payload["population_feasible"] is True


def test_v3_expansion_calibration_outcome_preserves_predecessor_evidence() -> None:
    payload = outcome.candidate_pool_v3_expansion_calibration_outcome_freeze_payload()

    assert payload["predecessor_evidence_fingerprints"] == {
        "e3l": "2a4aade4a78f45eb0160963b6d90e3f8c5f2d2cd63250570a23873f4b4fce5b4",
        "c3q-r1": "200c70894de8c017d25b11074c2d7b89333fd47165134d23e46c590029a41a71",
        "c3": "492e44a3efe9bbef19a3abb6ae2ed592a481de4e6e9cb73bdc9feaafc6098a3f",
    }


def test_v3_expansion_calibration_outcome_authorization_boundary() -> None:
    authorization = (
        outcome.candidate_pool_v3_expansion_calibration_outcome_freeze_payload()[
            "authorization"
        ]
    )
    assert authorization == {
        "expansion_calibration_rerun_authorized": False,
        "calibration_gate_lowering_authorized": False,
        "candidate_specific_tuning_authorized": False,
        "evaluate_unevaluated_scouts_after_pass_authorized": False,
        "automatic_candidate_replacement_authorized": False,
        "population_substitution_authorized": False,
        "fresh_selection_pack_authoring_authorized_after_green": True,
        "selection_inference_authorized": False,
        "plural_synthesis_authorized": False,
        "selection_pack_must_be_fresh_and_untouched": True,
        "selection_pack_task_count": 12,
        "selection_population_size": 4,
        "selection_min_valid_rate": 0.95,
    }


def test_v3_expansion_calibration_outcome_canonical_identity() -> None:
    payload = outcome.candidate_pool_v3_expansion_calibration_outcome_freeze_payload()
    digest = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
    assert digest == (
        "d39b2d3da6d156485e957e8e37f7eb2e961364e45c936fd15b673f67ecc61f12"
    )
    assert digest == outcome.EXPECTED_EXPANSION_CALIBRATION_OUTCOME_FREEZE_SHA256_V3
