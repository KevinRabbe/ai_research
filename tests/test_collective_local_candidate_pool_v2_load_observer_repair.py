from __future__ import annotations

from pathlib import Path

from plural_cognition.collective.local_candidate_pool_v2_load_observer_repair import (
    CHALLENGER_IDS_V2,
    EXPECTED_RECOVERY_PLAN_SHA256,
    FINAL_RECOVERY_PLAN_SHA256,
    ORIGINAL_COMMON_FAILURE,
    ORIGINAL_LOAD_REVISION,
    ORIGINAL_SUITE_FILE_SHA256,
    RECOVERY_LOG_VERBOSITY,
    RecoveryAttemptObservation,
    _classify_attempt,
    _recovery_load_command,
    load_observer_repair_plan_payload_v2,
)
from plural_cognition.collective.local_model_load_preflight import _load_command


def _observation(*, exit_code: int = 0, timed_out: bool = False) -> RecoveryAttemptObservation:
    return RecoveryAttemptObservation(
        command=("llama-cli.exe",),
        exit_code=exit_code,
        timed_out=timed_out,
        elapsed_seconds=1.0,
        stdout_sha256="0" * 64,
        stderr_sha256="1" * 64,
        stdout_bytes=1,
        stderr_bytes=1,
        baseline_gpu_used_mib=100,
        peak_gpu_used_mib=200,
        peak_process_rss_bytes=123,
        monitor_error=None,
    )


def test_observer_repair_plan_identity_and_scientific_boundary() -> None:
    payload = load_observer_repair_plan_payload_v2()
    assert FINAL_RECOVERY_PLAN_SHA256 == EXPECTED_RECOVERY_PLAN_SHA256
    assert tuple(payload["challenger_ids"]) == CHALLENGER_IDS_V2
    invalidated = payload["invalidated_load_qualification"]
    assert invalidated["software_revision"] == ORIGINAL_LOAD_REVISION
    assert invalidated["suite_file_sha256"] == ORIGINAL_SUITE_FILE_SHA256
    assert invalidated["qualified_count"] == 0
    assert invalidated["failed_count"] == 3
    assert invalidated["common_failure"] == ORIGINAL_COMMON_FAILURE
    recovery = payload["recovery_probe"]
    assert recovery["log_verbosity"] == 4
    assert recovery["attempts_per_challenger"] == 1
    policy = payload["evidence_policy"]
    assert policy["original_l2_evidence_immutable"] is True
    assert policy["recovery_artifact_root_must_differ"] is True
    assert policy["raw_stdout_stderr_persisted_before_classification"] is True
    assert policy["selection_evidence"] is False


def test_recovery_command_changes_only_log_verbosity() -> None:
    cli = Path("C:/runtime/llama-cli.exe")
    model = Path("C:/models/model.gguf")
    base = list(_load_command(cli, model, context_tokens=4096, predict_tokens=32))
    repaired = list(_recovery_load_command(cli, model))

    index = repaired.index("--verbosity")
    assert repaired[index + 1] == str(RECOVERY_LOG_VERBOSITY)
    del repaired[index : index + 2]
    assert repaired == base


def test_recovery_command_keeps_formal_hardware_constraints() -> None:
    command = list(
        _recovery_load_command(
            Path("C:/runtime/llama-cli.exe"), Path("C:/models/model.gguf")
        )
    )
    assert command[command.index("-c") + 1] == "4096"
    assert command[command.index("-n") + 1] == "32"
    assert command[command.index("-ngl") + 1] == "all"
    assert command[command.index("-dev") + 1] == "CUDA0"
    assert command[command.index("-fit") + 1] == "off"
    assert command[command.index("-sm") + 1] == "none"
    assert command[command.index("-mg") + 1] == "0"
    assert command[command.index("--verbosity") + 1] == "4"
    assert "--offline" in command


def test_recovery_classifier_accepts_full_offload_trace() -> None:
    stderr = b"llama_model_load: offloaded 25/25 layers to GPU\n"
    status, failure, offloaded, total = _classify_attempt(
        _observation(), stdout=b"running\n", stderr=stderr
    )
    assert status == "LOCAL_MODEL_LOAD_PASS"
    assert failure is None
    assert (offloaded, total) == (25, 25)


def test_recovery_classifier_rejects_partial_offload() -> None:
    stderr = b"llama_model_load: offloaded 24/25 layers to GPU\n"
    status, failure, offloaded, total = _classify_attempt(
        _observation(), stdout=b"running\n", stderr=stderr
    )
    assert status == "LOCAL_MODEL_LOAD_FAIL"
    assert failure == "model was not fully offloaded to GPU: 24/25 layers"
    assert (offloaded, total) == (24, 25)


def test_recovery_classifier_retains_missing_trace_as_failure() -> None:
    status, failure, offloaded, total = _classify_attempt(
        _observation(), stdout=b"running\n", stderr=b"no offload evidence\n"
    )
    assert status == "LOCAL_MODEL_LOAD_FAIL"
    assert failure == "llama-cli trace log did not prove GPU layer offload"
    assert offloaded is None and total is None


def test_recovery_classifier_separates_timeout_exit_and_empty_stdout() -> None:
    timed = _classify_attempt(
        _observation(timed_out=True), stdout=b"partial", stderr=b""
    )
    assert timed[0] == "LOCAL_MODEL_LOAD_FAIL"
    assert "exceeded recovery timeout" in (timed[1] or "")

    failed = _classify_attempt(
        _observation(exit_code=7), stdout=b"partial", stderr=b""
    )
    assert failed[1] == "llama-cli load/generation failed with exit 7"

    empty = _classify_attempt(_observation(), stdout=b"", stderr=b"")
    assert empty[1] == "llama-cli produced no generated stdout"
