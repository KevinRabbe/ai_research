"""Development-only V2 protocol for the consumed V1 selection split.

The frozen V1 selection outcome is terminal evidence and is never reinterpreted as a
selection success.  This module uses that now-consumed split only as development
material.  It changes one protocol dimension: candidate edit anchoring/serialization.

V1 required strict JSON ``old``/``new`` exact-text replacements.  The negative outcome
showed near-correct repairs failing because candidates copied anchors or JSON escaping
incorrectly.  V2 instead shows immutable source lines with explicit 1-based line labels
and accepts strict line-span edit blocks whose replacement payload is raw source text.
All coordinates refer to the original solver-visible file.  The harness deterministically
materializes a canonical unified diff; it does not fuzzy-match, salvage, repair, or
consult protected evaluator material while interpreting candidate output.

This protocol is development-only.  Any later population-selection claim requires a
new operational freeze and a fresh untouched selection pack.
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

DEVELOPMENT_PROTOCOL_SCHEMA = "plural-cognition-consumed-selection-development-protocol-v2"
OUTPUT_CONTRACT = "original-line-span-raw-v1"
CANDIDATE_OUTPUT_INTERPRETER = "deterministic-original-line-span-unified-diff-v1"
PROMPT_SOURCE_REPRESENTATION = "line-numbered-source-v1"
MAX_LINE_SPAN_EDITS = 32
_HEADER_RE = re.compile(r"^EDIT ([^\s]+) ([1-9][0-9]*) ([0-9]+) ([0-9]+)$")


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def development_protocol_payload_v2() -> dict[str, object]:
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
        "line_number_basis": "original-file-1-based",
        "max_edits": MAX_LINE_SPAN_EDITS,
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


DEVELOPMENT_PROTOCOL_SHA256_V2 = hashlib.sha256(
    _canonical_json_bytes(development_protocol_payload_v2())
).hexdigest()


def _numbered_file(path: str, raw: bytes) -> str:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"solver-visible file is not UTF-8: {path}") from exc
    lines = text.splitlines()
    width = max(4, len(str(max(1, len(lines)))))
    body = "\n".join(f"L{index:0{width}d}|{line}" for index, line in enumerate(lines, start=1))
    return f"===== FILE: {path} =====\n{body}\n===== END FILE ====="


def build_solver_prompt_v2(blueprint: SelectionBlueprint) -> bytes:
    """Build development-only line-numbered solver input for one consumed task."""

    files = [_numbered_file(path, raw) for path, raw in blueprint.buggy_files]
    public = json.dumps(
        list(blueprint.public_cases),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    issue = blueprint.issue_prompt.decode("utf-8").strip()
    prompt = (
        "You are repairing a small repository. Work only from the issue, repository "
        "files, and public examples below. Return only one or more EDIT blocks and "
        "nothing else. Do not use markdown fences or JSON.\n\n"
        "OUTPUT FORMAT:\n"
        "EDIT relative/file.py START DELETE INSERT\n"
        "<exact raw replacement line 1>\n"
        "<exact raw replacement line 2 if INSERT is 2>\n\n"
        "RULES:\n"
        "- Each EDIT header has exactly: path, 1-based START line, DELETE line count, INSERT line count.\n"
        "- START coordinates always refer to the ORIGINAL numbered file shown below, not to a state after earlier edits.\n"
        "- After each header, output exactly INSERT raw replacement lines. Do not quote or JSON-escape them.\n"
        "- The L0001| style prefixes are reference labels only. Never copy a line label into replacement text.\n"
        "- path must exactly name one solver-visible repository file.\n"
        "- Multiple edits to the same file must not overlap.\n"
        "- DELETE and INSERT may be zero, but they may not both be zero.\n"
        "- Make the smallest repair needed. Do not include explanations or unchanged context.\n\n"
        "FORMAT EXAMPLE ONLY (unrelated to the task):\n"
        "EDIT demo.txt 3 1 1\n"
        "green\n"
        "Do not copy the example content. Solve the actual issue below.\n\n"
        f"ISSUE:\n{issue}\n\n"
        + "\n\n".join(files)
        + f"\n\nPUBLIC_EXAMPLES_JSON:\n{public}\n"
    )
    return prompt.encode("utf-8")


@dataclass(frozen=True, slots=True)
class LineSpanEdit:
    path: str
    start_line: int
    delete_count: int
    insert_lines: tuple[str, ...]

    @property
    def insert_count(self) -> int:
        return len(self.insert_lines)


def parse_line_span_edits(raw: bytes) -> tuple[LineSpanEdit, ...]:
    """Parse strict raw line-span blocks without fuzzy matching or repair."""

    if type(raw) is not bytes:
        raise TypeError("raw must be bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("model output is not UTF-8") from exc
    if "\r" in text:
        raise ValueError("line-span output must use LF newlines only")
    if text.endswith("\n"):
        text = text[:-1]
    if not text:
        raise ValueError("model output is empty")
    if "```" in text:
        raise ValueError("line-span output must not use markdown fencing")

    lines = text.split("\n")
    edits: list[LineSpanEdit] = []
    cursor = 0
    while cursor < len(lines):
        match = _HEADER_RE.fullmatch(lines[cursor])
        if match is None:
            raise ValueError(f"expected EDIT header at output line {cursor + 1}")
        path, start_raw, delete_raw, insert_raw = match.groups()
        start_line = int(start_raw)
        delete_count = int(delete_raw)
        insert_count = int(insert_raw)
        if delete_count == 0 and insert_count == 0:
            raise ValueError(f"edit {len(edits)} cannot have DELETE=0 and INSERT=0")
        cursor += 1
        if cursor + insert_count > len(lines):
            raise ValueError(f"edit {len(edits)} declares more replacement lines than were emitted")
        replacement = tuple(lines[cursor : cursor + insert_count])
        cursor += insert_count
        edits.append(
            LineSpanEdit(
                path=path,
                start_line=start_line,
                delete_count=delete_count,
                insert_lines=replacement,
            )
        )
        if len(edits) > MAX_LINE_SPAN_EDITS:
            raise ValueError("line-span edit count exceeds development ceiling")
    return tuple(edits)


def _visible_files(blueprint: SelectionBlueprint) -> dict[str, str]:
    files: dict[str, str] = {}
    for path, raw in blueprint.buggy_files:
        try:
            files[path] = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"solver-visible file is not UTF-8: {path}") from exc
    return files


def _apply_line_span_edits(
    *, blueprint: SelectionBlueprint, edits: tuple[LineSpanEdit, ...]
) -> dict[str, str]:
    originals = _visible_files(blueprint)
    by_path: dict[str, list[LineSpanEdit]] = {}
    for index, edit in enumerate(edits):
        if edit.path not in originals:
            raise ValueError(f"edit {index} path is not solver-visible: {edit.path}")
        by_path.setdefault(edit.path, []).append(edit)

    changed: dict[str, str] = {}
    for path, path_edits in by_path.items():
        original = originals[path]
        original_lines = original.splitlines()
        trailing_lf = original.endswith("\n")
        normalized: list[tuple[int, int, LineSpanEdit]] = []
        for edit in path_edits:
            start = edit.start_line - 1
            end = start + edit.delete_count
            if edit.delete_count == 0:
                if start < 0 or start > len(original_lines):
                    raise ValueError(f"line-span insertion start is outside {path}: {edit.start_line}")
            elif start < 0 or start >= len(original_lines) or end > len(original_lines):
                raise ValueError(
                    f"line-span replacement is outside {path}: start={edit.start_line} delete={edit.delete_count}"
                )
            replacement = list(edit.insert_lines)
            if original_lines[start:end] == replacement:
                raise ValueError(f"line-span edit leaves selected lines unchanged in {path}")
            normalized.append((start, end, edit))

        ordered = sorted(normalized, key=lambda item: (item[0], item[1]))
        for left, right in zip(ordered, ordered[1:]):
            left_start, left_end, _ = left
            right_start, right_end, _ = right
            left_point = left_end if left_end > left_start else left_start
            if right_start < left_point or (left_start == right_start and left_end == left_start and right_end == right_start):
                raise ValueError(f"line-span edits overlap in {path}")

        result = list(original_lines)
        for start, end, edit in sorted(normalized, key=lambda item: item[0], reverse=True):
            result[start:end] = list(edit.insert_lines)
        updated = "\n".join(result) + ("\n" if trailing_lf else "")
        if updated == original:
            raise ValueError(f"line-span edits leave file unchanged: {path}")
        changed[path] = updated
    return changed


def _canonical_patch(*, blueprint: SelectionBlueprint, changed_files: dict[str, str]) -> bytes:
    originals = _visible_files(blueprint)
    pieces: list[str] = []
    for path in sorted(changed_files):
        before = originals[path]
        after = changed_files[path]
        pieces.extend(
            difflib.unified_diff(
                before.splitlines(),
                after.splitlines(),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                n=3,
                lineterm="",
            )
        )
    if not pieces:
        raise ValueError("line-span edits produced no file modifications")
    return ("\n".join(pieces) + "\n").encode("utf-8")


def extract_line_span_patch(raw: bytes, blueprint: SelectionBlueprint) -> tuple[bytes, str]:
    edits = parse_line_span_edits(raw)
    changed = _apply_line_span_edits(blueprint=blueprint, edits=edits)
    return _canonical_patch(blueprint=blueprint, changed_files=changed), "original-line-span-raw"
