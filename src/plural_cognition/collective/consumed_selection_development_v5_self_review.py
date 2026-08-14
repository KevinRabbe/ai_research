"""Development-only V5 same-mind self-review over frozen V4 draft outputs.

V4 whole-file output removed most transport failures but the full consumed development
matrix still contained three failure/partial observations. V5 does not regenerate those
base answers. It treats the immutable V4 assistant output as a frozen draft and adds one
same-candidate review call that may inspect only the same solver-visible issue, repository
files, public examples, and its own previous draft.

No V4 parse error, evaluator score, hidden test, protected expectation, or population
selection information is included in the review prompt. The final reviewed answer uses
the unchanged V4 whole-file output contract and deterministic interpreter.

This remains consumed-split development evidence only. Any later selection claim needs a
new operational freeze and fresh untouched selection material.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .consumed_selection_development_v4 import (
    CANDIDATE_OUTPUT_INTERPRETER_V4,
    DEVELOPMENT_PROTOCOL_SHA256_V4,
    OUTPUT_CONTRACT_V4,
    build_solver_prompt_v4,
    extract_full_file_patch_v4,
)
from .consumed_selection_development_v4_outcome_freeze import (
    FINAL_CONSUMED_SELECTION_DEVELOPMENT_V4_OUTCOME_FREEZE_SHA256,
)
from .local_operational_freeze_v1 import FINAL_RAW_MIND_PROTOCOL, FINAL_RESOURCE_BUDGET_SHA256
from .repository_surgery_selection_outcome_freeze_v1 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256,
)
from .repository_surgery_selection_pack_v1 import SelectionBlueprint

DEVELOPMENT_PROTOCOL_SCHEMA_V5 = "plural-cognition-consumed-selection-development-protocol-v5-self-review"
SELF_REVIEW_PROTOCOL_V5 = "same-mind-visible-draft-self-review-v1"
BASE_DRAFT_PROTOCOL_V5 = "frozen-v4-whole-file-draft-reuse-v1"
REVIEW_PROMPT_REPRESENTATION_V5 = "v4-visible-task-plus-raw-draft-v1"

TARGET_CANDIDATE_IDS_V5 = (
    "qwen3-8b-q8",
    "qwen2.5-coder-14b-q5km",
    "devstral-24b-q4km",
    "deepseek-coder-v2-lite-q5km",
)
TARGET_TASK_IDS_V5 = (
    "repository-surgery-selection-error-handling-0002",
    "repository-surgery-selection-multi-file-0001",
    "repository-surgery-selection-multi-file-0002",
)

TARGET_V4_PARSED_COUNT_V5 = 11
TARGET_V4_SOLVED_COUNT_V5 = 9
TARGET_RESULT_COUNT_V5 = 12
TARGET_MIN_REVIEWED_PARSED_COUNT_V5 = 12
TARGET_MIN_REVIEWED_SOLVED_COUNT_V5 = 11
TARGET_REQUIRED_RECOVERED_FAILURE_COUNT_V5 = 2


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def development_protocol_payload_v5() -> dict[str, object]:
    p = FINAL_RAW_MIND_PROTOCOL
    return {
        "schema": DEVELOPMENT_PROTOCOL_SCHEMA_V5,
        "development_basis": "frozen-v4-consumed-development-outcome",
        "v4_development_protocol_sha256": DEVELOPMENT_PROTOCOL_SHA256_V4,
        "v4_outcome_freeze_sha256": FINAL_CONSUMED_SELECTION_DEVELOPMENT_V4_OUTCOME_FREEZE_SHA256,
        "consumed_selection_outcome_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256,
        "base_draft_protocol": BASE_DRAFT_PROTOCOL_V5,
        "base_draft_regenerated": False,
        "review_protocol": SELF_REVIEW_PROTOCOL_V5,
        "review_prompt_representation": REVIEW_PROMPT_REPRESENTATION_V5,
        "reviewer_identity": "same-candidate-as-draft",
        "review_inference_calls_per_pair": 1,
        "output_contract": OUTPUT_CONTRACT_V4,
        "candidate_output_interpreter": CANDIDATE_OUTPUT_INTERPRETER_V4,
        "target_candidate_ids": list(TARGET_CANDIDATE_IDS_V5),
        "target_task_ids": list(TARGET_TASK_IDS_V5),
        "target_result_count": TARGET_RESULT_COUNT_V5,
        "target_v4_parsed_count": TARGET_V4_PARSED_COUNT_V5,
        "target_v4_solved_count": TARGET_V4_SOLVED_COUNT_V5,
        "continuation_gate": {
            "minimum_reviewed_parsed_count": TARGET_MIN_REVIEWED_PARSED_COUNT_V5,
            "minimum_reviewed_solved_count": TARGET_MIN_REVIEWED_SOLVED_COUNT_V5,
            "minimum_recovered_v4_failure_count": TARGET_REQUIRED_RECOVERED_FAILURE_COUNT_V5,
            "forbid_regression_on_v4_solved_pairs": True,
        },
        "context_tokens": p.context_tokens,
        "predict_tokens": p.predict_tokens,
        "temperature": p.temperature,
        "seed": p.seed,
        "review_max_attempts": 1,
        "resource_budget_sha256": FINAL_RESOURCE_BUDGET_SHA256,
        "fuzzy_matching": False,
        "candidate_output_repair": False,
        "draft_interpreter_feedback_visible_to_reviewer": False,
        "protected_evaluator_visible_to_reviewer": False,
        "population_selection_evidence": False,
    }


DEVELOPMENT_PROTOCOL_SHA256_V5 = hashlib.sha256(
    _canonical_json_bytes(development_protocol_payload_v5())
).hexdigest()


def build_self_review_prompt_v5(blueprint: SelectionBlueprint, draft_output: bytes) -> bytes:
    """Build one same-mind review prompt without evaluator or parser feedback."""

    if type(draft_output) is not bytes:
        raise TypeError("draft_output must be bytes")
    try:
        draft_text = draft_output.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("frozen V4 draft output is not UTF-8") from exc

    base = build_solver_prompt_v4(blueprint).decode("utf-8")
    if not base.endswith("\n"):
        raise AssertionError("V4 base solver prompt must end in one LF")
    base = base[:-1]
    review = (
        base
        + "\n\nSELF_REVIEW_STAGE:\n"
        + "The text between PREVIOUS_DRAFT markers is your own earlier answer for this same task. "
        + "Review it using only the issue, solver-visible repository files, and public examples above. "
        + "You are not receiving parser feedback, hidden tests, evaluator results, or protected expectations.\n"
        + "Before answering, independently check: (1) that you changed the correct file or files, "
        + "(2) that the code actually implements the issue rather than merely looking plausible, "
        + "(3) that each emitted FILE body is a complete corrected file with valid syntax and indentation, "
        + "(4) that unchanged files are omitted, and (5) that diff/search markers or duplicate alternative bodies "
        + "do not appear inside CONTENT.\n"
        + "Return a fresh final answer only in the exact V4 FILE/CONTENT format already specified above. "
        + "You may keep the draft unchanged if it is already correct. Do not explain your review.\n\n"
        + "===== PREVIOUS_DRAFT START =====\n"
        + draft_text
        + ("" if draft_text.endswith("\n") else "\n")
        + "===== PREVIOUS_DRAFT END =====\n"
        + "Now return only the final FILE/CONTENT answer.\n"
    )
    return review.encode("utf-8")


def extract_reviewed_patch_v5(raw: bytes, blueprint: SelectionBlueprint) -> tuple[bytes, str]:
    patch, _ = extract_full_file_patch_v4(raw, blueprint)
    return patch, "raw-full-file-replacement-after-self-review"
