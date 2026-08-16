"""Freeze the positive candidate-pool v3 expansion calibration outcome.

The first pre-frozen expansion scout completed exactly six development-calibration
pairs and passed the unchanged v3 gate. The sequential protocol therefore stopped
without evaluating either later scout. This freeze binds that positive outcome,
the resulting exact four-member development population, and the boundary that
selection work must begin with a fresh untouched pack.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .candidate_pool_v3_calibration_outcome_freeze import (
    CALIBRATION_ELIGIBLE_CANDIDATE_IDS_V3,
    CALIBRATION_REQUIRED_POPULATION_SIZE_V3,
    EXPECTED_CALIBRATION_OUTCOME_FREEZE_SHA256_V3,
    validate_candidate_pool_v3_calibration_outcome_freeze,
)
from .candidate_pool_v3_expansion_calibration_runner_freeze import (
    EXPECTED_EXPANSION_CALIBRATION_RUNNER_FREEZE_SHA256_V3,
    validate_candidate_pool_v3_expansion_calibration_runner_freeze,
)
from .candidate_pool_v3_expansion_load_outcome_freeze import (
    EXPECTED_EXPANSION_LOAD_OUTCOME_FREEZE_SHA256_V3,
)
from .candidate_pool_v3_expansion_source_freeze import EXPANSION_SCOUT_IDS_V3
from .candidate_pool_v3_representation_protocol import (
    EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256,
    V3_MINIMUM_SOLVED_COUNT,
    V3_REQUIRED_PARSE_VALID_COUNT,
    V3_SELECTION_MIN_VALID_RATE,
    V3_SELECTION_POPULATION_SIZE,
)
from .local_candidate_pool_v3_expansion_calibration import (
    EXPANSION_CALIBRATION_ARTIFACT_ROOT_V3,
    EXPECTED_EXPANSION_CALIBRATION_RUNNER_PROTOCOL_SHA256_V3,
)
from .repository_surgery_calibration_pack_v3 import CALIBRATION_TASK_IDS_V3
from .repository_surgery_calibration_qualification_freeze_v3 import (
    EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3,
    REPAIRED_CALIBRATION_PACK_CANONICAL_SHA256_V3,
)

EXPANSION_CALIBRATION_OUTCOME_FREEZE_SCHEMA_V3 = (
    "plural-cognition-candidate-pool-v3-expansion-calibration-outcome-freeze-v1"
)
EXPANSION_CALIBRATION_OUTCOME_SCIENTIFIC_STATUS_V3 = (
    "candidate-pool-v3-expansion-calibration-positive-four-member-population"
)
EXPANSION_CALIBRATION_OUTCOME_SOFTWARE_REVISION_V3 = (
    "ac7f15152d12e56a3062aa72276dc8b9292c14b7"
)
EXPANSION_CALIBRATION_SUITE_FILE_SHA256_V3 = (
    "bb628f97e9775b997369449bffe1a128ff11f3c05fa4bbc023b462fb2aac7c68"
)
EXPANSION_CALIBRATION_REPORT_SHA256_V3 = (
    "6c54e6b3b57752dbde1bacc9f2bd2b5fdb6264a26bcdb63692d7510dabf7aa2a"
)
EXPECTED_EXPANSION_CALIBRATION_OUTCOME_FREEZE_SHA256_V3 = (
    "d39b2d3da6d156485e957e8e37f7eb2e961364e45c936fd15b673f67ecc61f12"
)

EXPANSION_CALIBRATION_PAIR_COUNT_V3 = 6
EXPANSION_CALIBRATION_NEW_INFERENCE_ATTEMPT_COUNT_V3 = 6
EXPANSION_CALIBRATION_MODEL_CALLS_CONSUMED_V3 = 6
EXPANSION_CALIBRATION_PASSING_CANDIDATE_ID_V3 = "qwen3-14b-q5km"

EXPANSION_CALIBRATION_EVALUATED_CANDIDATE_IDS_V3 = (
    EXPANSION_CALIBRATION_PASSING_CANDIDATE_ID_V3,
)
EXPANSION_CALIBRATION_UNEVALUATED_CANDIDATE_IDS_V3 = (
    "ministral-3-14b-instruct-2512-q5km",
    "ministral-3-8b-instruct-2512-q5km",
)
EXPANSION_NEW_ELIGIBLE_CANDIDATE_IDS_V3 = (
    EXPANSION_CALIBRATION_PASSING_CANDIDATE_ID_V3,
)
V3_FROZEN_POPULATION_CANDIDATE_IDS = (
    *CALIBRATION_ELIGIBLE_CANDIDATE_IDS_V3,
    *EXPANSION_NEW_ELIGIBLE_CANDIDATE_IDS_V3,
)

_EXPANSION_PAIR_REPORTS_V3 = (
    (
        "repository-surgery-calibration-v3-api-contract-0001",
        True,
        True,
        "67756ff5bc8782085cba08f90f597ed8fe5798350084263402e37e2d5469fb65",
    ),
    (
        "repository-surgery-calibration-v3-boundary-0001",
        True,
        True,
        "cc0fe64840e9fc0e2f01d1ebcd1db25105c89ff7b7e4d8badf56f85354f21357",
    ),
    (
        "repository-surgery-calibration-v3-error-handling-0001",
        True,
        False,
        "a4604fd4d228052aef33f7246a092dc125e5cdae5b82803d227ed1146579a0a0",
    ),
    (
        "repository-surgery-calibration-v3-local-logic-0001",
        True,
        True,
        "893da3b2e783f21adcdba5d4c5b87b70e0df492799fbbf8a3e130b92a0992cc2",
    ),
    (
        "repository-surgery-calibration-v3-multi-file-0001",
        True,
        True,
        "8bca07bba6297cfc9902365c0547331aaaa35c2b831e3d1685144955acff6b6d",
    ),
    (
        "repository-surgery-calibration-v3-state-management-0001",
        True,
        True,
        "ad224b0333485d0604299335f84f81fe98b836aeba4a92d2940d0301b57482f8",
    ),
)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def candidate_pool_v3_expansion_calibration_outcome_freeze_payload() -> dict[str, Any]:
    return {
        "schema": EXPANSION_CALIBRATION_OUTCOME_FREEZE_SCHEMA_V3,
        "scientific_status": EXPANSION_CALIBRATION_OUTCOME_SCIENTIFIC_STATUS_V3,
        "software_revision": EXPANSION_CALIBRATION_OUTCOME_SOFTWARE_REVISION_V3,
        "artifact_root": EXPANSION_CALIBRATION_ARTIFACT_ROOT_V3,
        "suite_file_sha256": EXPANSION_CALIBRATION_SUITE_FILE_SHA256_V3,
        "report_sha256": EXPANSION_CALIBRATION_REPORT_SHA256_V3,
        "runner_protocol_sha256": EXPECTED_EXPANSION_CALIBRATION_RUNNER_PROTOCOL_SHA256_V3,
        "runner_freeze_sha256": EXPECTED_EXPANSION_CALIBRATION_RUNNER_FREEZE_SHA256_V3,
        "load_outcome_freeze_sha256": EXPECTED_EXPANSION_LOAD_OUTCOME_FREEZE_SHA256_V3,
        "predecessor_calibration_outcome_freeze_sha256": (
            EXPECTED_CALIBRATION_OUTCOME_FREEZE_SHA256_V3
        ),
        "qualification_freeze_sha256": (
            EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3
        ),
        "representation_protocol_sha256": EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256,
        "repaired_calibration_pack_sha256": (
            REPAIRED_CALIBRATION_PACK_CANONICAL_SHA256_V3
        ),
        "scout_ids": list(EXPANSION_SCOUT_IDS_V3),
        "task_ids": list(CALIBRATION_TASK_IDS_V3),
        "gate": {
            "required_parse_valid_count": V3_REQUIRED_PARSE_VALID_COUNT,
            "minimum_solved_count": V3_MINIMUM_SOLVED_COUNT,
        },
        "pair_count": EXPANSION_CALIBRATION_PAIR_COUNT_V3,
        "new_inference_attempt_count": (
            EXPANSION_CALIBRATION_NEW_INFERENCE_ATTEMPT_COUNT_V3
        ),
        "candidate_model_calls_consumed": EXPANSION_CALIBRATION_MODEL_CALLS_CONSUMED_V3,
        "evaluated_candidate_ids": list(EXPANSION_CALIBRATION_EVALUATED_CANDIDATE_IDS_V3),
        "unevaluated_candidate_ids": list(
            EXPANSION_CALIBRATION_UNEVALUATED_CANDIDATE_IDS_V3
        ),
        "passing_candidate_id": EXPANSION_CALIBRATION_PASSING_CANDIDATE_ID_V3,
        "stopped_after_first_gate_pass": True,
        "summary": {
            "candidate_id": EXPANSION_CALIBRATION_PASSING_CANDIDATE_ID_V3,
            "task_count": 6,
            "parse_valid_count": 6,
            "solved_count": 5,
            "passed_calibration_gate": True,
            "peak_gpu_used_mib": 15338,
        },
        "pair_reports": [
            {
                "task_id": task_id,
                "parse_valid": parse_valid,
                "solved": solved,
                "report_sha256": report_sha256,
            }
            for task_id, parse_valid, solved, report_sha256 in _EXPANSION_PAIR_REPORTS_V3
        ],
        "predecessor_evidence_fingerprints": {
            "e3l": "2a4aade4a78f45eb0160963b6d90e3f8c5f2d2cd63250570a23873f4b4fce5b4",
            "c3q-r1": "200c70894de8c017d25b11074c2d7b89333fd47165134d23e46c590029a41a71",
            "c3": "492e44a3efe9bbef19a3abb6ae2ed592a481de4e6e9cb73bdc9feaafc6098a3f",
        },
        "existing_eligible_candidate_ids": list(CALIBRATION_ELIGIBLE_CANDIDATE_IDS_V3),
        "new_eligible_candidate_ids": list(EXPANSION_NEW_ELIGIBLE_CANDIDATE_IDS_V3),
        "frozen_population_candidate_ids": list(V3_FROZEN_POPULATION_CANDIDATE_IDS),
        "eligible_candidate_count": len(V3_FROZEN_POPULATION_CANDIDATE_IDS),
        "required_population_size": CALIBRATION_REQUIRED_POPULATION_SIZE_V3,
        "population_feasible": True,
        "selection_evidence": False,
        "authorization": {
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
            "selection_population_size": V3_SELECTION_POPULATION_SIZE,
            "selection_min_valid_rate": V3_SELECTION_MIN_VALID_RATE,
        },
    }


def validate_candidate_pool_v3_expansion_calibration_outcome_freeze() -> None:
    validate_candidate_pool_v3_calibration_outcome_freeze()
    validate_candidate_pool_v3_expansion_calibration_runner_freeze()
    payload = candidate_pool_v3_expansion_calibration_outcome_freeze_payload()

    if tuple(payload["scout_ids"]) != EXPANSION_SCOUT_IDS_V3:
        raise RuntimeError("v3 expansion calibration scout order drifted")
    if tuple(payload["task_ids"]) != CALIBRATION_TASK_IDS_V3:
        raise RuntimeError("v3 expansion calibration task order drifted")
    if payload["gate"] != {
        "required_parse_valid_count": 6,
        "minimum_solved_count": 4,
    }:
        raise RuntimeError("v3 expansion calibration gate drifted")
    if payload["pair_count"] != 6:
        raise RuntimeError("v3 expansion calibration pair count drifted")
    if payload["new_inference_attempt_count"] != 6:
        raise RuntimeError("v3 expansion calibration attempt count drifted")
    if payload["candidate_model_calls_consumed"] != 6:
        raise RuntimeError("v3 expansion calibration consumed-call count drifted")
    if tuple(payload["evaluated_candidate_ids"]) != (
        EXPANSION_CALIBRATION_PASSING_CANDIDATE_ID_V3,
    ):
        raise RuntimeError("v3 expansion evaluated scout set drifted")
    if tuple(payload["unevaluated_candidate_ids"]) != (
        EXPANSION_SCOUT_IDS_V3[1:]
    ):
        raise RuntimeError("v3 expansion unevaluated scout suffix drifted")
    if not payload["stopped_after_first_gate_pass"]:
        raise RuntimeError("v3 expansion must retain first-pass stopping")
    summary = payload["summary"]
    if (
        summary["parse_valid_count"] != 6
        or summary["solved_count"] != 5
        or not summary["passed_calibration_gate"]
    ):
        raise RuntimeError("v3 expansion passing summary drifted")
    if len(payload["pair_reports"]) != 6:
        raise RuntimeError("v3 expansion pair-report count drifted")
    if tuple(item["task_id"] for item in payload["pair_reports"]) != CALIBRATION_TASK_IDS_V3:
        raise RuntimeError("v3 expansion pair-report task order drifted")
    if sum(bool(item["parse_valid"]) for item in payload["pair_reports"]) != 6:
        raise RuntimeError("v3 expansion parse-valid total drifted")
    if sum(bool(item["solved"]) for item in payload["pair_reports"]) != 5:
        raise RuntimeError("v3 expansion solved total drifted")

    if tuple(payload["existing_eligible_candidate_ids"]) != (
        CALIBRATION_ELIGIBLE_CANDIDATE_IDS_V3
    ):
        raise RuntimeError("v3 existing eligible population drifted")
    if tuple(payload["new_eligible_candidate_ids"]) != (
        EXPANSION_CALIBRATION_PASSING_CANDIDATE_ID_V3,
    ):
        raise RuntimeError("v3 new eligible candidate drifted")
    if tuple(payload["frozen_population_candidate_ids"]) != (
        V3_FROZEN_POPULATION_CANDIDATE_IDS
    ):
        raise RuntimeError("v3 frozen population order drifted")
    if payload["eligible_candidate_count"] != 4:
        raise RuntimeError("v3 frozen eligible count drifted")
    if payload["required_population_size"] != 4 or not payload["population_feasible"]:
        raise RuntimeError("v3 population feasibility drifted")
    if payload["selection_evidence"]:
        raise RuntimeError("v3 expansion calibration cannot become selection evidence")

    authorization = payload["authorization"]
    forbidden = (
        "expansion_calibration_rerun_authorized",
        "calibration_gate_lowering_authorized",
        "candidate_specific_tuning_authorized",
        "evaluate_unevaluated_scouts_after_pass_authorized",
        "automatic_candidate_replacement_authorized",
        "population_substitution_authorized",
        "selection_inference_authorized",
        "plural_synthesis_authorized",
    )
    if any(authorization[field] for field in forbidden):
        raise RuntimeError("v3 expansion outcome improperly authorizes continuation")
    if not authorization["fresh_selection_pack_authoring_authorized_after_green"]:
        raise RuntimeError("green positive outcome must authorize fresh selection-pack authoring")
    if not authorization["selection_pack_must_be_fresh_and_untouched"]:
        raise RuntimeError("v3 selection pack must remain fresh and untouched")
    if authorization["selection_pack_task_count"] != 12:
        raise RuntimeError("v3 future selection task count drifted")
    if authorization["selection_population_size"] != 4:
        raise RuntimeError("v3 future selection population size drifted")
    if authorization["selection_min_valid_rate"] != 0.95:
        raise RuntimeError("v3 future selection valid-rate threshold drifted")

    digest = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    if digest != EXPECTED_EXPANSION_CALIBRATION_OUTCOME_FREEZE_SHA256_V3:
        raise RuntimeError(
            f"v3 expansion calibration outcome freeze identity drifted: {digest}"
        )


FINAL_CANDIDATE_POOL_V3_EXPANSION_CALIBRATION_OUTCOME_FREEZE = (
    candidate_pool_v3_expansion_calibration_outcome_freeze_payload()
)
FINAL_CANDIDATE_POOL_V3_EXPANSION_CALIBRATION_OUTCOME_FREEZE_SHA256 = (
    EXPECTED_EXPANSION_CALIBRATION_OUTCOME_FREEZE_SHA256_V3
)

validate_candidate_pool_v3_expansion_calibration_outcome_freeze()
