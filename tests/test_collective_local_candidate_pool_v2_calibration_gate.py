from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from plural_cognition.collective import local_candidate_pool_v2_calibration_gate as gate
from plural_cognition.collective.candidate_pool_v2_calibration_protocol import (
    FINAL_CALIBRATION_PROTOCOL_SHA256_V2,
)
from plural_cognition.collective.local_candidate_pool_v2_calibration import (
    CALIBRATION_SUITE_SCHEMA_V2,
    _canonical_json_bytes,
)


def _suite(revision: str) -> dict:
    payload = {
        "schema": CALIBRATION_SUITE_SCHEMA_V2,
        "scientific_status": "candidate-development-v2-calibration-only-not-selection-evidence",
        "status": "CANDIDATE_POOL_V2_CALIBRATION_COMPLETE",
        "software_revision": revision,
        "protocol_sha256": FINAL_CALIBRATION_PROTOCOL_SHA256_V2,
        "pair_count": 36,
        "results": [
            {"candidate_id": f"c{i // 6}", "task_id": f"t{i % 6}", "report_sha256": "0" * 64, "parse_valid": True, "solved": True}
            for i in range(36)
        ],
        "summaries": [
            {"candidate_id": f"c{i}", "task_count": 6, "parse_valid_count": 6, "solved_count": 6, "passed_calibration_gate": True, "peak_gpu_used_mib": 1}
            for i in range(6)
        ],
        "eligible_candidate_ids": [f"c{i}" for i in range(6)],
        "eligible_candidate_count": 6,
        "selection_evidence": False,
    }
    payload["report_sha256"] = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    return payload


def test_completed_suite_is_validated_without_rewriting(tmp_path: Path) -> None:
    revision = "a" * 40
    path = tmp_path / "candidate-pool-v2-calibration-suite.json"
    suite = _suite(revision)
    raw = _canonical_json_bytes(suite) + b"\n"
    path.write_bytes(raw)
    observed = gate._validate_completed_suite(path, software_revision=revision)
    assert observed == suite
    assert path.read_bytes() == raw


def test_completed_suite_rejects_content_drift(tmp_path: Path) -> None:
    revision = "b" * 40
    path = tmp_path / "candidate-pool-v2-calibration-suite.json"
    suite = _suite(revision)
    suite["eligible_candidate_count"] = 5
    path.write_text(json.dumps(suite), encoding="ascii")
    with pytest.raises(RuntimeError, match="content drifted"):
        gate._validate_completed_suite(path, software_revision=revision)
