"""Zero-inference counterfactual parsing for consumed candidate-pool v2 selection outputs.

This module never changes the frozen v2 selection outcome. It reuses already-saved
assistant outputs and qualified Docker evaluation to measure how much semantic
performance is hidden behind narrow output-grammar incompatibilities.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .content_store import FileContentStore
from .local_candidate_pool_v2_selection import (
    _materials,
    _validate_completed_pair,
    _verify_frozen_selection_artifacts,
)
from .local_model_load_preflight import _git_revision
from .qualified_docker import probe_qualified_docker_configuration
from .repository_surgery_calibration_matrix import _evaluate_patch, _metric
from .repository_surgery_selection_outcome_freeze_v2 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_V2,
    SELECTION_OUTCOME_SOFTWARE_REVISION_V2,
    SELECTION_REPORT_SHA256_V2,
    SELECTION_SUITE_FILE_SHA256_V2,
)
from .repository_surgery_selection_pack_v1 import SelectionMaterial
from .repository_surgery_selection_pack_v2 import selection_blueprints_v2

FORENSIC_SCHEMA_V2 = "plural-cognition-candidate-pool-v2-selection-counterfactual-forensics-v1"
LEVELS = (
    "frozen-strict",
    "surface-tolerant",
    "prompt-path-tolerant",
    "bare-file-tolerant",
)
EXPECTED_INVALID_PAIR_COUNT_V2 = 27

_STRICT_FILE_RE = re.compile(r"^[ \t]*FILE ([^ \t\r\n]+)[ \t]*$")
_TOLERANT_FILE_RE = re.compile(r"^[ \t]*FILE:?[ \t]+([^ \t\r\n]+)[ \t]*$")
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class ParsedReplacement:
    path: str
    content_lines: tuple[str, ...]


def _visible_files(blueprint: Any) -> dict[str, str]:
    return {path: raw.decode("utf-8") for path, raw in blueprint.buggy_files}


def _normalize_path(path: str, visible: dict[str, str], *, level: int) -> str:
    if path in visible:
        return path
    if level >= 2 and path.startswith("relative/"):
        candidate = path[len("relative/") :]
        if candidate in visible:
            return candidate
    raise ValueError(f"path is not solver-visible: {path}")


def _next_nonblank(lines: Sequence[str], cursor: int) -> int:
    while cursor < len(lines) and lines[cursor] == "":
        cursor += 1
    return cursor


def parse_counterfactual_replacements(
    raw: bytes, blueprint: Any, *, level: int
) -> tuple[ParsedReplacement, ...]:
    """Parse one saved output under a cumulative, candidate-agnostic tolerance level.

    level 0 reproduces the frozen grammar.
    level 1 additionally accepts ``FILE: path`` and blank lines between blocks.
    level 2 additionally maps only a leading literal ``relative/`` prefix when the
    remainder exactly matches one visible file.
    level 3 additionally accepts bare ``FILE path`` blocks whose content runs to the
    next FILE header or EOF.
    """
    if level not in range(len(LEVELS)):
        raise ValueError("unsupported counterfactual level")
    text = raw.decode("utf-8")
    if "\r" in text:
        raise ValueError("counterfactual output must use LF newlines only")
    if text.endswith("\n"):
        text = text[:-1]
    if not text:
        raise ValueError("counterfactual output is empty")
    if "```" in text:
        raise ValueError("counterfactual output must not use markdown fencing")

    lines = text.split("\n")
    visible = _visible_files(blueprint)
    blocks: list[ParsedReplacement] = []
    cursor = 0
    file_re = _STRICT_FILE_RE if level == 0 else _TOLERANT_FILE_RE

    while cursor < len(lines):
        if level >= 1:
            cursor = _next_nonblank(lines, cursor)
            if cursor >= len(lines):
                break
        match = file_re.fullmatch(lines[cursor])
        if match is None:
            raise ValueError(f"expected FILE header at output line {cursor + 1}")
        path = _normalize_path(match.group(1), visible, level=level)
        cursor += 1

        if cursor < len(lines) and _OPEN_RE.fullmatch(lines[cursor]) is not None:
            cursor += 1
            start = cursor
            while cursor < len(lines) and _CLOSE_RE.fullmatch(lines[cursor]) is None:
                cursor += 1
            if cursor >= len(lines):
                raise ValueError(f"missing CONTENT closer for FILE {path}")
            content_lines = tuple(lines[start:cursor])
            cursor += 1
        elif level >= 3:
            start = cursor
            while cursor < len(lines):
                if _TOLERANT_FILE_RE.fullmatch(lines[cursor]) is not None and cursor > start:
                    break
                if lines[cursor] == "":
                    candidate = _next_nonblank(lines, cursor)
                    if candidate < len(lines) and _TOLERANT_FILE_RE.fullmatch(lines[candidate]) is not None:
                        break
                cursor += 1
            end = cursor
            while end > start and lines[end - 1] == "":
                end -= 1
            content_lines = tuple(lines[start:end])
            if not content_lines:
                raise ValueError(f"bare FILE block is empty: {path}")
            if cursor < len(lines) and lines[cursor] == "":
                cursor = _next_nonblank(lines, cursor)
        else:
            raise ValueError(f"expected CONTENT opener after FILE {path}")

        blocks.append(ParsedReplacement(path=path, content_lines=content_lines))

    paths = tuple(item.path for item in blocks)
    if not blocks:
        raise ValueError("counterfactual output contains no FILE blocks")
    if len(paths) != len(set(paths)):
        raise ValueError("counterfactual output repeats a FILE path")
    return tuple(blocks)


def counterfactual_patch(raw: bytes, blueprint: Any, *, level: int) -> bytes:
    visible = _visible_files(blueprint)
    blocks = parse_counterfactual_replacements(raw, blueprint, level=level)
    changed: dict[str, str] = {}
    for block in blocks:
        original = visible[block.path]
        replacement = "\n".join(block.content_lines)
        if original.endswith("\n"):
            replacement += "\n"
        if replacement == original:
            raise ValueError(f"counterfactual block leaves file unchanged: {block.path}")
        changed[block.path] = replacement

    pieces: list[str] = []
    for path in sorted(changed):
        pieces.extend(
            difflib.unified_diff(
                visible[path].splitlines(),
                changed[path].splitlines(),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                n=3,
                lineterm="",
            )
        )
    if not pieces:
        raise ValueError("counterfactual replacements produced no modifications")
    return ("\n".join(pieces) + "\n").encode("utf-8")


def _load_frozen_results(selection_root: Path) -> tuple[dict[str, Any], ...]:
    suite_path = selection_root / "candidate-pool-v2-selection-suite.json"
    if not suite_path.is_file():
        raise RuntimeError("frozen v2 selection suite is missing")
    if _sha256_file(suite_path) != SELECTION_SUITE_FILE_SHA256_V2:
        raise RuntimeError("frozen v2 selection suite file SHA-256 drifted")
    suite = json.loads(suite_path.read_text(encoding="ascii"))
    if suite.get("report_sha256") != SELECTION_REPORT_SHA256_V2:
        raise RuntimeError("frozen v2 selection report SHA-256 drifted")
    if suite.get("pair_count") != 60 or suite.get("selection_evidence") is not True:
        raise RuntimeError("frozen v2 selection evidence fields drifted")

    results: list[dict[str, Any]] = []
    for row in suite["results"]:
        pair_root = selection_root / "pairs" / row["candidate_id"] / row["task_id"]
        report_path = pair_root / "result.json"
        if not report_path.is_file():
            raise RuntimeError(f"frozen pair result is missing: {row['candidate_id']}/{row['task_id']}")
        report = json.loads(report_path.read_text(encoding="ascii"))
        _validate_completed_pair(
            report,
            candidate_id=row["candidate_id"],
            task_id=row["task_id"],
            software_revision=SELECTION_OUTCOME_SOFTWARE_REVISION_V2,
        )
        if report["report_sha256"] != row["report_sha256"]:
            raise RuntimeError(f"suite/pair report identity mismatch: {row['candidate_id']}/{row['task_id']}")
        results.append(report)
    return tuple(results)


def _evaluate_recovered_patch(
    *,
    material: SelectionMaterial,
    candidate_id: str,
    level_name: str,
    patch: bytes,
    store: FileContentStore,
    staging_root: Path,
    configuration: Any,
    docker_executable: str,
) -> tuple[float, float, bool, str]:
    patch_sha256 = store.put_bytes(patch)
    marker = {
        "schema": "candidate-pool-v2-counterfactual-submission-v1",
        "candidate_id": candidate_id,
        "task_id": material.visible_task.task.task_id,
        "level": level_name,
        "patch_sha256": patch_sha256,
        "candidate_model_inference_performed": False,
        "selection_outcome_mutated": False,
    }
    marker_sha256 = store.put_bytes(_canonical_json_bytes(marker))
    evaluation = _evaluate_patch(
        material=material,
        configuration=configuration,
        store=store,
        staging_root=staging_root,
        patch_sha256=patch_sha256,
        submission_sha256=marker_sha256,
        artifact_sha256=marker_sha256,
        docker_executable=docker_executable,
    )
    return (
        _metric(evaluation, "exact_accuracy"),
        _metric(evaluation, "valid_rate"),
        bool(evaluation.qualified),
        evaluation.sha256,
    )


def run_counterfactual_forensics(
    *,
    selection_root: Path,
    selection_pack_path: Path,
    qualification_path: Path,
    artifact_root: Path,
    docker_executable: str = "docker",
) -> dict[str, Any]:
    FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_V2.validate_against_repository()
    if artifact_root.exists() and any(artifact_root.iterdir()):
        raise ValueError("counterfactual artifact_root must be absent or empty")
    artifact_root.mkdir(parents=True, exist_ok=True)

    frozen_pack = _verify_frozen_selection_artifacts(selection_pack_path, qualification_path)
    reports = _load_frozen_results(selection_root)
    invalid = [item for item in reports if not bool(item["parse_valid"])]
    if len(invalid) != EXPECTED_INVALID_PAIR_COUNT_V2:
        raise RuntimeError(f"expected 27 frozen parse-invalid pairs; found {len(invalid)}")

    store = FileContentStore(artifact_root / "store")
    build_root = artifact_root / "build"
    materials = _materials(store=store, build_root=build_root, frozen_pack=frozen_pack)
    material_by_task = {item.visible_task.task.task_id: item for item in materials}
    blueprint_by_task = {item.task_id: item for item in selection_blueprints_v2()}
    configuration = probe_qualified_docker_configuration(
        software_revision=_git_revision(), docker_executable=docker_executable
    )
    staging_root = artifact_root / "staging"

    recovered: dict[tuple[str, str], dict[str, Any]] = {}
    for report in invalid:
        pair_root = selection_root / "pairs" / report["candidate_id"] / report["task_id"]
        assistant_path = pair_root / "assistant.txt"
        if not assistant_path.is_file():
            raise RuntimeError(f"parse-invalid pair lacks saved assistant output: {report['candidate_id']}/{report['task_id']}")
        assistant = assistant_path.read_bytes()
        if hashlib.sha256(assistant).hexdigest() != report["assistant_sha256"]:
            raise RuntimeError(f"assistant output identity drifted: {report['candidate_id']}/{report['task_id']}")

        errors: list[str] = []
        outcome: dict[str, Any] | None = None
        for level in range(1, len(LEVELS)):
            try:
                patch = counterfactual_patch(
                    assistant,
                    blueprint_by_task[report["task_id"]],
                    level=level,
                )
            except ValueError as exc:
                errors.append(f"{LEVELS[level]}: {exc}")
                continue
            exact, valid, solved, evaluation_sha256 = _evaluate_recovered_patch(
                material=material_by_task[report["task_id"]],
                candidate_id=report["candidate_id"],
                level_name=LEVELS[level],
                patch=patch,
                store=store,
                staging_root=staging_root,
                configuration=configuration,
                docker_executable=docker_executable,
            )
            outcome = {
                "candidate_id": report["candidate_id"],
                "task_id": report["task_id"],
                "frozen_parse_error": report["parse_error"],
                "minimal_recovery_level": LEVELS[level],
                "counterfactual_parse_valid": True,
                "counterfactual_exact_accuracy": exact,
                "counterfactual_evaluator_valid_rate": valid,
                "counterfactual_solved": solved,
                "counterfactual_evaluation_sha256": evaluation_sha256,
                "preceding_parse_errors": errors,
            }
            break
        if outcome is None:
            outcome = {
                "candidate_id": report["candidate_id"],
                "task_id": report["task_id"],
                "frozen_parse_error": report["parse_error"],
                "minimal_recovery_level": None,
                "counterfactual_parse_valid": False,
                "counterfactual_exact_accuracy": 0.0,
                "counterfactual_evaluator_valid_rate": 0.0,
                "counterfactual_solved": False,
                "counterfactual_evaluation_sha256": None,
                "preceding_parse_errors": errors,
            }
        recovered[(report["candidate_id"], report["task_id"])] = outcome

    by_level: list[dict[str, Any]] = []
    candidate_ids = tuple(dict.fromkeys(item["candidate_id"] for item in reports))
    for level, level_name in enumerate(LEVELS):
        diagnostics: list[dict[str, Any]] = []
        for candidate_id in candidate_ids:
            candidate_reports = [item for item in reports if item["candidate_id"] == candidate_id]
            valid_count = 0
            solved_count = 0
            for report in candidate_reports:
                if bool(report["parse_valid"]):
                    valid_count += 1
                    solved_count += int(bool(report["solved"]))
                    continue
                outcome = recovered[(candidate_id, report["task_id"])]
                minimal = outcome["minimal_recovery_level"]
                if minimal is not None and LEVELS.index(minimal) <= level:
                    valid_count += 1
                    solved_count += int(bool(outcome["counterfactual_solved"]))
            diagnostics.append(
                {
                    "candidate_id": candidate_id,
                    "valid_count": valid_count,
                    "solved_count": solved_count,
                    "valid_rate": valid_count / 12,
                    "score": solved_count / 12,
                    "counterfactual_eligible_at_frozen_threshold": valid_count / 12 >= 0.95,
                }
            )
        by_level.append({"level": level_name, "diagnostics": diagnostics})

    strict = by_level[0]["diagnostics"]
    if sum(item["valid_count"] for item in strict) != 33:
        raise AssertionError("strict counterfactual baseline no longer reproduces 33 parse-valid pairs")
    if sum(item["solved_count"] for item in strict) != 30:
        raise AssertionError("strict counterfactual baseline no longer reproduces 30 solved pairs")

    payload = {
        "schema": FORENSIC_SCHEMA_V2,
        "scientific_status": "post-selection-development-forensics-only",
        "frozen_selection_outcome_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_V2.sha256,
        "selection_suite_file_sha256": SELECTION_SUITE_FILE_SHA256_V2,
        "selection_report_sha256": SELECTION_REPORT_SHA256_V2,
        "invalid_pair_count": len(invalid),
        "levels": list(LEVELS),
        "recovered_pairs": [recovered[key] for key in sorted(recovered)],
        "counterfactual_diagnostics": by_level,
        "candidate_model_inference_performed": False,
        "selection_outcome_mutated": False,
        "selection_rerun": False,
        "threshold_lowered": False,
    }
    report_sha256 = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    final = dict(payload)
    final["report_sha256"] = report_sha256
    (artifact_root / "candidate-pool-v2-selection-counterfactual-forensics.json").write_bytes(
        _canonical_json_bytes(final) + b"\n"
    )
    return final


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate saved v2 selection outputs under narrow counterfactual parsers without model inference.")
    parser.add_argument("--selection-root", required=True, type=Path)
    parser.add_argument("--selection-pack", required=True, type=Path)
    parser.add_argument("--qualification-report", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--docker-executable", default="docker")
    return parser


def _print_report(report: dict[str, Any]) -> None:
    print("status=CANDIDATE_POOL_V2_SELECTION_COUNTERFACTUAL_FORENSICS_COMPLETE")
    print(f"report_sha256={report['report_sha256']}")
    print(f"invalid_pair_count={report['invalid_pair_count']}")
    for row in report["recovered_pairs"]:
        print(
            "pair=" + row["candidate_id"] + "/" + row["task_id"]
            + " recovery=" + str(row["minimal_recovery_level"])
            + " solved=" + str(row["counterfactual_solved"])
        )
    for level in report["counterfactual_diagnostics"]:
        print(f"level={level['level']}")
        for item in level["diagnostics"]:
            print(
                f"candidate={item['candidate_id']} valid={item['valid_count']}/12 "
                f"solved={item['solved_count']}/12 valid_rate={item['valid_rate']:.6f} "
                f"counterfactual_eligible={item['counterfactual_eligible_at_frozen_threshold']}"
            )
    print("candidate_model_inference_performed=False")
    print("selection_outcome_mutated=False")
    print("selection_rerun=False")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = run_counterfactual_forensics(
        selection_root=args.selection_root,
        selection_pack_path=args.selection_pack,
        qualification_path=args.qualification_report,
        artifact_root=args.artifact_root,
        docker_executable=args.docker_executable,
    )
    _print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
