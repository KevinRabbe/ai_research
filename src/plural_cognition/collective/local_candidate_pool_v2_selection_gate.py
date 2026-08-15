"""Safe entrypoint for the one-shot candidate-pool v2 selection run.

A completed 60-pair suite is immutable selection evidence. This entrypoint
validates and reuses it verbatim instead of delegating to the pair runner. Any
incomplete state is handled by the runner's global partial-pair preflight before
another model call can be authorized.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from .candidate_pool_v2_operational_freeze import (
    FINAL_CANDIDATE_IDS_V2,
    FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256,
)
from .candidate_pool_v2_selection_protocol import (
    FINAL_SELECTION_PROTOCOL_SHA256_V2,
    SELECTION_PAIR_COUNT_V2,
    SELECTION_TASK_IDS_V2,
)
from . import local_candidate_pool_v2_selection as _runner
from .local_candidate_pool_v2_selection import (
    DEFAULT_TIMEOUT_SECONDS_V2,
    SELECTION_SUITE_SCHEMA_V2,
    _canonical_json_bytes,
)
from .repository_surgery_selection_freeze_v2 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2,
    SELECTION_PACK_SHA256_V2,
    SELECTION_QUALIFICATION_REPORT_SHA256_V2,
)


def _validate_completed_suite(
    path: Path, *, artifact_root: Path, software_revision: str
) -> dict[str, Any]:
    suite = json.loads(path.read_text(encoding="ascii"))
    required = {
        "schema": SELECTION_SUITE_SCHEMA_V2,
        "scientific_status": "candidate-pool-v2-fresh-selection-evidence",
        "status": "CANDIDATE_POOL_V2_SELECTION_COMPLETE",
        "software_revision": software_revision,
        "protocol_sha256": FINAL_SELECTION_PROTOCOL_SHA256_V2,
        "selection_pack_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2,
        "selection_pack_sha256": SELECTION_PACK_SHA256_V2,
        "qualification_report_sha256": SELECTION_QUALIFICATION_REPORT_SHA256_V2,
        "operational_config_freeze_sha256": FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256,
        "pair_count": SELECTION_PAIR_COUNT_V2,
        "selection_evidence": True,
    }
    for key, expected in required.items():
        if suite.get(key) != expected:
            raise RuntimeError(f"completed v2 selection suite field drifted: {key}")
    if tuple(suite.get("candidate_ids", ())) != FINAL_CANDIDATE_IDS_V2:
        raise RuntimeError("completed v2 selection suite candidate order drifted")
    if tuple(suite.get("task_ids", ())) != SELECTION_TASK_IDS_V2:
        raise RuntimeError("completed v2 selection suite task order drifted")

    unsigned = dict(suite)
    observed = unsigned.pop("report_sha256", None)
    expected_sha = hashlib.sha256(_canonical_json_bytes(unsigned)).hexdigest()
    if observed != expected_sha:
        raise RuntimeError("completed v2 selection suite content drifted")

    results = suite.get("results")
    if not isinstance(results, list) or len(results) != SELECTION_PAIR_COUNT_V2:
        raise RuntimeError("completed v2 selection suite result count drifted")
    expected_pairs = [
        (candidate_id, task_id)
        for candidate_id in FINAL_CANDIDATE_IDS_V2
        for task_id in SELECTION_TASK_IDS_V2
    ]
    observed_pairs = [(item.get("candidate_id"), item.get("task_id")) for item in results]
    if observed_pairs != expected_pairs:
        raise RuntimeError("completed v2 selection suite result matrix drifted")

    complete, pair_reports = _runner._preflight_pair_states(
        artifact_root, software_revision=software_revision
    )
    if complete != SELECTION_PAIR_COUNT_V2 or len(pair_reports) != SELECTION_PAIR_COUNT_V2:
        raise RuntimeError("completed v2 selection suite lacks complete pair evidence")
    pair_sha = {
        (item["candidate_id"], item["task_id"]): item["report_sha256"]
        for item in pair_reports
    }
    for item in results:
        key = (item["candidate_id"], item["task_id"])
        if item.get("report_sha256") != pair_sha.get(key):
            raise RuntimeError(f"completed v2 selection suite pair binding drifted: {key}")

    selection = suite.get("population_selection")
    if not isinstance(selection, dict):
        raise RuntimeError("completed v2 selection suite population selection is missing")
    diagnostics = selection.get("diagnostics")
    if not isinstance(diagnostics, list) or len(diagnostics) != len(FINAL_CANDIDATE_IDS_V2):
        raise RuntimeError("completed v2 selection diagnostics drifted")
    if tuple(item.get("candidate_id") for item in diagnostics) != FINAL_CANDIDATE_IDS_V2:
        raise RuntimeError("completed v2 selection diagnostic candidate order drifted")
    selected = selection.get("selected_candidate_ids")
    status = selection.get("status")
    if status == "selected":
        if not isinstance(selected, list) or len(selected) != 4:
            raise RuntimeError("completed v2 selection population size drifted")
    elif status == "insufficient-eligible":
        if selected != []:
            raise RuntimeError("insufficient-eligible suite unexpectedly selected candidates")
    else:
        raise RuntimeError("completed v2 selection status drifted")
    return suite


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely run, resume, or reuse the frozen candidate-pool v2 selection."
    )
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--selection-pack", required=True, type=Path)
    parser.add_argument("--qualification-report", required=True, type=Path)
    parser.add_argument("--calibration-suite", required=True, type=Path)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS_V2)
    parser.add_argument("--docker-executable", default="docker")
    return parser


def _print_suite(suite: dict[str, Any], *, reused: bool) -> None:
    selection = suite["population_selection"]
    print("status=CANDIDATE_POOL_V2_SELECTION_COMPLETE")
    print(f"completed_suite_reused={reused}")
    print(f"report_sha256={suite['report_sha256']}")
    print(f"protocol_sha256={suite['protocol_sha256']}")
    print(f"selection_pack_freeze_sha256={suite['selection_pack_freeze_sha256']}")
    print(f"pair_count={suite['pair_count']}")
    if reused:
        print("new_inference_attempt_count_this_invocation=0")
    else:
        print(
            "new_inference_attempt_count_this_invocation="
            + str(suite["new_inference_attempt_count_this_invocation"])
        )
    for diagnostic in selection["diagnostics"]:
        print(
            f"candidate={diagnostic['candidate_id']} score={diagnostic['score']:.6f} "
            f"valid_rate={diagnostic['valid_rate']:.6f} pass_count={diagnostic['pass_count']} "
            f"valid_count={diagnostic['valid_count']} accelerator_time_ms={diagnostic['total_accelerator_time_ms']} "
            f"tokens={diagnostic['total_tokens']}"
        )
    print(f"selection_status={selection['status']}")
    print(f"eligible_candidate_ids={','.join(selection['eligible_candidate_ids'])}")
    print(f"strongest_candidate_id={selection['strongest_candidate_id'] or ''}")
    print(f"selected_candidate_ids={','.join(selection['selected_candidate_ids'])}")
    print(f"best_constituent_score={selection['best_constituent_score']}")
    print(f"oracle_union_score={selection['oracle_union_score']}")
    print(f"complementarity_headroom={selection['complementarity_headroom']}")
    print(f"mean_pairwise_error_correlation={selection['mean_pairwise_error_correlation']}")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    suite_path = args.artifact_root / "candidate-pool-v2-selection-suite.json"
    try:
        if suite_path.is_file():
            suite = _validate_completed_suite(
                suite_path,
                artifact_root=args.artifact_root,
                software_revision=args.software_revision,
            )
            _print_suite(suite, reused=True)
            return 0

        suite = _runner.run_selection(
            runtime_root=args.runtime_root,
            model_root=args.model_root,
            artifact_root=args.artifact_root,
            selection_pack_path=args.selection_pack,
            qualification_path=args.qualification_report,
            calibration_suite_path=args.calibration_suite,
            software_revision=args.software_revision,
            timeout_seconds=args.timeout_seconds,
            docker_executable=args.docker_executable,
        )
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"status=CANDIDATE_POOL_V2_SELECTION_ABORT\nerror={exc}")
        return 2
    _print_suite(suite, reused=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
