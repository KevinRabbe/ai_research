"""Predeclared qualification protocol for the separately versioned candidate-pool v2 cycle.

This protocol is development-only and precedes any fresh v2 selection evidence. It
intentionally reduces experiment count after the consumed v1 diagnostics: keep the
V4 whole-file representation, do not add self-review, reuse unchanged incumbent load
evidence, give each challenger one formal load attempt, use one six-task calibration
gate, then freeze a new operational configuration before a fresh untouched v2
selection pack is created.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

CANDIDATE_POOL_V2_PROTOCOL_SCHEMA = (
    "plural-cognition-candidate-pool-v2-qualification-protocol-v1"
)
EXPECTED_CANDIDATE_POOL_V2_PROTOCOL_SHA256 = (
    "f3886fa683aeb5ab3343dc6c388da4b58ebc63f2911be01602fa2fdc2ddaa4b6"
)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def candidate_pool_v2_qualification_protocol_payload() -> dict[str, Any]:
    return {
        "schema": CANDIDATE_POOL_V2_PROTOCOL_SCHEMA,
        "scientific_status": "candidate-development-v2-pre-selection-not-selection-evidence",
        "research_base_revision": "405611be399bb6e5f8139bf898db91f771e15426",
        "v1_selection_outcome_freeze_sha256": "e579e01b0c1d710a4ca303896da84801ef27d9502b66782c88f384129fbe4eb5",
        "v4_development_outcome_freeze_sha256": "93c0d0bd15092e3a7c5d7664461f8542b6d203ff0c64132ad0517183bd370e9a",
        "v5_self_review_outcome_freeze_sha256": "738d1e633c767f09f5d11c46e71eb7e552adfe424b93b826f3834380af7af58d",
        "runtime": {
            "llama_cpp_build": "b10361",
            "llama_cpp_revision": "14e78ddef7a2061e7d5a31dce4eb7ee0bcdbc840",
            "binary_sha256": "115fc69566deb8d1191b4f79bc31f6e8ca7a6f7a951879008f20db796909c381",
            "cuda_runtime_sha256": "8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6",
            "device": "CUDA0",
        },
        "hardware": {
            "gpu": "NVIDIA GeForce RTX 4060 Ti",
            "vram_mib": 16380,
            "compute_capability": "8.9",
            "bf16": True,
        },
        "representation": {
            "output_contract": "raw-full-file-replacement-v1",
            "candidate_output_interpreter": "deterministic-full-file-unified-diff-v1",
            "self_review": False,
            "candidate_output_repair": False,
            "fuzzy_matching": False,
            "max_attempts": 1,
        },
        "resource_budget": {
            "context_tokens": 4096,
            "predict_tokens": 2048,
            "threads": 16,
            "batch_threads": 16,
            "batch_size": 2048,
            "microbatch_size": 512,
            "flash_attention": "auto",
            "temperature": 0.0,
            "seed": 1,
            "full_gpu_offload_required": True,
        },
        "incumbent_candidates": [
            "qwen3-8b-q8",
            "qwen2.5-coder-14b-q5km",
            "devstral-24b-q4km",
        ],
        "retired_from_v2": [
            {
                "candidate_id": "gemma4-12b-it-qat-q4",
                "reason": "persistent empty-final-output transport pathology under frozen resources",
            },
            {
                "candidate_id": "deepseek-coder-v2-lite-q5km",
                "reason": "V4/V5 development left repeated semantic partial repairs despite parse recovery",
            },
        ],
        "challenger_scouts": [
            {
                "candidate_id": "gpt-oss-20b-mxfp4",
                "developer": "OpenAI",
                "source_model": "openai/gpt-oss-20b",
                "target_quantization": "native-mxfp4",
            },
            {
                "candidate_id": "phi-4-reasoning-plus-14b-q5km",
                "developer": "Microsoft",
                "source_model": "microsoft/Phi-4-reasoning-plus",
                "target_quantization": "Q5_K_M",
            },
            {
                "candidate_id": "devstral-small-2-24b-q4km",
                "developer": "Mistral AI",
                "source_model": "mistralai/Devstral-Small-2-24B-Instruct-2512",
                "target_quantization": "Q4_K_M",
            },
        ],
        "source_qualification": {
            "exact_first_party_source_revision_required": True,
            "exact_runtime_artifact_sha256_required": True,
            "community_quantization_allowed_only_with_first_party_source_binding": True,
            "substitution_after_load_outcome": False,
        },
        "load_qualification": {
            "challenger_formal_load_attempts_per_candidate": 1,
            "incumbent_prior_load_evidence_reusable_if_identity_unchanged": True,
            "full_gpu_offload_required": True,
            "fit_mode": False,
        },
        "calibration_gate": {
            "task_count_per_candidate": 6,
            "task_split": "calibration-only",
            "required_parse_valid_count": 6,
            "minimum_solved_count": 4,
            "per_candidate_prompt_tuning_after_observation": False,
            "reruns_for_failed_candidates": False,
        },
        "selection_v2": {
            "requires_new_operational_freeze": True,
            "requires_fresh_untouched_pack": True,
            "task_count": 12,
            "min_valid_rate": 0.95,
            "population_size": 4,
            "selection_run_count": 1,
            "threshold_lowering_after_outcome": False,
            "consumed_v1_material_usable_for_selection_claim": False,
        },
        "stopping_rule": "do-not-run-a-test-unless-pass-versus-fail-can-change-the-next-decision",
    }


FINAL_CANDIDATE_POOL_V2_PROTOCOL_SHA256 = hashlib.sha256(
    _canonical_json_bytes(candidate_pool_v2_qualification_protocol_payload())
).hexdigest()

if FINAL_CANDIDATE_POOL_V2_PROTOCOL_SHA256 != EXPECTED_CANDIDATE_POOL_V2_PROTOCOL_SHA256:
    raise AssertionError("candidate-pool v2 qualification protocol identity drifted")
