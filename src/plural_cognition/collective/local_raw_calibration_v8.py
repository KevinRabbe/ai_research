"""V8 raw calibration: replace handwritten unified diffs with exact structured edits.

V6 established stable answer transport across all five frozen candidates. V7 then
changed only unified-diff instructions and still produced zero parse-valid patches,
even when several candidates expressed the correct semantic replacement. V8 keeps
V6 transport, generation, resources, strict repository validation, qualified Docker
execution, and protected evaluator semantics unchanged while replacing the
candidate serialization contract.

A candidate returns one exact JSON object containing repository-relative path plus
old/new text replacements. The harness accepts only a strict schema, requires each
old text to occur exactly once in the solver-visible file state, applies edits in
listed order in memory, and deterministically materializes a canonical unified diff.
The raw JSON remains the immutable model output. No malformed diff is repaired and
no protected information is consulted while interpreting the candidate answer.
"""
from __future__ import annotations

import difflib
import json
import sys
from typing import Any, Sequence

from . import local_raw_calibration as v1
from . import local_raw_calibration_v3 as v3
from . import local_raw_calibration_v4 as v4
from . import local_raw_calibration_v6 as v6
from .repository_surgery_calibration_matrix import CalibrationBlueprint

REPORT_SCHEMA_V7 = "plural-cognition-local-raw-capability-calibration-v7"
PROTOCOL_SCHEMA_V7 = "plural-cognition-local-raw-calibration-protocol-v7"
STRUCTURED_EDIT_CONTRACT = "exact-replace-json-v1"
STRUCTURED_EDIT_INTERPRETER = "deterministic-canonical-unified-diff-v1"
MAX_STRUCTURED_EDITS = 32
_BASE_V6_PROTOCOL_PAYLOAD = v6.calibration_protocol_payload_v5
_ACTIVE_BLUEPRINT: CalibrationBlueprint | None = None


def calibration_protocol_payload_v7() -> dict[str, object]:
    payload = dict(_BASE_V6_PROTOCOL_PAYLOAD())
    payload.update(
        {
            "schema": PROTOCOL_SCHEMA_V7,
            "output_contract": STRUCTURED_EDIT_CONTRACT,
            "candidate_output_interpreter": STRUCTURED_EDIT_INTERPRETER,
            "structured_edit_max_count": MAX_STRUCTURED_EDITS,
            "patch_validation": "qualified-docker-unified-diff-grammar-v1",
        }
    )
    return payload


CALIBRATION_PROTOCOL_SHA256_V7 = v1._sha256_json(calibration_protocol_payload_v7())


def build_solver_prompt_v8(blueprint: CalibrationBlueprint) -> bytes:
    """Build solver-visible V8 input and bind the current public blueprint."""

    global _ACTIVE_BLUEPRINT
    _ACTIVE_BLUEPRINT = blueprint

    files: list[str] = []
    for path, data in blueprint.buggy_files:
        text = data.decode("utf-8")
        files.append(f"===== FILE: {path} =====\n{text}===== END FILE =====")
    public = json.dumps(
        list(blueprint.public_cases),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    issue = blueprint.issue_prompt.decode("utf-8").strip()
    prompt = (
        "You are repairing a small repository. Work only from the issue, repository "
        "files, and public examples below. Return exactly one JSON object and nothing "
        "else. Do not use markdown fences.\n\n"
        "OUTPUT SCHEMA:\n"
        '{"edits":[{"path":"relative/file.py","old":"exact old text","new":"exact replacement text"}]}\n\n'
        "RULES:\n"
        "- edits must be a non-empty JSON array in the order the replacements should be applied.\n"
        "- path must exactly name one solver-visible repository file.\n"
        "- old and new must be JSON strings copied/written exactly, including indentation and newlines.\n"
        "- old must identify exactly one occurrence in the current file state when that edit is applied.\n"
        "- new must differ from old.\n"
        "- Make the smallest repair needed. Do not include explanations, line numbers, diff headers, or unchanged context.\n"
        "- For a one-line change, old and new should normally contain only that one complete source line.\n\n"
        "FORMAT EXAMPLE ONLY (unrelated to the task):\n"
        '{"edits":[{"path":"demo.txt","old":"blue","new":"green"}]}\n'
        "Do not copy the example content. Solve the actual issue below.\n\n"
        f"ISSUE:\n{issue}\n\n"
        + "\n\n".join(files)
        + f"\n\nPUBLIC_EXAMPLES_JSON:\n{public}\n"
    )
    return prompt.encode("utf-8")


def _strict_json_object(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes:
        raise TypeError("raw must be bytes")
    if len(raw) > v1.MAX_PATCH_BYTES:
        raise ValueError("model structured output exceeds calibration size ceiling")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("model output is not UTF-8") from exc
    text = text.strip()
    if not text:
        raise ValueError("model output is empty")
    if text.startswith("```") or "```" in text:
        raise ValueError("structured edit output must not use markdown fencing")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("model output is not one valid JSON object") from exc
    if type(payload) is not dict:
        raise ValueError("structured edit output must be a JSON object")
    if set(payload) != {"edits"}:
        raise ValueError("structured edit object must contain only the edits field")
    return payload


def _solver_visible_files(blueprint: CalibrationBlueprint) -> dict[str, str]:
    files: dict[str, str] = {}
    for path, raw in blueprint.buggy_files:
        try:
            files[path] = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"solver-visible file is not UTF-8: {path}") from exc
    return files


def _parse_edits(raw: bytes, blueprint: CalibrationBlueprint) -> dict[str, str]:
    payload = _strict_json_object(raw)
    edits = payload["edits"]
    if type(edits) is not list or not edits:
        raise ValueError("edits must be a non-empty JSON array")
    if len(edits) > MAX_STRUCTURED_EDITS:
        raise ValueError("structured edit count exceeds calibration ceiling")

    files = _solver_visible_files(blueprint)
    changed_paths: set[str] = set()
    for index, edit in enumerate(edits):
        if type(edit) is not dict or set(edit) != {"path", "old", "new"}:
            raise ValueError(f"edit {index} must contain exactly path, old, and new")
        path = edit["path"]
        old = edit["old"]
        new = edit["new"]
        if type(path) is not str or not path:
            raise ValueError(f"edit {index} path must be a non-empty string")
        if path not in files:
            raise ValueError(f"edit {index} path is not solver-visible: {path}")
        if type(old) is not str or type(new) is not str:
            raise ValueError(f"edit {index} old/new must be strings")
        if not old:
            raise ValueError(f"edit {index} old text must be non-empty")
        if old == new:
            raise ValueError(f"edit {index} replacement does not change the file")
        occurrence_count = files[path].count(old)
        if occurrence_count != 1:
            raise ValueError(
                f"edit {index} old text must occur exactly once in {path}; found {occurrence_count}"
            )
        files[path] = files[path].replace(old, new, 1)
        changed_paths.add(path)

    return {path: files[path] for path in sorted(changed_paths)}


def _canonical_patch(
    *, blueprint: CalibrationBlueprint, changed_files: dict[str, str]
) -> bytes:
    originals = _solver_visible_files(blueprint)
    pieces: list[str] = []
    for path in sorted(changed_files):
        before = originals[path]
        after = changed_files[path]
        if before == after:
            raise ValueError(f"structured edits leave file unchanged: {path}")
        diff_lines = list(
            difflib.unified_diff(
                before.splitlines(),
                after.splitlines(),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                n=3,
                lineterm="",
            )
        )
        if not diff_lines:
            raise ValueError(f"structured edits produced no diff for {path}")
        pieces.extend(diff_lines)
    patch = ("\n".join(pieces) + "\n").encode("utf-8")
    if len(patch) > v1.MAX_PATCH_BYTES:
        raise ValueError("materialized model patch exceeds calibration patch-size ceiling")
    return patch


def extract_structured_edit_patch(raw: bytes) -> tuple[bytes, str]:
    """Interpret strict candidate JSON into one deterministic unified diff."""

    if _ACTIVE_BLUEPRINT is None:
        raise RuntimeError("structured edit parser has no active calibration blueprint")
    changed_files = _parse_edits(raw, _ACTIVE_BLUEPRINT)
    patch = _canonical_patch(blueprint=_ACTIVE_BLUEPRINT, changed_files=changed_files)

    # The generated patch must itself satisfy the exact historical parser before
    # V1's unchanged blueprint application check and qualified Docker execution.
    if not v1._parse_unified_diff(patch):
        raise ValueError("materialized structured edit contains no file modifications")
    return patch, "structured-edit-json"


def main(argv: Sequence[str] | None = None) -> int:
    actual_argv = tuple(sys.argv[1:] if argv is None else argv)

    # V4 remains responsible for literal prompt transport and one-terminal-LF
    # normalization; V6 remains responsible for closed-at-EOF answer transport.
    v4._BASE_BUILD_SOLVER_PROMPT = build_solver_prompt_v8
    v3.extract_assistant_content = v6.extract_assistant_content_v6
    v1.extract_unified_diff = extract_structured_edit_patch
    v4.REPORT_SCHEMA_V3 = REPORT_SCHEMA_V7
    v4.PROTOCOL_SCHEMA_V3 = PROTOCOL_SCHEMA_V7
    v4.calibration_protocol_payload_v3 = calibration_protocol_payload_v7
    v4.CALIBRATION_PROTOCOL_SHA256_V3 = CALIBRATION_PROTOCOL_SHA256_V7
    return v4.main(actual_argv)


if __name__ == "__main__":
    raise SystemExit(main())
