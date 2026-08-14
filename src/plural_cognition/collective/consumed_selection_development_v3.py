"""Development-only V3 raw SEARCH/REPLACE protocol on the consumed V1 split.

V1 selection remains terminal negative evidence. This protocol uses that consumed split
only as development material and changes one candidate-output serialization dimension:
strict JSON exact-replacement objects become literal raw SEARCH/REPLACE blocks.

The semantic edit rule remains exact replacement. SEARCH must occur exactly once in the
current solver-visible file state, blocks apply in listed order, paths remain restricted
to solver-visible existing files, and the harness deterministically materializes a
canonical unified diff. There is no fuzzy matching, output repair, retry, or protected
evaluator access during interpretation.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from .local_operational_freeze_v1 import (
    FINAL_CANDIDATE_IDS,
    FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1,
    FINAL_RAW_MIND_PROTOCOL,
    FINAL_RESOURCE_BUDGET_SHA256,
)
from .repository_surgery_selection_freeze_v1 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256,
)
from .repository_surgery_selection_outcome_freeze_v1 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256,
)
from .repository_surgery_selection_pack_v1 import SelectionBlueprint

DEVELOPMENT_PROTOCOL_SCHEMA = "plural-cognition-consumed-selection-development-protocol-v3"
OUTPUT_CONTRACT = "raw-search-replace-blocks-v1"
CANDIDATE_OUTPUT_INTERPRETER = "deterministic-exact-search-replace-unified-diff-v1"
PROMPT_SOURCE_REPRESENTATION = "plain-source-v1"
MAX_EDITS = 32
_FILE_RE = re.compile(r"^FILE ([^\s]+)$")
SEARCH_MARKER = "<<<<<<< SEARCH"
DIVIDER_MARKER = "======="
REPLACE_MARKER = ">>>>>>> REPLACE"


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def development_protocol_payload_v3() -> dict[str, object]:
    p = FINAL_RAW_MIND_PROTOCOL
    return {
        "schema": DEVELOPMENT_PROTOCOL_SCHEMA,
        "development_basis": "consumed-selection-v1-negative-outcome",
        "consumed_selection_outcome_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256,
        "selection_pack_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256,
        "operational_config_freeze_sha256": FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.sha256,
        "candidate_ids": list(FINAL_CANDIDATE_IDS),
        "prompt_source_representation": PROMPT_SOURCE_REPRESENTATION,
        "output_contract": OUTPUT_CONTRACT,
        "candidate_output_interpreter": CANDIDATE_OUTPUT_INTERPRETER,
        "replacement_semantics": "exactly-once-current-file-state-v1",
        "edit_application": "listed-order-v1",
        "max_edits": MAX_EDITS,
        "context_tokens": p.context_tokens,
        "predict_tokens": p.predict_tokens,
        "temperature": p.temperature,
        "seed": p.seed,
        "max_attempts": p.max_attempts,
        "resource_budget_sha256": FINAL_RESOURCE_BUDGET_SHA256,
        "fuzzy_matching": False,
        "candidate_output_repair": False,
        "protected_evaluator_visible_to_interpreter": False,
    }


DEVELOPMENT_PROTOCOL_SHA256_V3 = hashlib.sha256(_canonical_json_bytes(development_protocol_payload_v3())).hexdigest()


def build_solver_prompt_v3(blueprint: SelectionBlueprint) -> bytes:
    files: list[str] = []
    for path, raw in blueprint.buggy_files:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"solver-visible file is not UTF-8: {path}") from exc
        files.append(f"===== FILE: {path} =====\n{text}===== END FILE =====")
    public = json.dumps(list(blueprint.public_cases), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    issue = blueprint.issue_prompt.decode("utf-8").strip()
    prompt = (
        "You are repairing a small repository. Work only from the issue, repository files, and public examples below. "
        "Return only one or more raw SEARCH/REPLACE blocks and nothing else. Do not use markdown fences or JSON.\n\n"
        "OUTPUT FORMAT:\n"
        "FILE relative/file.py\n"
        "<<<<<<< SEARCH\n"
        "<exact existing source text>\n"
        "=======\n"
        "<exact replacement source text>\n"
        ">>>>>>> REPLACE\n\n"
        "RULES:\n"
        "- SEARCH must be non-empty exact text from the current solver-visible file and must occur exactly once when that block is applied.\n"
        "- Use the smallest unique SEARCH text that safely identifies the intended change; it may be a short expression or one or more full lines.\n"
        "- SEARCH and replacement are literal raw source text. Use real newlines for multiline text; do not JSON-escape quotes or newlines.\n"
        "- Preserve indentation when it is part of the replacement.\n"
        "- Blocks apply in the order emitted. Later SEARCH text is matched against the state after earlier blocks.\n"
        "- FILE must exactly name one solver-visible existing repository file.\n"
        "- Do not include explanations, unchanged context beyond what makes SEARCH unique, or line-number prefixes.\n\n"
        "FORMAT EXAMPLE ONLY (unrelated to the task):\n"
        "FILE demo.txt\n"
        "<<<<<<< SEARCH\n"
        "blue\n"
        "=======\n"
        "green\n"
        ">>>>>>> REPLACE\n"
        "Do not copy the example content. Solve the actual issue below.\n\n"
        f"ISSUE:\n{issue}\n\n"
        + "\n\n".join(files)
        + f"\n\nPUBLIC_EXAMPLES_JSON:\n{public}\n"
    )
    return prompt.encode("utf-8")


@dataclass(frozen=True, slots=True)
class SearchReplaceEdit:
    path: str
    search: str
    replacement: str


def parse_search_replace_blocks(raw: bytes) -> tuple[SearchReplaceEdit, ...]:
    if type(raw) is not bytes:
        raise TypeError("raw must be bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("model output is not UTF-8") from exc
    if "\r" in text:
        raise ValueError("search-replace output must use LF newlines only")
    if text.endswith("\n"):
        text = text[:-1]
    if not text:
        raise ValueError("model output is empty")
    if "```" in text:
        raise ValueError("search-replace output must not use markdown fencing")
    lines = text.split("\n")
    edits: list[SearchReplaceEdit] = []
    cursor = 0
    while cursor < len(lines):
        match = _FILE_RE.fullmatch(lines[cursor])
        if match is None:
            raise ValueError(f"expected FILE header at output line {cursor + 1}")
        path = match.group(1)
        cursor += 1
        if cursor >= len(lines) or lines[cursor] != SEARCH_MARKER:
            raise ValueError(f"expected SEARCH marker at output line {cursor + 1}")
        cursor += 1
        search_start = cursor
        while cursor < len(lines) and lines[cursor] != DIVIDER_MARKER:
            cursor += 1
        if cursor >= len(lines):
            raise ValueError("SEARCH block is missing divider marker")
        search = "\n".join(lines[search_start:cursor])
        if not search:
            raise ValueError(f"edit {len(edits)} SEARCH text must be non-empty")
        cursor += 1
        replace_start = cursor
        while cursor < len(lines) and lines[cursor] != REPLACE_MARKER:
            cursor += 1
        if cursor >= len(lines):
            raise ValueError("replacement block is missing REPLACE marker")
        replacement = "\n".join(lines[replace_start:cursor])
        cursor += 1
        if replacement == search:
            raise ValueError(f"edit {len(edits)} replacement must differ from SEARCH text")
        edits.append(SearchReplaceEdit(path=path, search=search, replacement=replacement))
        if len(edits) > MAX_EDITS:
            raise ValueError("search-replace edit count exceeds development ceiling")
    return tuple(edits)


def _visible_files(blueprint: SelectionBlueprint) -> dict[str, str]:
    files: dict[str, str] = {}
    for path, raw in blueprint.buggy_files:
        try:
            files[path] = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"solver-visible file is not UTF-8: {path}") from exc
    return files


def _apply_search_replace_edits(*, blueprint: SelectionBlueprint, edits: tuple[SearchReplaceEdit, ...]) -> dict[str, str]:
    originals = _visible_files(blueprint)
    state = dict(originals)
    changed_paths: set[str] = set()
    for index, edit in enumerate(edits):
        if edit.path not in state:
            raise ValueError(f"edit {index} path is not solver-visible: {edit.path}")
        current = state[edit.path]
        count = current.count(edit.search)
        if count != 1:
            raise ValueError(f"edit {index} SEARCH text must occur exactly once in {edit.path}; found {count}")
        state[edit.path] = current.replace(edit.search, edit.replacement, 1)
        changed_paths.add(edit.path)
    changed = {path: state[path] for path in sorted(changed_paths) if state[path] != originals[path]}
    if not changed:
        raise ValueError("search-replace edits produced no file modifications")
    return changed


def _canonical_patch(*, blueprint: SelectionBlueprint, changed_files: dict[str, str]) -> bytes:
    originals = _visible_files(blueprint)
    pieces: list[str] = []
    for path in sorted(changed_files):
        pieces.extend(
            difflib.unified_diff(
                originals[path].splitlines(),
                changed_files[path].splitlines(),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                n=3,
                lineterm="",
            )
        )
    if not pieces:
        raise ValueError("search-replace edits produced no canonical diff")
    return ("\n".join(pieces) + "\n").encode("utf-8")


def extract_search_replace_patch(raw: bytes, blueprint: SelectionBlueprint) -> tuple[bytes, str]:
    edits = parse_search_replace_blocks(raw)
    changed = _apply_search_replace_edits(blueprint=blueprint, edits=edits)
    return _canonical_patch(blueprint=blueprint, changed_files=changed), "raw-search-replace"
