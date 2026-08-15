"""V4 whole-file candidate representation for candidate-pool v2 calibration.

The representation is ported from the consumed-split V4 development protocol but
is applied here only to the six pre-existing calibration blueprints.  The old
calibration issue prompts contain one obsolete serialization clause requesting a
unified diff.  That clause is removed exactly once, globally and deterministically,
so the solver sees one unambiguous whole-file output contract.
"""
from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from typing import Any

from .candidate_pool_v2_calibration_protocol import CALIBRATION_TASK_IDS_V2
from .repository_surgery_calibration_matrix import CalibrationBlueprint

OUTPUT_CONTRACT_V2 = "raw-full-file-replacement-v1"
CANDIDATE_OUTPUT_INTERPRETER_V2 = "deterministic-full-file-unified-diff-v1"
PROMPT_SOURCE_REPRESENTATION_V2 = "plain-source-v1"
CONTROL_LINE_GRAMMAR_V2 = "optional-horizontal-whitespace-control-lines-v1"
TERMINAL_LF_SEMANTICS_V2 = "preserve-original-terminal-lf-v1"
MAX_FULL_FILE_BLOCKS_V2 = 32
MAX_FULL_FILE_OUTPUT_BYTES_V2 = 262_144
OBSOLETE_SERIALIZATION_CLAUSE = " and return a unified diff only."

_FILE_RE = re.compile(r"^[ \t]*FILE ([^ \t\r\n]+)[ \t]*$")
_OPEN_RE = re.compile(r"^[ \t]*<<<<<<< CONTENT[ \t]*$")
_CLOSE_RE = re.compile(r"^[ \t]*>>>>>>> CONTENT[ \t]*$")


def _plain_file(path: str, raw: bytes) -> str:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"solver-visible file is not UTF-8: {path}") from exc
    if any(_OPEN_RE.fullmatch(line) or _CLOSE_RE.fullmatch(line) for line in text.splitlines()):
        raise ValueError(f"solver-visible file collides with V4 content delimiter: {path}")
    return f"===== FILE: {path} =====\n{text}===== END FILE ====="


def normalized_issue_text_v2(blueprint: CalibrationBlueprint) -> str:
    if blueprint.task_id not in CALIBRATION_TASK_IDS_V2:
        raise ValueError(f"not a frozen v2 calibration task: {blueprint.task_id}")
    try:
        issue = blueprint.issue_prompt.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("calibration issue prompt is not UTF-8") from exc
    count = issue.count(OBSOLETE_SERIALIZATION_CLAUSE)
    if count != 1:
        raise RuntimeError(
            f"expected exactly one obsolete serialization clause in {blueprint.task_id}; found {count}"
        )
    normalized = issue.replace(OBSOLETE_SERIALIZATION_CLAUSE, ".", 1)
    if "unified diff only" in normalized.lower():
        raise RuntimeError(f"obsolete diff-only instruction survived normalization: {blueprint.task_id}")
    return normalized


def build_solver_prompt_v2(blueprint: CalibrationBlueprint) -> bytes:
    files = [_plain_file(path, raw) for path, raw in blueprint.buggy_files]
    public = json.dumps(
        list(blueprint.public_cases),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    issue = normalized_issue_text_v2(blueprint)
    prompt = (
        "You are repairing a small repository. Work only from the issue, repository "
        "files, and public examples below. Return only one or more FILE blocks and "
        "nothing else. Do not use markdown fences or JSON.\n\n"
        "OUTPUT FORMAT:\n"
        "FILE relative/file.py\n"
        "<<<<<<< CONTENT\n"
        "<complete corrected contents of that file>\n"
        ">>>>>>> CONTENT\n\n"
        "RULES:\n"
        "- Emit exactly one FILE block for each file you change; omit unchanged files.\n"
        "- path must exactly name one solver-visible repository file.\n"
        "- Between CONTENT markers, emit the complete corrected file, not a diff or fragment.\n"
        "- Preserve indentation and all unchanged source exactly; make only the smallest repair needed.\n"
        "- Do not include FILE/CONTENT wrapper lines inside the file body.\n"
        "- Do not include explanations, line numbers, JSON quoting, or markdown fences.\n"
        "- The harness preserves the original file's terminal-newline convention deterministically.\n"
        "- Horizontal spaces around FILE/CONTENT control lines are wrapper syntax only and are ignored.\n\n"
        "FORMAT EXAMPLE ONLY (unrelated to the task):\n"
        "FILE demo.txt\n"
        "<<<<<<< CONTENT\n"
        "red\n"
        "green\n"
        ">>>>>>> CONTENT\n"
        "Do not copy the example content. Solve the actual issue below.\n\n"
        f"ISSUE:\n{issue}\n\n"
        + "\n\n".join(files)
        + f"\n\nPUBLIC_EXAMPLES_JSON:\n{public}\n"
    )
    return prompt.encode("utf-8")


def solver_prompt_transport_v2(blueprint: CalibrationBlueprint) -> bytes:
    raw = build_solver_prompt_v2(blueprint)
    if not raw.endswith(b"\n"):
        raise RuntimeError("v2 whole-file prompt builder no longer ends in one LF")
    prompt = raw[:-1]
    if prompt.endswith(b"\n"):
        raise RuntimeError("v2 prompt transport did not remove exactly one terminal LF")
    return prompt


@dataclass(frozen=True, slots=True)
class FullFileReplacementV2:
    path: str
    content_lines: tuple[str, ...]


def parse_full_file_replacements_v2(raw: bytes) -> tuple[FullFileReplacementV2, ...]:
    if type(raw) is not bytes:
        raise TypeError("raw must be bytes")
    if len(raw) > MAX_FULL_FILE_OUTPUT_BYTES_V2:
        raise ValueError("model full-file output exceeds v2 size ceiling")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("model output is not UTF-8") from exc
    if "\r" in text:
        raise ValueError("v2 whole-file output must use LF newlines only")
    if text.endswith("\n"):
        text = text[:-1]
    if not text:
        raise ValueError("model output is empty")
    if "```" in text:
        raise ValueError("v2 whole-file output must not use markdown fencing")

    lines = text.split("\n")
    blocks: list[FullFileReplacementV2] = []
    cursor = 0
    while cursor < len(lines):
        match = _FILE_RE.fullmatch(lines[cursor])
        if match is None:
            raise ValueError(f"expected FILE header at output line {cursor + 1}")
        path = match.group(1)
        cursor += 1
        if cursor >= len(lines) or _OPEN_RE.fullmatch(lines[cursor]) is None:
            raise ValueError(f"expected CONTENT opener after FILE {path}")
        cursor += 1
        start = cursor
        while cursor < len(lines) and _CLOSE_RE.fullmatch(lines[cursor]) is None:
            cursor += 1
        if cursor >= len(lines):
            raise ValueError(f"missing CONTENT closer for FILE {path}")
        content_lines = tuple(lines[start:cursor])
        cursor += 1
        blocks.append(FullFileReplacementV2(path=path, content_lines=content_lines))
        if len(blocks) > MAX_FULL_FILE_BLOCKS_V2:
            raise ValueError("v2 whole-file block count exceeds calibration ceiling")

    paths = tuple(block.path for block in blocks)
    if len(paths) != len(set(paths)):
        raise ValueError("v2 output may contain each FILE path at most once")
    return tuple(blocks)


def _visible_files(blueprint: CalibrationBlueprint) -> dict[str, str]:
    files: dict[str, str] = {}
    for path, raw in blueprint.buggy_files:
        try:
            files[path] = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"solver-visible file is not UTF-8: {path}") from exc
    return files


def _materialize_replacements_v2(
    *, blueprint: CalibrationBlueprint, blocks: tuple[FullFileReplacementV2, ...]
) -> dict[str, str]:
    originals = _visible_files(blueprint)
    changed: dict[str, str] = {}
    for index, block in enumerate(blocks):
        if block.path not in originals:
            raise ValueError(f"file block {index} path is not solver-visible: {block.path}")
        original = originals[block.path]
        replacement = "\n".join(block.content_lines)
        if original.endswith("\n"):
            replacement += "\n"
        if replacement == original:
            raise ValueError(f"v2 file block leaves file unchanged: {block.path}")
        changed[block.path] = replacement
    return changed


def _canonical_patch_v2(
    *, blueprint: CalibrationBlueprint, changed_files: dict[str, str]
) -> bytes:
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
        raise ValueError("v2 replacements produced no file modifications")
    return ("\n".join(pieces) + "\n").encode("utf-8")


def extract_full_file_patch_v2(
    raw: bytes, blueprint: CalibrationBlueprint
) -> tuple[bytes, str]:
    blocks = parse_full_file_replacements_v2(raw)
    changed = _materialize_replacements_v2(blueprint=blueprint, blocks=blocks)
    return _canonical_patch_v2(blueprint=blueprint, changed_files=changed), "raw-full-file-replacement"


def gold_full_file_output_v2(blueprint: CalibrationBlueprint) -> bytes:
    """Deterministic test oracle for representation tests; never solver-visible."""
    buggy = dict(blueprint.buggy_files)
    blocks: list[str] = []
    for path, clean_raw in blueprint.clean_files:
        if clean_raw == buggy[path]:
            continue
        clean = clean_raw.decode("utf-8")
        if clean.endswith("\n"):
            clean = clean[:-1]
        blocks.append(f"FILE {path}\n<<<<<<< CONTENT\n{clean}\n>>>>>>> CONTENT")
    if not blocks:
        raise AssertionError("calibration blueprint has no changed files")
    return "\n".join(blocks).encode("utf-8")
