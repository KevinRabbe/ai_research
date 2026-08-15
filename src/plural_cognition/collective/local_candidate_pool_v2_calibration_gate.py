"""Safe entrypoint for the candidate-pool v2 calibration gate.

A completed suite is immutable evidence.  This entrypoint validates and reuses it
verbatim instead of delegating to the pair runner, while incomplete states are
handled by the runner's global partial-pair preflight.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from .candidate_pool_v2_calibration_protocol import (
    FINAL_CALIBRATION_PROTOCOL_SHA256_V2,
)
from .local_candidate_pool_v2_calibration import (
    CALIBRATION_SUITE_SCHEMA_V2,
    DEFAULT_TIMEOUT_SECONDS_V2,
    _canonical_json_bytes,
    run_calibration,
)


def _validate_completed_suite(path: Path, *, software_revision: str) -> dict[str, Any]:
    suite = json.loads(path.read_text(encoding="ascii"))
    required = {
        "schema": CALIBRATION_SUITE_SCHEMA_V2,
        "scientific_status": "candidate-development-v2-calibration-only-not-selection-evidence",
        "status": "CANDIDATE_POOL_V2_CALIBRATION_COMPLETE",
        "software_revision": software_revision,
        "protocol_sha256": FINAL_CALIBRATION_PROTOCOL_SHA256_V2,
        "pair_count": 36,
        "selection_evidence": False,
    }
    for key, expected in required.items():
        if suite.get(key) != expected:
            raise RuntimeError(f"completed v2 calibration suite field drifted: {key}")
    unsigned = dict(suite)
    observed = unsigned.pop("report_sha256", None)
    expected_sha = hashlib.sha256(_canonical_json_bytes(unsigned)).hexdigest()
    if observed != expected_sha:
        raise RuntimeError("completed v2 calibration suite content drifted")
    results = suite.get("results")
    summaries = suite.get("summaries")
    if not isinstance(results, list) or len(results) != 36:
        raise RuntimeError("completed v2 calibration suite result count drifted")
    if not isinstance(summaries, list) or len(summaries) != 6:
        raise RuntimeError("completed v2 calibration suite summary count drifted")
    return suite


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely run, resume, or reuse the candidate-pool v2 calibration gate."
    )
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--load-repair-root", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--software-revision", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS_V2)
    parser.add_argument("--docker-executable", default="docker")
    return parser


def _print_suite(suite: dict[str, Any], *, reused: bool) -> None:
    print("status=CANDIDATE_POOL_V2_CALIBRATION_COMPLETE")
    print(f"completed_suite_reused={reused}")
    print(f"report_sha256={suite['report_sha256']}")
    print(f"protocol_sha256={suite['protocol_sha256']}")
    print(f"pair_count={suite['pair_count']}")
    print(f"eligible_candidate_count={suite['eligible_candidate_count']}/6")
    print("eligible_candidate_ids=" + ",".join(suite["eligible_candidate_ids"]))
    if reused:
        print("new_inference_attempt_count_this_invocation=0")
    else:
        print(
            "new_inference_attempt_count_this_invocation="
            + str(suite["new_inference_attempt_count_this_invocation"])
        )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    suite_path = args.artifact_root / "candidate-pool-v2-calibration-suite.json"
    try:
        if suite_path.is_file():
            suite = _validate_completed_suite(
                suite_path, software_revision=args.software_revision
            )
            _print_suite(suite, reused=True)
            return 0
        suite = run_calibration(
            runtime_root=args.runtime_root,
            model_root=args.model_root,
            load_repair_root=args.load_repair_root,
            artifact_root=args.artifact_root,
            software_revision=args.software_revision,
            timeout_seconds=args.timeout_seconds,
            docker_executable=args.docker_executable,
        )
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"status=CANDIDATE_POOL_V2_CALIBRATION_ABORT\nerror={exc}")
        return 2
    _print_suite(suite, reused=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
