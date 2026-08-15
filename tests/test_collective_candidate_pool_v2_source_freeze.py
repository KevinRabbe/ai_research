from plural_cognition.collective.candidate_pool_v2_source_freeze import (
    EXPECTED_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256,
    FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256,
    QUALIFICATION_PROTOCOL_SHA256,
    candidate_pool_v2_source_freeze_payload,
)


def test_candidate_pool_v2_source_freeze_identity_and_boundary() -> None:
    payload = candidate_pool_v2_source_freeze_payload()
    assert (
        FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256
        == EXPECTED_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256
    )
    assert payload["qualification_protocol_sha256"] == QUALIFICATION_PROTOCOL_SHA256
    assert payload["source_qualification_completed_before_challenger_inference"] is True
    assert payload["qualification_rule"]["load_inference_performed"] is False
    assert payload["qualification_rule"]["selection_evidence"] is False
    assert payload["qualification_rule"]["artifact_substitution_after_load_outcome"] is False


def test_candidate_pool_v2_source_freeze_has_exact_three_challengers() -> None:
    payload = candidate_pool_v2_source_freeze_payload()
    challengers = payload["challengers"]
    assert [item["candidate_id"] for item in challengers] == [
        "gpt-oss-20b-mxfp4",
        "phi-4-reasoning-plus-14b-q5km",
        "devstral-small-2-24b-q4km",
    ]
    assert len({item["artifact_sha256"] for item in challengers}) == 3
    assert all(len(item["artifact_sha256"]) == 64 for item in challengers)
    assert all(len(item["artifact_revision"]) == 40 for item in challengers)
    assert all(len(item["artifact_linked_source_revision"]) == 40 for item in challengers)
    assert all(item["artifact_revision"] in item["download_url"] for item in challengers)
    assert all("/resolve/" in item["download_url"] for item in challengers)


def test_gpt_oss_uses_current_ggml_artifact_and_direct_source_binding() -> None:
    gpt = candidate_pool_v2_source_freeze_payload()["challengers"][0]
    assert gpt["artifact_linked_source_revision"] == gpt["observed_current_source_revision"]
    assert gpt["artifact_revision"] == "b97cbb20d1995efd41dce8c4dd1ddf86e8db375b"
    assert gpt["filename"] == "gpt-oss-20b-MXFP4.gguf"
    assert gpt["artifact_sha256"] == (
        "27cd6c432c7672cb812a92f611cf3ba7bbc35928262bb1e1253ff4ee6ae35901"
    )
    assert gpt["artifact_size_bytes"] == 12109566624
    assert gpt["lineage_evidence"]["artifact_src_sha_matches_first_party_revision"] is True


def test_community_quant_lineage_gaps_are_explicit_not_silent() -> None:
    phi, devstral = candidate_pool_v2_source_freeze_payload()["challengers"][1:]
    assert phi["artifact_revision"] == "7724f4a631c905f40112df7104ec590dc3bf290a"
    assert phi["artifact_sha256"] == (
        "7d4dd651787f16365d6ceed9bcc42fe76e47204dedf9ac3539a749e1c3f3b6f7"
    )
    assert phi["artifact_size_bytes"] is None
    assert phi["lineage_evidence"]["quantizer_release"] == "llama.cpp-b5228"
    assert phi["lineage_evidence"]["artifact_src_sha_matches_first_party_revision"] is False
    assert phi["provenance_caveats"]

    assert devstral["artifact_revision"] == "2926c4f9c89e15bdebd5c8f458acd9609e778631"
    assert devstral["artifact_sha256"] == (
        "bfd11c8679c6b81eb43763505465d7dcfa72e460ab1c220ecc235a3efadd7f7f"
    )
    assert devstral["artifact_size_bytes"] == 14334438272
    assert devstral["lineage_evidence"]["quantizer_release"] == "llama.cpp-b7335"
    assert devstral["lineage_evidence"]["artifact_src_sha_matches_first_party_revision"] is False
    assert devstral["provenance_caveats"]
