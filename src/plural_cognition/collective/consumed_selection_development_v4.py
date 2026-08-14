"""Development-only V4 whole-file protocol on the consumed V1 selection split.

V1 exact-replacement JSON was semantically strong once parsed but exposed candidates
to JSON escaping and exact-anchor copying failures. V2 line spans added coordinate,
count, and indentation burdens and was rejected. V3 raw SEARCH/REPLACE improved the
same-pair solve count but did not strictly improve parse validity over V1, so it was
also rejected under its predeclared continuation rule.

V4 removes candidate-authored anchor matching entirely. A candidate emits the complete
corrected contents of each file it changes inside a small deterministic wrapper. Wrapper
control lines admit optional horizontal whitespace; payload lines are otherwise preserved
exactly. The interpreter restores only the original file's terminal-LF convention and
materializes a canonical unified diff. It does not fuzzy-match, salvage, repair candidate
source, or consult protected evaluator material.

This protocol is development-only. Any later population-selection claim requires a new
operational freeze and a fresh untouched selection pack.
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

DEVELOPMENT_PROTOCOL_SCHEMA_V4 = "plural-cognition-consumed-selection-development-protocol-v4"
OUTPUT_CONTRACT_V4 = "raw-full-file-replacement-v1"
CANDIDATE_OUTPUT_INTERPRETER_V4 = "deterministic-full-file-unified-diff-v1"
PROMPT_SOURCE_REPRESENTATION_V4 = "plain-source-v1"
CONTROL_LINE_GRAMMAR_V4 = "optional-horizontal-whitespace-control-lines-v1"
TERMINAL_LF_SEMANTICS_V4 = "preserve-original-terminal-lf-v1"
MAX_FULL_FILE_BLOCKS_V4 = 32
MAX_FULL_FILE_OUTPUT_BYTES_V4 = 262_144
V2_TARGETED_REPORT_SHA256 = "a3a9167e63f02113b356ac747a538fc1a253c25a53d6a5aae4a12e03c386757c"
V3_TARGETED_REPORT_SHA256 = "66e244d0716e08cc4543d0d68e623dd7f6c40390e5ecc6e405f97eddba4207f3"
V3_TARGETED_OUTPUT_MANIFEST_SHA256 = "128eb717d617d0a05d33609efad4a6abd992e4c338da198cb15ee755f9bb52c3"

_FILE_RE = re.compile(r"^[ \t]*FILE ([^ \t\r\n]+)[ \t]*$")
_OPEN_RE = re.compile(r"^[ \t]*<<<<<<< CONTENT[ \t]*$")
_CLOSE_RE = re.compile(r"^[ \t]*>>>>>>> CONTENT[ \t]*$")


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def development_protocol_payload_v4() -> dict[str, object]:
    p = FINAL_RAW_MIND_PROTOCOL
    return {
        "schema": DEVELOPMENT_PROTOCOL_SCHEMA_V4,
        "development_basis": "consumed-selection-v1-negative-outcome",
        "preceding_v2_targeted_report_sha256": V2_TARGETED_REPORT_SHA256,
        "preceding_v3_targeted_report_sha256": V3_TARGETED_REPORT_SHA256,
        "preceding_v3_output_manifest_sha256": V3_TARGETED_OUTPUT_MANIFEST_SHA256,
        "consumed_selection_outcome_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256,
        "selection_pack_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256,
        "operational_config_freeze_sha256": FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.sha256,
        "candidate_ids": list(FINAL_CANDIDATE_IDS),
        "prompt_source_representation": PROMPT_SOURCE_REPRESENTATION_V4,
        "output_contract": OUTPUT_CONTRACT_V4,
        "candidate_output_interpreter": CANDIDATE_OUTPUT_INTERPRETER_V4,
        "control_line_grammar": CONTROL_LINE_GRAMMAR_V4,
        "terminal_lf_semantics": TERMINAL_LF_SEMANTICS_V4,
        "max_file_blocks": MAX_FULL_FILE_BLOCKS_V4,
        "max_output_bytes": MAX_FULL_FILE_OUTPUT_BYTES_V4,
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


DEVELOPMENT_PROTOCOL_SHA256_V4 = hashlib.sha256(
    _canonical_json_bytes(development_protocol_payload_v4())
).hexdigest()


def _plain_file(path: str, raw: bytes) -> str:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"solver-visible file is not UTF-8: {path}") from exc
    if any(_OPEN_RE.fullmatch(line) or _CLOSE_RE.fullmatch(line) for line in text.splitlines()):
        raise ValueError(f"solver-visible file collides with V4 content delimiter: {path}")
    return f"===== FILE: {path} =====\n{text}===== END FILE ====="


def build_solver_prompt_v4(blueprint: SelectionBlueprint) -> bytes:
    """Build V4 solver input using plain source and whole-file replacement blocks."""

    files = [_plain_file(path, raw) for path, raw in blueprint.buggy_files]
    public = json.dumps(
        list(blueprint.public_cases),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    issue = blueprint.issue_prompt.decode("utf-8").strip()
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


@dataclass(frozen=True, slots=True)
class FullFileReplacementV4:
    path: str
    content_lines: tuple[str, ...]


def parse_full_file_replacements_v4(raw: bytes) -> tuple[FullFileReplacementV4, ...]:
    """Parse strict whole-file blocks; normalize wrapper whitespace but never payload."""

    if type(raw) is not bytes:
        raise TypeError("raw must be bytes")
    if len(raw) > MAX_FULL_FILE_OUTPUT_BYTES_V4:
        raise ValueError("model full-file output exceeds V4 size ceiling")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("model output is not UTF-8") from exc
    if "\r" in text:
        raise ValueError("V4 output must use LF newlines only")
    if text.endswith("\n"):
        text = text[:-1]
    if not text:
        raise ValueError("model output is empty")
    if "```" in text:
        raise ValueError("V4 output must not use markdown fencing")

    lines = text.split("\n")
    blocks: list[FullFileReplacementV4] = []
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
        blocks.append(FullFileReplacementV4(path=path, content_lines=content_lines))
        if len(blocks) > MAX_FULL_FILE_BLOCKS_V4:
            raise ValueError("V4 file block count exceeds development ceiling")

    paths = tuple(block.path for block in blocks)
    if len(paths) != len(set(paths)):
        raise ValueError("V4 output may contain each FILE path at most once")
    return tuple(blocks)


def _visible_files(blueprint: SelectionBlueprint) -> dict[str, str]:
    files: dict[str, str] = {}
    for path, raw in blueprint.buggy_files:
        try:
            files[path] = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"solver-visible file is not UTF-8: {path}") from exc
    return files


def _materialize_replacements_v4(
    *, blueprint: SelectionBlueprint, blocks: tuple[FullFileReplacementV4, ...]
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
            raise ValueError(f"V4 file block leaves file unchanged: {block.path}")
        changed[block.path] = replacement
    return changed


def _canonical_patch_v4(*, blueprint: SelectionBlueprint, changed_files: dict[str, str]) -> bytes:
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
        raise ValueError("V4 replacements produced no file modifications")
    return ("\n".join(pieces) + "\n").encode("utf-8")


def extract_full_file_patch_v4(raw: bytes, blueprint: SelectionBlueprint) -> tuple[bytes, str]:
    blocks = parse_full_file_replacements_v4(raw)
    changed = _materialize_replacements_v4(blueprint=blueprint, blocks=blocks)
    return _canonical_patch_v4(blueprint=blueprint, changed_files=changed), "raw-full-file-replacement"
