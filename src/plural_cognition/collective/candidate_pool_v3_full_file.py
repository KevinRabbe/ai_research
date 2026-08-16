"""Candidate-pool v3 structured whole-file representation.

V3 is the minimal representation change supported by the frozen v2 post-selection
forensics. It keeps explicit CONTENT delimiters and exact solver-visible paths,
while accepting two harmless wrapper variations that hid semantic performance in
v2: an optional colon after FILE and blank lines between complete FILE blocks.

There is deliberately no fuzzy path repair, no ``relative/`` prefix rewrite, no
bare-file mode, no output repair, and no candidate-specific behavior.
"""
from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from typing import Any

OUTPUT_CONTRACT_V3 = "structured-full-file-replacement-v3"
CANDIDATE_OUTPUT_INTERPRETER_V3 = "deterministic-structured-full-file-unified-diff-v3"
PROMPT_SOURCE_REPRESENTATION_V3 = "plain-source-v1"
CONTROL_LINE_GRAMMAR_V3 = "optional-file-colon-and-blank-interblock-lines-v1"
TERMINAL_LF_SEMANTICS_V3 = "preserve-original-terminal-lf-v1"
MAX_FULL_FILE_BLOCKS_V3 = 32
MAX_FULL_FILE_OUTPUT_BYTES_V3 = 262_144

_FILE_RE = re.compile(r"^[ \t]*FILE:?[ \t]+([^ \t\r\n]+)[ \t]*$")
_OPEN_RE = re.compile(r"^[ \t]*<<<<<<< CONTENT[ \t]*$")
_CLOSE_RE = re.compile(r"^[ \t]*>>>>>>> CONTENT[ \t]*$")


def _plain_file(path: str, raw: bytes) -> str:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"solver-visible file is not UTF-8: {path}") from exc
    if any(_OPEN_RE.fullmatch(line) or _CLOSE_RE.fullmatch(line) for line in text.splitlines()):
        raise ValueError(f"solver-visible file collides with v3 content delimiter: {path}")
    return f"===== FILE: {path} =====\n{text}===== END FILE ====="


def _issue_text(blueprint: Any) -> str:
    try:
        return blueprint.issue_prompt.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("issue prompt is not UTF-8") from exc


def _visible_path_order(blueprint: Any) -> tuple[str, ...]:
    paths = tuple(path for path, _raw in blueprint.buggy_files)
    if not paths:
        raise ValueError("v3 solver prompt requires at least one visible file")
    if len(paths) != len(set(paths)):
        raise ValueError("v3 solver-visible file paths must be unique")
    return paths


def build_solver_prompt_v3(blueprint: Any) -> bytes:
    """Build the candidate-agnostic v3 prompt using exact task-local paths."""
    paths = _visible_path_order(blueprint)
    files = [_plain_file(path, raw) for path, raw in blueprint.buggy_files]
    public = json.dumps(
        list(blueprint.public_cases),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    issue = _issue_text(blueprint)
    allowed = "\n".join(f"- {path}" for path in paths)
    example_path = paths[0]
    prompt = (
        "You are repairing a small repository. Work only from the issue, repository "
        "files, and public examples below. Return only one or more structured FILE "
        "blocks and nothing else. Do not use markdown fences or JSON.\n\n"
        "ALLOWED_FILE_PATHS (copy paths exactly from this list):\n"
        f"{allowed}\n\n"
        "OUTPUT FORMAT:\n"
        f"FILE {example_path}\n"
        "<<<<<<< CONTENT\n"
        f"<complete corrected contents of {example_path}>\n"
        ">>>>>>> CONTENT\n\n"
        "RULES:\n"
        "- Emit exactly one FILE block for each file you change; omit unchanged files.\n"
        "- Each FILE path must exactly equal one entry in ALLOWED_FILE_PATHS.\n"
        "- `FILE path` and `FILE: path` are equivalent wrapper syntax; prefer `FILE path`.\n"
        "- Blank lines between complete FILE blocks are allowed.\n"
        "- CONTENT opener and closer lines are mandatory for every FILE block.\n"
        "- Between CONTENT markers, emit the complete corrected file, not a diff or fragment.\n"
        "- Preserve indentation and unchanged source; make only the smallest repair needed.\n"
        "- Do not include FILE/CONTENT wrapper lines inside the file body.\n"
        "- Do not include explanations, line numbers, JSON quoting, or markdown fences.\n"
        "- Do not invent path prefixes or rewrite an allowed path.\n"
        "- The harness preserves the original file's terminal-newline convention deterministically.\n"
        "- Horizontal spaces around FILE/CONTENT control lines are wrapper syntax only and are ignored.\n"
        "- The angle-bracket line in OUTPUT FORMAT is schematic; replace it with actual source.\n\n"
        f"ISSUE:\n{issue}\n\n"
        + "\n\n".join(files)
        + f"\n\nPUBLIC_EXAMPLES_JSON:\n{public}\n"
    )
    if "relative/file.py" in prompt or "FILE relative/" in prompt:
        raise RuntimeError("misleading v2 relative-path placeholder survived in v3 prompt")
    return prompt.encode("utf-8")


def solver_prompt_transport_v3(blueprint: Any) -> bytes:
    raw = build_solver_prompt_v3(blueprint)
    if not raw.endswith(b"\n"):
        raise RuntimeError("v3 whole-file prompt builder no longer ends in one LF")
    prompt = raw[:-1]
    if prompt.endswith(b"\n"):
        raise RuntimeError("v3 prompt transport did not remove exactly one terminal LF")
    return prompt


@dataclass(frozen=True, slots=True)
class FullFileReplacementV3:
    path: str
    content_lines: tuple[str, ...]


def _skip_blank_lines(lines: list[str], cursor: int) -> int:
    while cursor < len(lines) and lines[cursor] == "":
        cursor += 1
    return cursor


def parse_full_file_replacements_v3(raw: bytes) -> tuple[FullFileReplacementV3, ...]:
    if type(raw) is not bytes:
        raise TypeError("raw must be bytes")
    if len(raw) > MAX_FULL_FILE_OUTPUT_BYTES_V3:
        raise ValueError("model full-file output exceeds v3 size ceiling")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("model output is not UTF-8") from exc
    if "\r" in text:
        raise ValueError("v3 whole-file output must use LF newlines only")
    if text.endswith("\n"):
        text = text[:-1]
    if not text:
        raise ValueError("model output is empty")
    if "```" in text:
        raise ValueError("v3 whole-file output must not use markdown fencing")

    lines = text.split("\n")
    blocks: list[FullFileReplacementV3] = []
    cursor = 0
    while cursor < len(lines):
        cursor = _skip_blank_lines(lines, cursor)
        if cursor >= len(lines):
            break
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
        blocks.append(FullFileReplacementV3(path=path, content_lines=content_lines))
        if len(blocks) > MAX_FULL_FILE_BLOCKS_V3:
            raise ValueError("v3 whole-file block count exceeds ceiling")

    paths = tuple(block.path for block in blocks)
    if not blocks:
        raise ValueError("v3 output contains no FILE blocks")
    if len(paths) != len(set(paths)):
        raise ValueError("v3 output may contain each FILE path at most once")
    return tuple(blocks)


def _visible_files(blueprint: Any) -> dict[str, str]:
    files: dict[str, str] = {}
    for path, raw in blueprint.buggy_files:
        try:
            files[path] = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"solver-visible file is not UTF-8: {path}") from exc
    return files


def _materialize_replacements_v3(
    *, blueprint: Any, blocks: tuple[FullFileReplacementV3, ...]
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
            raise ValueError(f"v3 file block leaves file unchanged: {block.path}")
        changed[block.path] = replacement
    return changed


def _canonical_patch_v3(*, blueprint: Any, changed_files: dict[str, str]) -> bytes:
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
        raise ValueError("v3 replacements produced no file modifications")
    return ("\n".join(pieces) + "\n").encode("utf-8")


def extract_full_file_patch_v3(raw: bytes, blueprint: Any) -> tuple[bytes, str]:
    blocks = parse_full_file_replacements_v3(raw)
    changed = _materialize_replacements_v3(blueprint=blueprint, blocks=blocks)
    return _canonical_patch_v3(blueprint=blueprint, changed_files=changed), OUTPUT_CONTRACT_V3


def gold_full_file_output_v3(blueprint: Any) -> bytes:
    """Deterministic test oracle; never solver-visible."""
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
        raise AssertionError("blueprint has no changed files")
    return "\n\n".join(blocks).encode("utf-8")
