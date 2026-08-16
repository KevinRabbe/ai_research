"""Freeze the three candidate-pool v3 expansion scout artifacts before inference."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .candidate_pool_v3_expansion_protocol import (
    EXPECTED_CANDIDATE_POOL_V3_EXPANSION_PROTOCOL_SHA256,
    EXPANSION_SCOUT_COUNT_V3,
    validate_candidate_pool_v3_expansion_protocol,
)

CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SCHEMA = (
    "plural-cognition-candidate-pool-v3-expansion-source-freeze-v1"
)
EXPANSION_SOURCE_FREEZE_PREDECESSOR_REVISION = (
    "1f51f19083f3e0ab7cc4f85e9bb77ef91d40d385"
)
EXPECTED_CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SHA256 = (
    "7e3a49def60361dc2ce82f32c750d44b4dd0cb2d024b79f76d8469be3e2bec03"
)
EXPANSION_SCOUT_IDS_V3 = (
    "qwen3-14b-q5km",
    "ministral-3-14b-instruct-2512-q5km",
    "ministral-3-8b-instruct-2512-q5km",
)

_EXPECTED_SCOUTS = (
    {
        "candidate_id": "qwen3-14b-q5km",
        "developer": "Qwen",
        "first_party_repo": "Qwen/Qwen3-14B-GGUF",
        "source_revision": "c75e7b2d0234068f674a1bacf548ea32e27ccd29",
        "artifact_revision": "c75e7b2d0234068f674a1bacf548ea32e27ccd29",
        "artifact_filename": "Qwen3-14B-Q5_K_M.gguf",
        "quantization": "Q5_K_M",
        "artifact_size_bytes": 10_514_569_568,
        "artifact_sha256": "e7c9aba1129ca2936be9eca01419d9f86af40e08caa01230d5574b34d08e3e31",
        "license": "apache-2.0",
        "first_party_artifact": True,
        "llama_cpp_usage_documented": True,
        "previously_measured_artifact": False,
        "immutable_download_url": (
            "https://huggingface.co/Qwen/Qwen3-14B-GGUF/resolve/"
            "c75e7b2d0234068f674a1bacf548ea32e27ccd29/Qwen3-14B-Q5_K_M.gguf"
        ),
    },
    {
        "candidate_id": "ministral-3-14b-instruct-2512-q5km",
        "developer": "Mistral AI",
        "first_party_repo": "mistralai/Ministral-3-14B-Instruct-2512-GGUF",
        "source_revision": "fb49df4a3cde2c774da8def12437118a66c4f5cf",
        "artifact_revision": "fb49df4a3cde2c774da8def12437118a66c4f5cf",
        "artifact_filename": "Ministral-3-14B-Instruct-2512-Q5_K_M.gguf",
        "quantization": "Q5_K_M",
        "artifact_size_bytes": 9_621_091_904,
        "artifact_sha256": "f16fef77021df0d4c22e69140a2038478370492f51867b6237699918ae711000",
        "license": "apache-2.0",
        "first_party_artifact": True,
        "llama_cpp_usage_documented": True,
        "previously_measured_artifact": False,
        "immutable_download_url": (
            "https://huggingface.co/mistralai/Ministral-3-14B-Instruct-2512-GGUF/resolve/"
            "fb49df4a3cde2c774da8def12437118a66c4f5cf/"
            "Ministral-3-14B-Instruct-2512-Q5_K_M.gguf"
        ),
    },
    {
        "candidate_id": "ministral-3-8b-instruct-2512-q5km",
        "developer": "Mistral AI",
        "first_party_repo": "mistralai/Ministral-3-8B-Instruct-2512-GGUF",
        "source_revision": "65457cc28fafb2210c8fb885a068b107e8d7fab3",
        "artifact_revision": "65457cc28fafb2210c8fb885a068b107e8d7fab3",
        "artifact_filename": "Ministral-3-8B-Instruct-2512-Q5_K_M.gguf",
        "quantization": "Q5_K_M",
        "artifact_size_bytes": 6_059_268_512,
        "artifact_sha256": "7a5454127ec772e2389f0e71a77fedb88b83d4366d8a69facd0cfd0898f04d35",
        "license": "apache-2.0",
        "first_party_artifact": True,
        "llama_cpp_usage_documented": True,
        "previously_measured_artifact": False,
        "immutable_download_url": (
            "https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512-GGUF/resolve/"
            "65457cc28fafb2210c8fb885a068b107e8d7fab3/"
            "Ministral-3-8B-Instruct-2512-Q5_K_M.gguf"
        ),
    },
)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def candidate_pool_v3_expansion_source_freeze_payload() -> dict[str, Any]:
    return {
        "schema": CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SCHEMA,
        "scientific_status": (
            "candidate-pool-v3-expansion-three-scout-source-freeze-before-new-model-inference"
        ),
        "predecessor_expansion_protocol_revision": (
            EXPANSION_SOURCE_FREEZE_PREDECESSOR_REVISION
        ),
        "predecessor_expansion_protocol_sha256": (
            EXPECTED_CANDIDATE_POOL_V3_EXPANSION_PROTOCOL_SHA256
        ),
        "scout_order": list(EXPANSION_SCOUT_IDS_V3),
        "scouts": [dict(item) for item in _EXPECTED_SCOUTS],
        "selection_basis": {
            "task_specific_evidence_used": False,
            "consumed_v3_calibration_task_outputs_used": False,
            "candidate_specific_prompt_tuning_used": False,
            "allowed_metadata_only": True,
            "ordering_rule": [
                "plausible-capability-under-frozen-16gib-full-offload-budget",
                "first-party-artifact-provenance",
                "general-or-code-instruction-suitability",
                "prefer-larger-clean-artifact-before-smaller-backup-within-source-qualified-set",
            ],
            "granite_excluded_for_missing_exact_byte_count_at_source-freeze-authoring": True,
        },
        "authorization": {
            "candidate_model_calls_consumed_before_source_freeze": 0,
            "new_model_inference_authorized": False,
            "load_qualification_runner_authoring_authorized_after_green": True,
            "load_inference_authorized": False,
            "calibration_runner_authoring_authorized": False,
            "calibration_inference_authorized": False,
            "selection_pack_authoring_authorized": False,
            "selection_inference_authorized": False,
            "plural_synthesis_authorized": False,
            "artifact_substitution_authorized": False,
            "scout_reordering_authorized": False,
            "additional_scout_authoring_authorized": False,
        },
    }


def validate_candidate_pool_v3_expansion_source_freeze() -> None:
    validate_candidate_pool_v3_expansion_protocol()
    payload = candidate_pool_v3_expansion_source_freeze_payload()

    if payload["predecessor_expansion_protocol_sha256"] != (
        EXPECTED_CANDIDATE_POOL_V3_EXPANSION_PROTOCOL_SHA256
    ):
        raise RuntimeError("v3 expansion source-freeze predecessor drifted")
    if len(payload["scouts"]) != EXPANSION_SCOUT_COUNT_V3 or len(payload["scouts"]) != 3:
        raise RuntimeError("v3 expansion source freeze must contain exactly three scouts")
    if tuple(payload["scout_order"]) != EXPANSION_SCOUT_IDS_V3:
        raise RuntimeError("v3 expansion scout order drifted")
    if tuple(item["candidate_id"] for item in payload["scouts"]) != EXPANSION_SCOUT_IDS_V3:
        raise RuntimeError("v3 expansion scout identities drifted")

    seen_hashes: set[str] = set()
    for item in payload["scouts"]:
        if item["source_revision"] != item["artifact_revision"]:
            raise RuntimeError("first-party GGUF source/artifact revision must be identical")
        if len(item["artifact_revision"]) != 40:
            raise RuntimeError("artifact revision must be a full commit SHA")
        int(item["artifact_revision"], 16)
        if type(item["artifact_size_bytes"]) is not int or item["artifact_size_bytes"] <= 0:
            raise RuntimeError("artifact byte size must be exact and positive")
        digest = item["artifact_sha256"]
        if len(digest) != 64:
            raise RuntimeError("artifact SHA-256 must be full length")
        int(digest, 16)
        if digest in seen_hashes:
            raise RuntimeError("expansion scout artifacts must have distinct identities")
        seen_hashes.add(digest)
        if not item["first_party_artifact"]:
            raise RuntimeError("expansion scout artifact must be first-party")
        if not item["llama_cpp_usage_documented"]:
            raise RuntimeError("expansion scout must have documented llama.cpp usage")
        if item["previously_measured_artifact"]:
            raise RuntimeError("previously measured artifacts cannot become expansion scouts")
        if item["license"] != "apache-2.0":
            raise RuntimeError("expansion scout license drifted")
        expected_url_fragment = f"/resolve/{item['artifact_revision']}/{item['artifact_filename']}"
        if expected_url_fragment not in item["immutable_download_url"]:
            raise RuntimeError("expansion scout download URL is not revision-pinned")

    basis = payload["selection_basis"]
    if basis["task_specific_evidence_used"]:
        raise RuntimeError("task-specific evidence cannot influence expansion scouting")
    if basis["consumed_v3_calibration_task_outputs_used"]:
        raise RuntimeError("consumed calibration outputs cannot influence expansion scouting")
    if basis["candidate_specific_prompt_tuning_used"]:
        raise RuntimeError("candidate-specific prompt tuning cannot influence source scouting")
    if not basis["allowed_metadata_only"]:
        raise RuntimeError("expansion source selection must remain metadata-only")

    authorization = payload["authorization"]
    if authorization["candidate_model_calls_consumed_before_source_freeze"] != 0:
        raise RuntimeError("new model calls occurred before source freeze")
    forbidden = (
        "new_model_inference_authorized",
        "load_inference_authorized",
        "calibration_runner_authoring_authorized",
        "calibration_inference_authorized",
        "selection_pack_authoring_authorized",
        "selection_inference_authorized",
        "plural_synthesis_authorized",
        "artifact_substitution_authorized",
        "scout_reordering_authorized",
        "additional_scout_authoring_authorized",
    )
    if any(authorization[field] for field in forbidden):
        raise RuntimeError("v3 expansion source freeze improperly authorizes continuation")
    if not authorization["load_qualification_runner_authoring_authorized_after_green"]:
        raise RuntimeError("green source freeze must authorize load-runner authoring")

    digest = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    if digest != EXPECTED_CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SHA256:
        raise RuntimeError("candidate-pool v3 expansion source-freeze identity drifted")


FINAL_CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE = (
    candidate_pool_v3_expansion_source_freeze_payload()
)
FINAL_CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SHA256 = (
    EXPECTED_CANDIDATE_POOL_V3_EXPANSION_SOURCE_FREEZE_SHA256
)

validate_candidate_pool_v3_expansion_source_freeze()
