from __future__ import annotations

import hashlib
import json
import subprocess

from plural_cognition.collective import (
    candidate_pool_v3_expansion_load_runner_freeze as freeze,
)


def _git_blob(path: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", f"HEAD:{path}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip()


def test_v3_expansion_load_runner_freeze_has_exact_canonical_identity() -> None:
    payload = freeze.candidate_pool_v3_expansion_load_runner_freeze_payload()
    digest = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
    assert digest == freeze.EXPECTED_EXPANSION_LOAD_RUNNER_FREEZE_SHA256_V3
    assert digest == (
        "f64bb5a63dbe9e9141f44840d55b33420decaca71cc108c2842e8d43175ec763"
    )


def test_v3_expansion_load_runner_freeze_binds_exact_green_runner_sources() -> None:
    payload = freeze.candidate_pool_v3_expansion_load_runner_freeze_payload()
    assert payload["runner"] == {
        "source_revision": "3a8a80d8fdc28d9de36f7ee248d07d952117f428",
        "source_git_blob_sha1": "0241f1d38dc9db2a86cfd0cbf2dd9169deceb403",
        "test_git_blob_sha1": "af1c88e272408376794444f0b45ce3f0ee650aaf",
        "protocol_sha256": "6670ae531b31bd0548947bcc4ce0b8248204648f0bd3d280c68e1211bed340a4",
    }
    assert _git_blob(
        "src/plural_cognition/collective/local_candidate_pool_v3_expansion_load_qualification.py"
    ) == payload["runner"]["source_git_blob_sha1"]
    assert _git_blob(
        "tests/test_collective_local_candidate_pool_v3_expansion_load_qualification.py"
    ) == payload["runner"]["test_git_blob_sha1"]


def test_v3_expansion_load_runner_freeze_binds_three_exact_scout_artifacts() -> None:
    payload = freeze.candidate_pool_v3_expansion_load_runner_freeze_payload()
    assert payload["predecessor_source_freeze_sha256"] == (
        "7e3a49def60361dc2ce82f32c750d44b4dd0cb2d024b79f76d8469be3e2bec03"
    )
    assert payload["source_freeze_revision"] == (
        "dea35b4c11d8de39b978bf3a4ba5f098cfab795b"
    )
    assert payload["scout_ids"] == [
        "qwen3-14b-q5km",
        "ministral-3-14b-instruct-2512-q5km",
        "ministral-3-8b-instruct-2512-q5km",
    ]
    assert [item["artifact_size_bytes"] for item in payload["model_artifacts"]] == [
        10_514_569_568,
        9_621_091_904,
        6_059_268_512,
    ]
    assert [item["artifact_sha256"] for item in payload["model_artifacts"]] == [
        "e7c9aba1129ca2936be9eca01419d9f86af40e08caa01230d5574b34d08e3e31",
        "f16fef77021df0d4c22e69140a2038478370492f51867b6237699918ae711000",
        "7a5454127ec772e2389f0e71a77fedb88b83d4366d8a69facd0cfd0898f04d35",
    ]


def test_v3_expansion_load_runner_freeze_authorizes_only_three_load_only_calls() -> None:
    payload = freeze.candidate_pool_v3_expansion_load_runner_freeze_payload()
    authorization = payload["authorization"]
    assert authorization == {
        "candidate_model_calls_consumed_before_freeze": 0,
        "candidate_model_calls_authorized": 3,
        "exact_artifact_downloads_authorized": True,
        "one_call_per_scout": True,
        "load_only": True,
        "capability_prompt": False,
        "max_attempts_per_scout": 1,
        "attempt_marker_before_inference": True,
        "partial_pair_blocks_all_new_inference": True,
        "completed_result_reused_verbatim": True,
        "raw_stdout_stderr_before_classification": True,
        "full_gpu_offload_required": True,
        "candidate_specific_runtime_tuning": False,
        "automatic_reruns": False,
        "artifact_substitution": False,
        "scout_reordering": False,
        "first_invocation_requires_fresh_root": True,
        "selection_evidence": False,
    }
    assert payload["model_root"] == "artifacts/capable-collective/m2"
    assert payload["artifact_root"] == "artifacts/capable-collective/e3l"
    assert payload["selection_evidence"] is False


def test_v3_expansion_load_runner_freeze_blocks_calibration_and_selection() -> None:
    downstream = freeze.candidate_pool_v3_expansion_load_runner_freeze_payload()[
        "downstream"
    ]
    assert downstream[
        "load_outcome_freeze_required_before_calibration_runner_authoring"
    ] is True
    assert downstream["calibration_runner_authoring_authorized"] is False
    assert downstream["calibration_inference_authorized"] is False
    assert downstream["selection_pack_authoring_authorized"] is False
    assert downstream["selection_inference_authorized"] is False
    assert downstream["plural_synthesis_authorized"] is False
