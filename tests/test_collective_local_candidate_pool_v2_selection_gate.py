import hashlib
from pathlib import Path

from plural_cognition.collective.candidate_pool_v2_operational_freeze import (
    FINAL_CANDIDATE_IDS_V2,
    FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256,
)
from plural_cognition.collective.candidate_pool_v2_selection_protocol import (
    FINAL_SELECTION_PROTOCOL_SHA256_V2,
    SELECTION_PAIR_COUNT_V2,
    SELECTION_TASK_IDS_V2,
)
from plural_cognition.collective import local_candidate_pool_v2_selection_gate as gate
from plural_cognition.collective.local_candidate_pool_v2_selection import (
    SELECTION_SUITE_SCHEMA_V2,
    _canonical_json_bytes,
    _finalize_pair,
    _pair_id,
    _pair_root,
)
from plural_cognition.collective.repository_surgery_selection_freeze_v2 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2,
    SELECTION_PACK_SHA256_V2,
    SELECTION_QUALIFICATION_REPORT_SHA256_V2,
)


SOFTWARE_REVISION = "b" * 40


def _complete_suite(root: Path) -> dict[str, object]:
    results: list[dict[str, object]] = []
    for candidate_id in FINAL_CANDIDATE_IDS_V2:
        for task_id in SELECTION_TASK_IDS_V2:
            pair_root = _pair_root(root, candidate_id, task_id)
            pair_root.mkdir(parents=True)
            report = _finalize_pair(
                pair_root,
                {
                    "schema": "plural-cognition-candidate-pool-v2-selection-pair-v1",
                    "candidate_id": candidate_id,
                    "task_id": task_id,
                    "pair_id": _pair_id(candidate_id, task_id),
                    "software_revision": SOFTWARE_REVISION,
                    "protocol_sha256": FINAL_SELECTION_PROTOCOL_SHA256_V2,
                    "selection_pack_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2,
                    "selection_evidence": True,
                },
            )
            results.append(
                {
                    "candidate_id": candidate_id,
                    "task_id": task_id,
                    "report_sha256": report["report_sha256"],
                }
            )

    suite: dict[str, object] = {
        "schema": SELECTION_SUITE_SCHEMA_V2,
        "scientific_status": "candidate-pool-v2-fresh-selection-evidence",
        "status": "CANDIDATE_POOL_V2_SELECTION_COMPLETE",
        "software_revision": SOFTWARE_REVISION,
        "protocol_sha256": FINAL_SELECTION_PROTOCOL_SHA256_V2,
        "selection_pack_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2,
        "selection_pack_sha256": SELECTION_PACK_SHA256_V2,
        "qualification_report_sha256": SELECTION_QUALIFICATION_REPORT_SHA256_V2,
        "operational_config_freeze_sha256": FINAL_CANDIDATE_POOL_V2_OPERATIONAL_FREEZE_SHA256,
        "pair_count": SELECTION_PAIR_COUNT_V2,
        "new_inference_attempt_count_this_invocation": SELECTION_PAIR_COUNT_V2,
        "candidate_ids": list(FINAL_CANDIDATE_IDS_V2),
        "task_ids": list(SELECTION_TASK_IDS_V2),
        "results": results,
        "population_selection": {
            "status": "selected",
            "diagnostics": [
                {
                    "candidate_id": candidate_id,
                    "score": 1.0,
                    "valid_rate": 1.0,
                    "pass_count": 12,
                    "valid_count": 12,
                    "total_accelerator_time_ms": 1,
                    "total_tokens": 1,
                }
                for candidate_id in FINAL_CANDIDATE_IDS_V2
            ],
            "eligible_candidate_ids": list(FINAL_CANDIDATE_IDS_V2),
            "strongest_candidate_id": FINAL_CANDIDATE_IDS_V2[0],
            "selected_candidate_ids": list(FINAL_CANDIDATE_IDS_V2[:4]),
            "best_constituent_score": 1.0,
            "oracle_union_score": 1.0,
            "complementarity_headroom": 0.0,
            "mean_pairwise_error_correlation": None,
        },
        "selection_evidence": True,
    }
    suite["report_sha256"] = hashlib.sha256(_canonical_json_bytes(suite)).hexdigest()
    (root / "candidate-pool-v2-selection-suite.json").write_bytes(
        _canonical_json_bytes(suite) + b"\n"
    )
    return suite


def test_completed_selection_suite_is_validated_and_reused_without_runner(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    expected = _complete_suite(tmp_path)

    def fail_if_called(**kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("completed selection suite must not delegate to runner")

    monkeypatch.setattr(gate._runner, "run_selection", fail_if_called)
    result = gate.main(
        [
            "--runtime-root", str(tmp_path / "unused-runtime"),
            "--model-root", str(tmp_path / "unused-models"),
            "--artifact-root", str(tmp_path),
            "--selection-pack", str(tmp_path / "unused-pack"),
            "--qualification-report", str(tmp_path / "unused-qualification"),
            "--calibration-suite", str(tmp_path / "unused-calibration"),
            "--software-revision", SOFTWARE_REVISION,
        ]
    )
    assert result == 0
    output = capsys.readouterr().out
    assert "completed_suite_reused=True" in output
    assert "new_inference_attempt_count_this_invocation=0" in output
    assert expected["report_sha256"] in output


def test_completed_selection_suite_content_hash_is_checked(tmp_path: Path) -> None:
    suite = _complete_suite(tmp_path)
    suite["pair_count"] = 59
    path = tmp_path / "candidate-pool-v2-selection-suite.json"
    path.write_bytes(_canonical_json_bytes(suite) + b"\n")

    try:
        gate._validate_completed_suite(
            path,
            artifact_root=tmp_path,
            software_revision=SOFTWARE_REVISION,
        )
    except RuntimeError as exc:
        assert "field drifted" in str(exc) or "content drifted" in str(exc)
    else:
        raise AssertionError("tampered completed suite was accepted")
