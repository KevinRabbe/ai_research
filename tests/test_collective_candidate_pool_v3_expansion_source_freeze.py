from __future__ import annotations

import hashlib
import json

from plural_cognition.collective import candidate_pool_v3_expansion_source_freeze as freeze


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


def test_v3_expansion_source_freeze_has_exact_identity() -> None:
    payload = freeze.candidate_pool_v3_expansion_source_freeze_payload()
    assert _digest(payload) == freeze.EXPECTED_CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SHA256
    assert _digest(payload) == (
        "7e3a49def60361dc2ce82f32c750d44b4dd0cb2d024b79f76d8469be3e2bec03"
    )


def test_v3_expansion_source_freeze_binds_exact_order_and_artifacts() -> None:
    payload = freeze.candidate_pool_v3_expansion_source_freeze_payload()
    assert payload["predecessor_expansion_protocol_revision"] == (
        "1f51f19083f3e0ab7cc4f85e9bb77ef91d40d385"
    )
    assert payload["predecessor_expansion_protocol_sha256"] == (
        "2ac18170b0dc5a1708f3974816dafdd28fa092f01d8170afc0e85d65dcbae4fc"
    )
    assert payload["scout_order"] == [
        "qwen3-14b-q5km",
        "ministral-3-14b-instruct-2512-q5km",
        "ministral-3-8b-instruct-2512-q5km",
    ]
    assert [item["artifact_size_bytes"] for item in payload["scouts"]] == [
        10_514_569_568,
        9_621_091_904,
        6_059_268_512,
    ]
    assert [item["artifact_sha256"] for item in payload["scouts"]] == [
        "e7c9aba1129ca2936be9eca01419d9f86af40e08caa01230d5574b34d08e3e31",
        "f16fef77021df0d4c22e69140a2038478370492f51867b6237699918ae711000",
        "7a5454127ec772e2389f0e71a77fedb88b83d4366d8a69facd0cfd0898f04d35",
    ]


def test_v3_expansion_source_freeze_is_first_party_revision_pinned_and_unmeasured() -> None:
    payload = freeze.candidate_pool_v3_expansion_source_freeze_payload()
    for item in payload["scouts"]:
        assert item["source_revision"] == item["artifact_revision"]
        assert len(item["artifact_revision"]) == 40
        assert item["first_party_artifact"] is True
        assert item["llama_cpp_usage_documented"] is True
        assert item["previously_measured_artifact"] is False
        assert item["license"] == "apache-2.0"
        assert f"/resolve/{item['artifact_revision']}/{item['artifact_filename']}" in (
            item["immutable_download_url"]
        )


def test_v3_expansion_source_freeze_used_no_task_outcome_evidence() -> None:
    basis = freeze.candidate_pool_v3_expansion_source_freeze_payload()["selection_basis"]
    assert basis["task_specific_evidence_used"] is False
    assert basis["consumed_v3_calibration_task_outputs_used"] is False
    assert basis["candidate_specific_prompt_tuning_used"] is False
    assert basis["allowed_metadata_only"] is True


def test_v3_expansion_source_freeze_authorizes_only_load_runner_authoring() -> None:
    authorization = freeze.candidate_pool_v3_expansion_source_freeze_payload()["authorization"]
    assert authorization["candidate_model_calls_consumed_before_source_freeze"] == 0
    assert authorization["load_qualification_runner_authoring_authorized_after_green"] is True
    assert authorization["new_model_inference_authorized"] is False
    assert authorization["load_inference_authorized"] is False
    assert authorization["calibration_runner_authoring_authorized"] is False
    assert authorization["calibration_inference_authorized"] is False
    assert authorization["selection_pack_authoring_authorized"] is False
    assert authorization["selection_inference_authorized"] is False
    assert authorization["plural_synthesis_authorized"] is False
    assert authorization["artifact_substitution_authorized"] is False
    assert authorization["scout_reordering_authorized"] is False
    assert authorization["additional_scout_authoring_authorized"] is False
