from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from plural_cognition.collective import (
    local_candidate_pool_v3_expansion_calibration as runner,
)
from plural_cognition.collective.content_store import FileContentStore
from plural_cognition.collective.local_candidate_pool_v2_load_observer_repair import (
    RecoveryAttemptObservation,
)
from plural_cognition.collective.repository_surgery_calibration_pack_v3_repair import (
    repaired_calibration_blueprints_v3,
)


REVISION = "1" * 40


def _complete_report(
    *,
    candidate_id: str,
    task_id: str,
    parse_valid: bool,
    solved: bool,
    peak_gpu: int = 1000,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": runner.EXPANSION_CALIBRATION_PAIR_SCHEMA_V3,
        "scientific_status": (
            "candidate-development-v3-expansion-calibration-only-not-selection-evidence"
        ),
        "status": "CANDIDATE_POOL_V3_EXPANSION_CALIBRATION_PAIR_COMPLETE",
        "candidate_id": candidate_id,
        "task_id": task_id,
        "pair_id": runner._pair_id(candidate_id, task_id),
        "software_revision": REVISION,
        "runner_protocol_sha256": (
            runner.expansion_calibration_runner_protocol_sha256_v3()
        ),
        "representation_protocol_sha256": (
            runner.EXPECTED_V3_REPRESENTATION_PROTOCOL_SHA256
        ),
        "qualification_freeze_sha256": (
            runner.EXPECTED_CALIBRATION_QUALIFICATION_FREEZE_SHA256_V3
        ),
        "load_outcome_freeze_sha256": (
            runner.EXPECTED_EXPANSION_LOAD_OUTCOME_FREEZE_SHA256_V3
        ),
        "source_identity_sha256": "a" * 64,
        "model_file_sha256": "b" * 64,
        "model_file_size_bytes": 1,
        "task_sha256": "c" * 64,
        "prompt_sha256": "d" * 64,
        "command_sha256": "e" * 64,
        "attempt_observation": {
            "peak_gpu_used_mib": peak_gpu,
        },
        "process_stdout_sha256": "f" * 64,
        "stderr_sha256": "0" * 64,
        "token_counts_observed": False,
        "input_tokens": 0,
        "output_tokens": 0,
        "inference_valid": True,
        "inference_failure": None,
        "offloaded_layers": 1,
        "total_layers": 1,
        "transcript_sha256": "1" * 64,
        "assistant_sha256": "2" * 64,
        "reasoning_sha256": None,
        "raw_artifact_sha256": "3" * 64,
        "parse_valid": parse_valid,
        "parse_mode": "test" if parse_valid else None,
        "parse_error": None if parse_valid else "invalid",
        "patch_sha256": "4" * 64 if parse_valid else None,
        "submission_sha256": "5" * 64 if parse_valid else None,
        "evaluation_sha256": "6" * 64 if parse_valid else None,
        "exact_accuracy": 1.0 if solved else 0.0,
        "evaluator_valid_rate": 1.0 if solved else 0.0,
        "solved": solved,
        "selection_evidence": False,
    }
    payload["report_sha256"] = runner._canonical_sha256(payload)
    return payload


def _write_candidate(
    root,
    candidate_id: str,
    *,
    parse_valid_count: int,
    solved_count: int,
) -> list[dict[str, object]]:
    reports = []
    for index, task_id in enumerate(runner.CALIBRATION_TASK_IDS_V3):
        report = _complete_report(
            candidate_id=candidate_id,
            task_id=task_id,
            parse_valid=index < parse_valid_count,
            solved=index < solved_count,
            peak_gpu=1000 + index,
        )
        pair_root = runner._pair_root(root, candidate_id, task_id)
        pair_root.mkdir(parents=True)
        runner._write_json_atomic(pair_root / "result.json", report)
        reports.append(report)
    return reports


def test_expansion_calibration_protocol_binds_sequential_budget_and_gate() -> None:
    payload = runner.expansion_calibration_runner_protocol_payload_v3()
    assert payload["scout_ids"] == [
        "qwen3-14b-q5km",
        "ministral-3-14b-instruct-2512-q5km",
        "ministral-3-8b-instruct-2512-q5km",
    ]
    assert payload["task_ids"] == list(runner.CALIBRATION_TASK_IDS_V3)
    assert payload["max_pair_count"] == 18
    assert payload["gate"] == {
        "required_parse_valid_count": 6,
        "minimum_solved_count": 4,
    }
    assert payload["sequential_policy"] == {
        "ordered_scout_ids": payload["scout_ids"],
        "stop_after_first_gate_pass": True,
        "max_candidates_calibrated": 3,
        "max_candidate_task_calls": 18,
        "one_call_per_pair": True,
        "max_attempts_per_pair": 1,
        "attempt_marker_before_inference": True,
        "partial_pair_blocks_all_new_inference": True,
        "completed_result_reused_verbatim": True,
        "failed_candidate_rerun_authorized": False,
        "candidate_specific_prompt_tuning": False,
        "automatic_reruns": False,
    }
    assert (
        runner.expansion_calibration_runner_protocol_sha256_v3()
        == runner.EXPECTED_EXPANSION_CALIBRATION_RUNNER_PROTOCOL_SHA256_V3
    )
    assert payload["selection_evidence"] is False


def test_expansion_candidate_sources_bind_exact_frozen_artifacts() -> None:
    sources = runner.expansion_candidate_sources_v3()
    assert tuple(sources) == runner.EXPANSION_SCOUT_IDS_V3
    assert sources["qwen3-14b-q5km"]["artifact_size_bytes"] == 10_514_569_568
    assert sources["qwen3-14b-q5km"]["artifact_sha256"] == (
        "e7c9aba1129ca2936be9eca01419d9f86af40e08caa01230d5574b34d08e3e31"
    )
    assert sources["qwen3-14b-q5km"]["source_identity_sha256"] == (
        "1de970c52eb3c74a82cfbdc3b9a217c0f50ef0556e030b77b01a033bec184671"
    )
    assert sources["ministral-3-14b-instruct-2512-q5km"]["artifact_sha256"] == (
        "f16fef77021df0d4c22e69140a2038478370492f51867b6237699918ae711000"
    )
    assert sources["ministral-3-14b-instruct-2512-q5km"]["source_identity_sha256"] == (
        "faf4eb8d8b3f2f18151442129d21a3244b7a06ffdad86f6dcff2f5117d7fbdaf"
    )
    assert sources["ministral-3-8b-instruct-2512-q5km"]["artifact_sha256"] == (
        "7a5454127ec772e2389f0e71a77fedb88b83d4366d8a69facd0cfd0898f04d35"
    )
    assert sources["ministral-3-8b-instruct-2512-q5km"]["source_identity_sha256"] == (
        "b0a87b9497a2cfee76a917f601e07ca586a5e019b3d417f1f1200af3bba6c8bb"
    )


def test_expansion_pair_ids_bind_candidate_task_and_protocol() -> None:
    task_a, task_b = runner.CALIBRATION_TASK_IDS_V3[:2]
    first = runner._pair_id(runner.EXPANSION_SCOUT_IDS_V3[0], task_a)
    assert len(first) == 64
    assert first == runner._pair_id(runner.EXPANSION_SCOUT_IDS_V3[0], task_a)
    assert first != runner._pair_id(runner.EXPANSION_SCOUT_IDS_V3[0], task_b)
    assert first != runner._pair_id(runner.EXPANSION_SCOUT_IDS_V3[1], task_a)


def test_partial_pair_blocks_all_new_expansion_calibration(tmp_path) -> None:
    candidate_id = runner.EXPANSION_SCOUT_IDS_V3[0]
    task_id = runner.CALIBRATION_TASK_IDS_V3[0]
    pair_root = runner._pair_root(tmp_path, candidate_id, task_id)
    pair_root.mkdir(parents=True)
    (pair_root / "attempt.json").write_text("{}", encoding="ascii")
    with pytest.raises(RuntimeError, match="blocks all new inference"):
        runner._scan_existing_progress(tmp_path, software_revision=REVISION)


def test_scan_stops_at_first_passing_scout_and_rejects_later_evidence(
    tmp_path,
) -> None:
    first = runner.EXPANSION_SCOUT_IDS_V3[0]
    reports = _write_candidate(
        tmp_path,
        first,
        parse_valid_count=6,
        solved_count=4,
    )
    results, summaries, passing = runner._scan_existing_progress(
        tmp_path, software_revision=REVISION
    )
    assert len(results) == 6
    assert results == reports
    assert len(summaries) == 1
    assert summaries[0]["passed_calibration_gate"] is True
    assert passing == first

    second = runner.EXPANSION_SCOUT_IDS_V3[1]
    task_id = runner.CALIBRATION_TASK_IDS_V3[0]
    report = _complete_report(
        candidate_id=second,
        task_id=task_id,
        parse_valid=True,
        solved=True,
    )
    pair_root = runner._pair_root(tmp_path, second, task_id)
    pair_root.mkdir(parents=True)
    runner._write_json_atomic(pair_root / "result.json", report)
    with pytest.raises(RuntimeError, match="after an earlier passing scout"):
        runner._scan_existing_progress(tmp_path, software_revision=REVISION)


def test_nonprefix_task_evidence_is_rejected(tmp_path) -> None:
    candidate = runner.EXPANSION_SCOUT_IDS_V3[0]
    second_task = runner.CALIBRATION_TASK_IDS_V3[1]
    report = _complete_report(
        candidate_id=candidate,
        task_id=second_task,
        parse_valid=True,
        solved=True,
    )
    pair_root = runner._pair_root(tmp_path, candidate, second_task)
    pair_root.mkdir(parents=True)
    runner._write_json_atomic(pair_root / "result.json", report)
    with pytest.raises(RuntimeError, match="non-prefix"):
        runner._scan_existing_progress(tmp_path, software_revision=REVISION)


def test_positive_suite_stops_after_first_scout(tmp_path) -> None:
    first = runner.EXPANSION_SCOUT_IDS_V3[0]
    results = [
        _complete_report(
            candidate_id=first,
            task_id=task_id,
            parse_valid=True,
            solved=index < 4,
        )
        for index, task_id in enumerate(runner.CALIBRATION_TASK_IDS_V3)
    ]
    summary = runner._candidate_summary(first, results)
    suite = runner._finalize_suite(
        artifact_root=tmp_path,
        software_revision=REVISION,
        results=results,
        summaries=[summary],
        passing_candidate_id=first,
        new_attempts=6,
    )
    assert suite["pair_count"] == 6
    assert suite["evaluated_candidate_ids"] == [first]
    assert suite["unevaluated_candidate_ids"] == list(
        runner.EXPANSION_SCOUT_IDS_V3[1:]
    )
    assert suite["passing_candidate_id"] == first
    assert suite["population_feasible"] is True
    assert suite["stopped_after_first_gate_pass"] is True


def test_negative_suite_requires_all_three_scouts(tmp_path) -> None:
    results = []
    summaries = []
    for candidate in runner.EXPANSION_SCOUT_IDS_V3:
        own = [
            _complete_report(
                candidate_id=candidate,
                task_id=task_id,
                parse_valid=True,
                solved=index < 3,
            )
            for index, task_id in enumerate(runner.CALIBRATION_TASK_IDS_V3)
        ]
        results.extend(own)
        summaries.append(runner._candidate_summary(candidate, own))
    suite = runner._finalize_suite(
        artifact_root=tmp_path,
        software_revision=REVISION,
        results=results,
        summaries=summaries,
        passing_candidate_id=None,
        new_attempts=18,
    )
    assert suite["pair_count"] == 18
    assert suite["evaluated_candidate_ids"] == list(
        runner.EXPANSION_SCOUT_IDS_V3
    )
    assert suite["unevaluated_candidate_ids"] == []
    assert suite["passing_candidate_id"] is None
    assert suite["population_feasible"] is False


def test_attempt_marker_precedes_inference_and_completed_pair_is_reused(
    tmp_path,
    monkeypatch,
) -> None:
    candidate_id = runner.EXPANSION_SCOUT_IDS_V3[0]
    blueprint = repaired_calibration_blueprints_v3()[0]
    artifact_root = tmp_path / "artifacts"
    model_root = tmp_path / "models"
    model_dir = model_root / candidate_id
    model_dir.mkdir(parents=True)
    model_path = model_dir / "model.gguf"
    model_path.write_bytes(b"model")
    store = FileContentStore(tmp_path / "store")
    material = SimpleNamespace(visible_task=SimpleNamespace(sha256="c" * 64))
    source = {
        "candidate_id": candidate_id,
        "filename": "model.gguf",
        "artifact_sha256": "a" * 64,
        "source_identity_sha256": "b" * 64,
    }
    pair_root = runner._pair_root(
        artifact_root,
        candidate_id,
        blueprint.task_id,
    )
    calls = 0

    monkeypatch.setattr(
        runner,
        "_base_load_command",
        lambda **kwargs: ("llama-cli", "test"),
    )

    def fake_run(command, *, timeout_seconds):
        nonlocal calls
        calls += 1
        assert timeout_seconds == 17
        assert (pair_root / "attempt.json").is_file()
        attempt = json.loads(
            (pair_root / "attempt.json").read_text(encoding="ascii")
        )
        assert attempt["max_attempts"] == 1
        assert attempt["inference_attempt_authorized"] is True
        assert attempt["selection_evidence"] is False
        return (
            RecoveryAttemptObservation(
                command=tuple(command),
                exit_code=1,
                timed_out=False,
                elapsed_seconds=0.01,
                stdout_sha256=hashlib.sha256(b"").hexdigest(),
                stderr_sha256=hashlib.sha256(b"").hexdigest(),
                stdout_bytes=0,
                stderr_bytes=0,
                baseline_gpu_used_mib=0,
                peak_gpu_used_mib=0,
                peak_process_rss_bytes=0,
                monitor_error=None,
            ),
            b"",
            b"",
        )

    monkeypatch.setattr(runner, "_run_raw_attempt", fake_run)
    report, attempted = runner._run_pair_once(
        candidate_id=candidate_id,
        source=source,
        blueprint=blueprint,
        material=material,
        cli=tmp_path / "llama-cli.exe",
        model_root=model_root,
        artifact_root=artifact_root,
        store=store,
        configuration=None,
        staging_root=tmp_path / "staging",
        software_revision=REVISION,
        timeout_seconds=17,
        docker_executable="docker",
    )
    assert attempted is True
    assert calls == 1
    assert report["inference_valid"] is False
    assert report["parse_valid"] is False
    assert report["solved"] is False
    assert (pair_root / "result.json").is_file()

    def forbidden_run(*args, **kwargs):
        raise AssertionError("completed expansion pair attempted a second model call")

    monkeypatch.setattr(runner, "_run_raw_attempt", forbidden_run)
    reused, attempted_again = runner._run_pair_once(
        candidate_id=candidate_id,
        source=source,
        blueprint=blueprint,
        material=material,
        cli=tmp_path / "llama-cli.exe",
        model_root=model_root,
        artifact_root=artifact_root,
        store=store,
        configuration=None,
        staging_root=tmp_path / "staging",
        software_revision=REVISION,
        timeout_seconds=17,
        docker_executable="docker",
    )
    assert attempted_again is False
    assert reused["report_sha256"] == report["report_sha256"]
    assert calls == 1
