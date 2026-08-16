from __future__ import annotations

import hashlib
import json

from plural_cognition.collective import candidate_pool_v3_calibration_outcome_freeze as freeze


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def test_v3_calibration_outcome_freeze_has_exact_canonical_identity() -> None:
    payload = freeze.candidate_pool_v3_calibration_outcome_freeze_payload()
    digest = _digest(payload)
    assert digest == freeze.EXPECTED_CALIBRATION_OUTCOME_FREEZE_SHA256_V3
    assert digest == "b82b08ea6603719ec70e250bf5635ea1c1443db25703b3dafd5e189b0a281f56"


def test_v3_calibration_outcome_freeze_binds_consumed_suite() -> None:
    payload = freeze.candidate_pool_v3_calibration_outcome_freeze_payload()
    assert payload["software_revision"] == "d8972e2ecc51f86c286169899024baea3850f33c"
    assert payload["artifact_root"] == "artifacts/capable-collective/c3"
    assert payload["suite_file_sha256"] == (
        "b1c8b697fcf2e7ccba5f60ac51ee67067e093f81c5342b4e6fdb791e9a74424e"
    )
    assert payload["report_sha256"] == (
        "b9d45942ef96d62babf048aaf9661fa6b018d9881ae526029a5fd6e1c638d668"
    )
    assert payload["runner_protocol_sha256"] == (
        "2e3984de232ddab4b9a96f8363a331b013ce1c68f9a1b91bc651f1312ad9b600"
    )
    assert payload["runner_freeze_sha256"] == (
        "6a2b815a3d2cd6b21c77f10bcd4725c05ba34a9a4605506940d85e72c5373cf9"
    )
    assert payload["qualification_freeze_sha256"] == (
        "b121dccd76616913fe144d8d298bc38a58bc278a1c6ba7e630e67c3bbaaef593"
    )
    assert payload["representation_protocol_sha256"] == (
        "28243c1a330bbc51734aa9083f98ee8a2257c17f6290c71ec9bbb4404bca3c61"
    )
    assert payload["repaired_calibration_pack_sha256"] == (
        "c00d98ed758016dab5571570ababbcbb6c639aa39ad87be34f9c37cddc803513"
    )
    assert payload["pair_count"] == 24
    assert payload["new_inference_attempt_count"] == 24
    assert payload["candidate_model_calls_consumed"] == 24
    assert payload["selection_evidence"] is False


def test_v3_calibration_outcome_freeze_preserves_exact_candidate_gate_results() -> None:
    payload = freeze.candidate_pool_v3_calibration_outcome_freeze_payload()
    assert payload["gate"] == {
        "required_parse_valid_count": 6,
        "minimum_solved_count": 4,
    }
    assert payload["parse_valid_count"] == 23
    assert payload["solved_count"] == 19
    assert payload["summaries"] == [
        {
            "candidate_id": "qwen3-8b-q8",
            "task_count": 6,
            "parse_valid_count": 5,
            "solved_count": 1,
            "passed_calibration_gate": False,
            "peak_gpu_used_mib": 9003,
        },
        {
            "candidate_id": "qwen2.5-coder-14b-q5km",
            "task_count": 6,
            "parse_valid_count": 6,
            "solved_count": 6,
            "passed_calibration_gate": True,
            "peak_gpu_used_mib": 11049,
        },
        {
            "candidate_id": "devstral-24b-q4km",
            "task_count": 6,
            "parse_valid_count": 6,
            "solved_count": 6,
            "passed_calibration_gate": True,
            "peak_gpu_used_mib": 14839,
        },
        {
            "candidate_id": "gpt-oss-20b-mxfp4",
            "task_count": 6,
            "parse_valid_count": 6,
            "solved_count": 6,
            "passed_calibration_gate": True,
            "peak_gpu_used_mib": 11823,
        },
    ]
    assert payload["eligible_candidate_count"] == 3
    assert payload["eligible_candidate_ids"] == [
        "qwen2.5-coder-14b-q5km",
        "devstral-24b-q4km",
        "gpt-oss-20b-mxfp4",
    ]
    assert payload["required_population_size"] == 4
    assert payload["population_feasible"] is False


def test_v3_calibration_outcome_freeze_forbids_posthoc_rescue_and_selection() -> None:
    authorization = freeze.candidate_pool_v3_calibration_outcome_freeze_payload()[
        "authorization"
    ]
    assert authorization == {
        "calibration_rerun_authorized": False,
        "calibration_gate_lowering_authorized": False,
        "candidate_specific_tuning_authorized": False,
        "automatic_candidate_replacement_authorized": False,
        "selection_pack_authoring_authorized": False,
        "selection_inference_authorized": False,
        "plural_synthesis_authorized": False,
        "new_candidate_expansion_authorized_by_this_freeze": False,
        "new_candidate_expansion_requires_new_prefreeze_source_load_qualification_protocol": True,
    }


def test_v3_calibration_outcome_freeze_validator_accepts_frozen_record() -> None:
    freeze.validate_candidate_pool_v3_calibration_outcome_freeze()
