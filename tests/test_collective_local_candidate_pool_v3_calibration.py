from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from plural_cognition.collective import local_candidate_pool_v3_calibration as v3
from plural_cognition.collective.content_store import FileContentStore
from plural_cognition.collective.local_candidate_pool_v2_load_observer_repair import (
    RecoveryAttemptObservation,
)
from plural_cognition.collective.repository_surgery_calibration_pack_v3_repair import (
    repaired_calibration_blueprints_v3,
)


def test_v3_runner_protocol_binds_exact_matrix_and_one_attempt_policy() -> None:
    payload = v3.calibration_runner_protocol_payload_v3()
    assert payload["candidate_ids"] == [
        "qwen3-8b-q8",
        "qwen2.5-coder-14b-q5km",
        "devstral-24b-q4km",
        "gpt-oss-20b-mxfp4",
    ]
    assert payload["pair_count"] == 24
    assert payload["gate"] == {
        "required_parse_valid_count": 6,
        "minimum_solved_count": 4,
    }
    assert payload["pair_policy"] == {
        "max_attempts": 1,
        "attempt_marker_before_inference": True,
        "partial_pair_blocks_all_new_inference": True,
        "completed_result_reused_verbatim": True,
        "candidate_specific_tuning": False,
        "automatic_reruns": False,
    }
    assert payload["representation"]["relative_prefix_rewrite"] is False
    assert payload["representation"]["bare_file_mode"] is False
    assert payload["selection_evidence"] is False
    assert v3.calibration_runner_protocol_sha256_v3() == hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def test_v3_runner_candidate_sources_are_exact_frozen_artifacts() -> None:
    sources = v3.candidate_sources_v3()
    assert tuple(sources) == (
        "qwen3-8b-q8",
        "qwen2.5-coder-14b-q5km",
        "devstral-24b-q4km",
        "gpt-oss-20b-mxfp4",
    )
    assert sources["qwen3-8b-q8"]["artifact_sha256"] == (
        "408b955510e196121c1c375201744783b5c9a43c7956d73fc78df54c66e883d6"
    )
    assert sources["qwen2.5-coder-14b-q5km"]["artifact_sha256"] == (
        "98ab25e0132e3f1e6d3554e1b64de2b5021908819b740d9c208430117e49a775"
    )
    assert sources["devstral-24b-q4km"]["artifact_sha256"] == (
        "4a9ec4e1b7fa7b8d3b26e56a54efe251349bb67d8a623bae662353a9d84e4b9b"
    )
    assert sources["gpt-oss-20b-mxfp4"]["artifact_sha256"] == (
        "27cd6c432c7672cb812a92f611cf3ba7bbc35928262bb1e1253ff4ee6ae35901"
    )
    assert sources["qwen3-8b-q8"]["artifact_size_bytes"] == 8_709_518_112
    assert sources["qwen2.5-coder-14b-q5km"]["artifact_size_bytes"] == 10_508_873_152
    assert sources["devstral-24b-q4km"]["artifact_size_bytes"] == 14_333_908_960
    assert sources["gpt-oss-20b-mxfp4"]["artifact_size_bytes"] == 12_109_566_624


def test_v3_pair_ids_bind_candidate_task_and_runner_protocol() -> None:
    task_a, task_b = v3.CALIBRATION_TASK_IDS_V3[:2]
    first = v3._pair_id("qwen3-8b-q8", task_a)
    assert len(first) == 64
    assert first == v3._pair_id("qwen3-8b-q8", task_a)
    assert first != v3._pair_id("qwen3-8b-q8", task_b)
    assert first != v3._pair_id("gpt-oss-20b-mxfp4", task_a)


def test_v3_partial_pair_blocks_all_new_inference(tmp_path) -> None:
    candidate_id = v3.V3_DEVELOPMENT_CANDIDATE_IDS[0]
    task_id = v3.CALIBRATION_TASK_IDS_V3[0]
    pair_root = v3._pair_root(tmp_path, candidate_id, task_id)
    pair_root.mkdir(parents=True)
    (pair_root / "attempt.json").write_text("{}", encoding="ascii")
    with pytest.raises(RuntimeError, match="blocks all new inference"):
        v3._preflight_pair_states(tmp_path, software_revision="1" * 40)


def test_v3_attempt_marker_precedes_inference_and_completed_pair_is_reused(
    tmp_path,
    monkeypatch,
) -> None:
    candidate_id = "qwen3-8b-q8"
    blueprint = repaired_calibration_blueprints_v3()[0]
    software_revision = "1" * 40
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
    pair_root = v3._pair_root(
        artifact_root,
        candidate_id,
        blueprint.task_id,
    )
    calls = 0

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

    monkeypatch.setattr(v3, "_run_raw_attempt", fake_run)
    report, attempted = v3._run_pair_once(
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
        software_revision=software_revision,
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
        raise AssertionError("completed pair attempted a second model call")

    monkeypatch.setattr(v3, "_run_raw_attempt", forbidden_run)
    reused, attempted_again = v3._run_pair_once(
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
        software_revision=software_revision,
        timeout_seconds=17,
        docker_executable="docker",
    )
    assert attempted_again is False
    assert reused["report_sha256"] == report["report_sha256"]
    assert v3._canonical_json_bytes(reused) == v3._canonical_json_bytes(report)
    assert calls == 1


def test_v3_completed_pair_cannot_be_reused_under_different_software_revision(
    tmp_path,
    monkeypatch,
) -> None:
    candidate_id = "qwen3-8b-q8"
    blueprint = repaired_calibration_blueprints_v3()[0]
    artifact_root = tmp_path / "artifacts"
    model_root = tmp_path / "models"
    model_dir = model_root / candidate_id
    model_dir.mkdir(parents=True)
    (model_dir / "model.gguf").write_bytes(b"model")
    store = FileContentStore(tmp_path / "store")
    material = SimpleNamespace(visible_task=SimpleNamespace(sha256="c" * 64))
    source = {
        "candidate_id": candidate_id,
        "filename": "model.gguf",
        "artifact_sha256": "a" * 64,
        "source_identity_sha256": "b" * 64,
    }

    def fake_run(command, *, timeout_seconds):
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

    monkeypatch.setattr(v3, "_run_raw_attempt", fake_run)
    v3._run_pair_once(
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
        software_revision="1" * 40,
        timeout_seconds=17,
        docker_executable="docker",
    )

    def forbidden_run(*args, **kwargs):
        raise AssertionError("drifted completed pair must fail before inference")

    monkeypatch.setattr(v3, "_run_raw_attempt", forbidden_run)
    with pytest.raises(RuntimeError, match="software_revision"):
        v3._run_pair_once(
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
            software_revision="2" * 40,
            timeout_seconds=17,
            docker_executable="docker",
        )
