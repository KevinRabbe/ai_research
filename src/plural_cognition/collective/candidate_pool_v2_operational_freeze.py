"""Five-survivor candidate-pool v2 operational freeze before fresh selection material exists.

This module is the post-calibration/pre-selection boundary. It binds the completed
36-pair calibration evidence, exact five surviving model artifacts, unchanged V4
whole-file execution protocol, and the predeclared v2 selection rule. It imports
or constructs no selection task material and contains no selection outcomes.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .candidate_pool_v2_calibration_protocol import (
    FINAL_CALIBRATION_PROTOCOL_SHA256_V2,
    INCUMBENT_MODEL_SOURCE_FREEZE_SHA256_V2,
    PREDECESSOR_RESOURCE_BUDGET_SHA256_V2,
)
from .candidate_pool_v2_qualification_protocol import (
    FINAL_CANDIDATE_POOL_V2_PROTOCOL_SHA256,
)
from .candidate_pool_v2_source_freeze import (
    FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256,
    candidate_pool_v2_source_freeze_payload,
)
from .local_models import LOCAL_MODEL_SOURCE_FREEZE_V2

OPERATIONAL_FREEZE_SCHEMA_V2 = "plural-cognition-candidate-pool-v2-operational-freeze-v1"
EXPECTED_OPERATIONAL_FREEZE_SHA256_V2 = (
    "9fabeaaed55d4dfd8a500dec5346450cf5a497ed8f7fb3a65d5fec6b2307380b"
)
CALIBRATION_SOFTWARE_REVISION_V2 = "bf12017cbd288ac52fb9ff674ca998bc0073068e"
CALIBRATION_SUITE_FILE_SHA256_V2 = (
    "1b7b60ee662213af0ab4bf0f80eb90d848aa5bd215b19cd90a696aca34ad84ff"
)
CALIBRATION_SUITE_REPORT_SHA256_V2 = (
    "b779a411f0b809c40cea1a4b3ecd635a1856fe68ab6741cff11b4396f01bffdc"
)

FINAL_CANDIDATE_IDS_V2 = (
    "qwen3-8b-q8",
    "qwen2.5-coder-14b-q5km",
    "devstral-24b-q4km",
    "gpt-oss-20b-mxfp4",
    "devstral-small-2-24b-q4km",
)
ELIMINATED_CANDIDATE_IDS_V2 = ("phi-4-reasoning-plus-14b-q5km",)

_CANDIDATE_ARTIFACTS = {
    "qwen3-8b-q8": ("incumbent-v1", "408b955510e196121c1c375201744783b5c9a43c7956d73fc78df54c66e883d6"),
    "qwen2.5-coder-14b-q5km": ("incumbent-v1", "98ab25e0132e3f1e6d3554e1b64de2b5021908819b740d9c208430117e49a775"),
    "devstral-24b-q4km": ("incumbent-v1", "4a9ec4e1b7fa7b8d3b26e56a54efe251349bb67d8a623bae662353a9d84e4b9b"),
    "gpt-oss-20b-mxfp4": ("challenger-v2", "27cd6c432c7672cb812a92f611cf3ba7bbc35928262bb1e1253ff4ee6ae35901"),
    "devstral-small-2-24b-q4km": ("challenger-v2", "bfd11c8679c6b81eb43763505465d7dcfa72e460ab1c220ecc235a3efadd7f7f"),
}


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def candidate_pool_v2_operational_freeze_payload() -> dict[str, Any]:
    return {
        "schema": OPERATIONAL_FREEZE_SCHEMA_V2,
        "scientific_status": "candidate-pool-v2-final-operational-config-pre-selection",
        "candidate_pool_v2_protocol_sha256": FINAL_CANDIDATE_POOL_V2_PROTOCOL_SHA256,
        "calibration": {
            "software_revision": CALIBRATION_SOFTWARE_REVISION_V2,
            "protocol_sha256": FINAL_CALIBRATION_PROTOCOL_SHA256_V2,
            "suite_file_sha256": CALIBRATION_SUITE_FILE_SHA256_V2,
            "suite_report_sha256": CALIBRATION_SUITE_REPORT_SHA256_V2,
            "pair_count": 36,
            "eligible_candidate_ids": list(FINAL_CANDIDATE_IDS_V2),
            "eliminated_candidate_ids": list(ELIMINATED_CANDIDATE_IDS_V2),
            "selection_evidence": False,
        },
        "execution_protocol": {
            "calibration_protocol_sha256": FINAL_CALIBRATION_PROTOCOL_SHA256_V2,
            "predecessor_resource_budget_sha256": PREDECESSOR_RESOURCE_BUDGET_SHA256_V2,
            "output_contract": "raw-full-file-replacement-v1",
            "candidate_output_interpreter": "deterministic-full-file-unified-diff-v1",
            "self_review": False,
            "candidate_output_repair": False,
            "fuzzy_matching": False,
            "max_attempts": 1,
        },
        "source_freezes": {
            "incumbent_model_source_freeze_sha256": INCUMBENT_MODEL_SOURCE_FREEZE_SHA256_V2,
            "challenger_source_freeze_sha256": FINAL_CANDIDATE_POOL_V2_SOURCE_FREEZE_SHA256,
        },
        "candidates": [
            {
                "candidate_id": candidate_id,
                "source_class": _CANDIDATE_ARTIFACTS[candidate_id][0],
                "artifact_sha256": _CANDIDATE_ARTIFACTS[candidate_id][1],
            }
            for candidate_id in FINAL_CANDIDATE_IDS_V2
        ],
        "selection_v2": {
            "task_count": 12,
            "min_valid_rate": 0.95,
            "population_size": 4,
            "selection_run_count": 1,
            "threshold_lowering_after_outcome": False,
            "requires_fresh_untouched_pack": True,
        },
    }


FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256 = hashlib.sha256(
    _canonical_json_bytes(candidate_pool_v2_operational_freeze_payload())
).hexdigest()


def validate_operational_freeze_against_repository() -> None:
    if FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256 != EXPECTED_OPERATIONAL_FREEZE_SHA256_V2:
        raise AssertionError("candidate-pool v2 operational freeze identity drifted")
    if LOCAL_MODEL_SOURCE_FREEZE_V2.sha256 != INCUMBENT_MODEL_SOURCE_FREEZE_SHA256_V2:
        raise AssertionError("incumbent source freeze identity drifted")

    incumbent_ids = FINAL_CANDIDATE_IDS_V2[:3]
    for candidate_id in incumbent_ids:
        source = LOCAL_MODEL_SOURCE_FREEZE_V2.candidate(candidate_id)
        if source.artifact_sha256 != _CANDIDATE_ARTIFACTS[candidate_id][1]:
            raise AssertionError(f"incumbent artifact identity drifted: {candidate_id}")

    challenger_payload = candidate_pool_v2_source_freeze_payload()
    challengers = {item["candidate_id"]: item for item in challenger_payload["challengers"]}
    for candidate_id in FINAL_CANDIDATE_IDS_V2[3:]:
        if challengers[candidate_id]["artifact_sha256"] != _CANDIDATE_ARTIFACTS[candidate_id][1]:
            raise AssertionError(f"challenger artifact identity drifted: {candidate_id}")

    if ELIMINATED_CANDIDATE_IDS_V2[0] not in challengers:
        raise AssertionError("eliminated Phi candidate identity disappeared from v2 source freeze")


validate_operational_freeze_against_repository()
