"""Fail-closed targeted entry point for the predeclared V5 self-review probe."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Sequence

from .consumed_selection_development_v5_self_review import (
    TARGET_CANDIDATE_IDS_V5,
    TARGET_RESULT_COUNT_V5,
    TARGET_TASK_IDS_V5,
    TARGET_V4_PARSED_COUNT_V5,
    TARGET_V4_SOLVED_COUNT_V5,
)
from .local_consumed_selection_development_v5_self_review import (
    DEFAULT_TIMEOUT_SECONDS,
    _load_frozen_v4_drafts,
    run_consumed_selection_development_v5_self_review,
)


def _targeted_v4_baseline(records: dict[tuple[str, str], dict[str, Any]]) -> tuple[int, int, int]:
    selected = [
        records[(candidate_id, task_id)]["result"]
        for candidate_id in TARGET_CANDIDATE_IDS_V5
        for task_id in TARGET_TASK_IDS_V5
    ]
    return (
        len(selected),
        sum(1 for item in selected if item["parse_valid"]),
        sum(1 for item in selected if item["solved"]),
    )


def _validate_targeted_v4_baseline(v4_targeted_root: Path, v4_remainder_root: Path) -> None:
    records = _load_frozen_v4_drafts(v4_targeted_root, v4_remainder_root)
    count, parsed, solved = _targeted_v4_baseline(records)
    expected = (TARGET_RESULT_COUNT_V5, TARGET_V4_PARSED_COUNT_V5, TARGET_V4_SOLVED_COUNT_V5)
    if (count, parsed, solved) != expected:
        raise ValueError(
            "predeclared V5 targeted V4 baseline drifted: "
            f"observed={(count, parsed, solved)} expected={expected}"
        )


def run_targeted_consumed_selection_development_v5_self_review(
    *,
    runtime_root: Path,
    model_root: Path,
    artifact_root: Path,
    selection_pack_path: Path,
    qualification_path: Path,
    v4_targeted_root: Path,
    v4_remainder_root: Path,
    software_revision: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    docker_executable: str = "docker",
) -> dict[str, Any]:
    _validate_targeted_v4_baseline(v4_targeted_root, v4_remainder_root)
    return run_consumed_selection_development_v5_self_review(
        runtime_root=runtime_root,
        model_root=model_root,
        artifact_root=artifact_root,
        selection_pack_path=selection_pack_path,
        qualification_path=qualification_path,
        v4_targeted_root=v4_targeted_root,
        v4_remainder_root=v4_remainder_root,
        software_revision=software_revision,
        candidate_ids=TARGET_CANDIDATE_IDS_V5,
        task_ids=TARGET_TASK_IDS_V5,
        timeout_seconds=timeout_seconds,
        docker_executable=docker_executable,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the exact predeclared 4x3 V5 same-mind self-review probe.")
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--selection-pack", required=True, type=Path)
    parser.add_argument("--qualification-report", required=True, type=Path)
    parser.add_argument("--v4-targeted-root", required=True, type=Path)
    parser.add_argument("--v4-remainder-root", required=True, type=Path)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--docker-executable", default="docker")
    args = parser.parse_args(argv)
    try:
        report = run_targeted_consumed_selection_development_v5_self_review(
            runtime_root=args.runtime_root,
            model_root=args.model_root,
            artifact_root=args.artifact_root,
            selection_pack_path=args.selection_pack,
            qualification_path=args.qualification_report,
            v4_targeted_root=args.v4_targeted_root,
            v4_remainder_root=args.v4_remainder_root,
            software_revision=args.software_revision,
            timeout_seconds=args.timeout_seconds,
            docker_executable=args.docker_executable,
        )
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"status=CONSUMED_SELECTION_DEVELOPMENT_V5_TARGETED_FAIL\nerror={exc}")
        return 2
    parsed = sum(1 for item in report["results"] if item["parse_valid"])
    solved = sum(1 for item in report["results"] if item["solved"])
    recovered = sum(1 for item in report["results"] if not item["draft_solved"] and item["solved"])
    regressions = sum(1 for item in report["results"] if item["draft_solved"] and not item["solved"])
    print("status=CONSUMED_SELECTION_DEVELOPMENT_V5_TARGETED_PASS")
    print(f"report_sha256={report['report_sha256']}")
    print(f"development_protocol_sha256={report['development_protocol_sha256']}")
    print(f"candidate_count={len(report['candidate_ids'])}")
    print(f"task_count={len(report['task_ids'])}")
    print(f"result_count={report['result_count']}")
    print(f"new_inference_calls={report['new_inference_calls']}")
    print(f"parsed_count={parsed}")
    print(f"solved_count={solved}")
    print(f"recovered_v4_failures={recovered}")
    print(f"regressed_v4_solves={regressions}")
    print(f"output={args.artifact_root / 'consumed-selection-development-v5-self-review.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
