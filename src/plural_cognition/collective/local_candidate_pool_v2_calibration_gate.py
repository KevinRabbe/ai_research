"""Safe entrypoint for the candidate-pool v2 calibration gate.

A completed suite is immutable evidence.  This entrypoint validates and reuses it
verbatim instead of delegating to the pair runner, while incomplete states are
handled by the runner's global partial-pair preflight.

One source-frozen challenger intentionally has no pre-inference byte-size value.
For that artifact the immutable SHA-256 remains authoritative; candidates with a
frozen byte size continue to require both exact size and SHA-256.
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
from . import local_candidate_pool_v2_calibration as _runner
from .local_candidate_pool_v2_calibration import (
    CALIBRATION_SUITE_SCHEMA_V2,
    DEFAULT_TIMEOUT_SECONDS_V2,
    _canonical_json_bytes,
)


def _verify_model_files_with_optional_frozen_size(
    model_root: Path, sources: dict[str, dict[str, Any]]
) -> None:
    """Verify frozen model artifacts without inventing a missing frozen size.

    A ``None`` artifact_size_bytes value means the pre-inference source freeze
    deliberately bound the artifact by immutable revision and SHA-256 only.  We
    therefore record/accept the observed local size implicitly but never replace
    or relax the SHA-256 identity.  Any non-None frozen size remains mandatory.
    """

    for candidate_id in _runner.CANDIDATE_IDS_V2:
        source = sources[candidate_id]
        path = model_root / candidate_id / source["filename"]
        if not path.is_file():
            raise RuntimeError(f"required v2 calibration model is missing: {path}")
        size = path.stat().st_size
        frozen_size = source["artifact_size_bytes"]
        if frozen_size is not None and size != int(frozen_size):
            raise RuntimeError(
                f"model size mismatch for {candidate_id}: {size} != {frozen_size}"
            )
        digest = _runner._sha256_file(path)
        if digest != source["artifact_sha256"]:
            raise RuntimeError(f"model SHA-256 mismatch for {candidate_id}: {digest}")


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

        # Compatibility repair for the source-frozen Phi artifact whose
        # pre-inference freeze intentionally records artifact_size_bytes=None.
        # This changes only deterministic local artifact verification; all
        # prompts, model/runtime settings, pair identities, grading, and gate
        # thresholds remain owned by the frozen runner/protocol.
        _runner._verify_model_files = _verify_model_files_with_optional_frozen_size
        suite = _runner.run_calibration(
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
