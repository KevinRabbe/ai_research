from __future__ import annotations

import hashlib
import json
import subprocess

from plural_cognition.collective import candidate_pool_v3_calibration_runner_freeze as freeze


def _git_blob(path: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", f"HEAD:{path}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip()


def test_v3_calibration_runner_freeze_has_exact_canonical_identity() -> None:
    payload = freeze.candidate_pool_v3_calibration_runner_freeze_payload()
    digest = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
    assert digest == freeze.EXPECTED_CALIBRATION_RUNNER_FREEZE_SHA256_V3
    assert digest == "6a2b815a3d2cd6b21c77f10bcd4725c05ba34a9a4605506940d85e72c5373cf9"


def test_v3_calibration_runner_freeze_binds_exact_green_runner_sources() -> None:
    payload = freeze.candidate_pool_v3_calibration_runner_freeze_payload()
    assert payload["runner"] == {
        "source_revision": "0aec10cb4dc72c54dc933439c0e4e653edfcccd7",
        "source_git_blob_sha1": "e4e03da726ecf0ce2694c49b69a3c32896dfbaa3",
        "test_git_blob_sha1": "189b1b91fc25e662fa6ce7bc0cc37508b0f2e30b",
        "protocol_sha256": "2e3984de232ddab4b9a96f8363a331b013ce1c68f9a1b91bc651f1312ad9b600",
    }
    assert _git_blob(
        "src/plural_cognition/collective/local_candidate_pool_v3_calibration.py"
    ) == payload["runner"]["source_git_blob_sha1"]
    assert _git_blob(
        "tests/test_collective_local_candidate_pool_v3_calibration.py"
    ) == payload["runner"]["test_git_blob_sha1"]


def test_v3_calibration_runner_freeze_authorizes_only_frozen_development_pairs() -> None:
    payload = freeze.candidate_pool_v3_calibration_runner_freeze_payload()
    assert payload["candidate_ids"] == [
        "qwen3-8b-q8",
        "qwen2.5-coder-14b-q5km",
        "devstral-24b-q4km",
        "gpt-oss-20b-mxfp4",
    ]
    assert len(payload["task_ids"]) == 6
    assert payload["gate"] == {
        "required_parse_valid_count": 6,
        "minimum_solved_count": 4,
    }
    authorization = payload["authorization"]
    assert authorization == {
        "pair_count": 24,
        "candidate_model_calls_consumed_before_freeze": 0,
        "candidate_model_calls_authorized": 24,
        "one_call_per_pair": True,
        "max_attempts_per_pair": 1,
        "attempt_marker_before_inference": True,
        "partial_pair_blocks_all_new_inference": True,
        "completed_result_reused_verbatim": True,
        "candidate_specific_tuning": False,
        "automatic_reruns": False,
        "artifact_root": "artifacts/capable-collective/c3",
        "first_invocation_requires_fresh_root": True,
        "selection_evidence": False,
    }
    assert payload["selection_evidence"] is False


def test_v3_calibration_runner_freeze_binds_qualified_predecessors_and_models() -> None:
    payload = freeze.candidate_pool_v3_calibration_runner_freeze_payload()
    assert payload["predecessor_qualification_freeze_sha256"] == (
        "b121dccd76616913fe144d8d298bc38a58bc278a1c6ba7e630e67c3bbaaef593"
    )
    assert payload["representation_protocol_sha256"] == (
        "28243c1a330bbc51734aa9083f98ee8a2257c17f6290c71ec9bbb4404bca3c61"
    )
    assert payload["qualification"]["repaired_pack_sha256"] == (
        "c00d98ed758016dab5571570ababbcbb6c639aa39ad87be34f9c37cddc803513"
    )
    assert payload["qualification"]["repaired_qualification_sha256"] == (
        "255f7a1dadf12e0dfd5107ab21c48cbaa07fe91ae937095001f00249750b2923"
    )
    assert payload["qualification"]["qualified_docker_report_sha256"] == (
        "2d2e3af2685a826b92cc03c36865cd74f1c4c954520b9448c82edbc294a70b04"
    )
    assert [item["artifact_sha256"] for item in payload["model_artifacts"]] == [
        "408b955510e196121c1c375201744783b5c9a43c7956d73fc78df54c66e883d6",
        "98ab25e0132e3f1e6d3554e1b64de2b5021908819b740d9c208430117e49a775",
        "4a9ec4e1b7fa7b8d3b26e56a54efe251349bb67d8a623bae662353a9d84e4b9b",
        "27cd6c432c7672cb812a92f611cf3ba7bbc35928262bb1e1253ff4ee6ae35901",
    ]
