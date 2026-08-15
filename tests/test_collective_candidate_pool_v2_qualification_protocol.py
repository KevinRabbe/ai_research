from plural_cognition.collective.candidate_pool_v2_qualification_protocol import (
    EXPECTED_CANDIDATE_POOL_V2_PROTOCOL_SHA256,
    FINAL_CANDIDATE_POOL_V2_PROTOCOL_SHA256,
    candidate_pool_v2_qualification_protocol_payload,
)


def test_candidate_pool_v2_protocol_identity_and_scope() -> None:
    payload = candidate_pool_v2_qualification_protocol_payload()
    assert FINAL_CANDIDATE_POOL_V2_PROTOCOL_SHA256 == EXPECTED_CANDIDATE_POOL_V2_PROTOCOL_SHA256
    assert payload["scientific_status"] == "candidate-development-v2-pre-selection-not-selection-evidence"
    assert payload["representation"]["output_contract"] == "raw-full-file-replacement-v1"
    assert payload["representation"]["self_review"] is False
    assert payload["representation"]["candidate_output_repair"] is False
    assert payload["representation"]["max_attempts"] == 1
    assert payload["selection_v2"]["requires_fresh_untouched_pack"] is True
    assert payload["selection_v2"]["consumed_v1_material_usable_for_selection_claim"] is False


def test_candidate_pool_v2_is_bounded_and_fail_closed() -> None:
    payload = candidate_pool_v2_qualification_protocol_payload()
    assert payload["incumbent_candidates"] == [
        "qwen3-8b-q8",
        "qwen2.5-coder-14b-q5km",
        "devstral-24b-q4km",
    ]
    assert [item["candidate_id"] for item in payload["challenger_scouts"]] == [
        "gpt-oss-20b-mxfp4",
        "phi-4-reasoning-plus-14b-q5km",
        "devstral-small-2-24b-q4km",
    ]
    assert payload["source_qualification"]["substitution_after_load_outcome"] is False
    assert payload["load_qualification"]["challenger_formal_load_attempts_per_candidate"] == 1
    assert payload["calibration_gate"]["task_count_per_candidate"] == 6
    assert payload["calibration_gate"]["required_parse_valid_count"] == 6
    assert payload["calibration_gate"]["minimum_solved_count"] == 4
    assert payload["calibration_gate"]["reruns_for_failed_candidates"] is False
    assert payload["selection_v2"]["task_count"] == 12
    assert payload["selection_v2"]["min_valid_rate"] == 0.95
    assert payload["selection_v2"]["population_size"] == 4
    assert payload["selection_v2"]["selection_run_count"] == 1
    assert payload["selection_v2"]["threshold_lowering_after_outcome"] is False


def test_candidate_pool_v2_reuses_frozen_runtime_and_hardware() -> None:
    payload = candidate_pool_v2_qualification_protocol_payload()
    runtime = payload["runtime"]
    resources = payload["resource_budget"]
    assert runtime["llama_cpp_build"] == "b10361"
    assert runtime["llama_cpp_revision"] == "14e78ddef7a2061e7d5a31dce4eb7ee0bcdbc840"
    assert payload["hardware"]["vram_mib"] == 16380
    assert resources["context_tokens"] == 4096
    assert resources["predict_tokens"] == 2048
    assert resources["threads"] == 16
    assert resources["batch_threads"] == 16
    assert resources["batch_size"] == 2048
    assert resources["microbatch_size"] == 512
    assert resources["temperature"] == 0.0
    assert resources["seed"] == 1
    assert resources["full_gpu_offload_required"] is True
