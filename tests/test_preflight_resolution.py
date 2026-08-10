import json

import pytest

from plural_cognition.preflight_resolution import (
    PreflightResolutionError,
    resolve_screening_plan_from_preflight,
)


def _report(models=("PC-4M", "PC-10M", "PC-18M")):
    results = []
    for model in models:
        results.extend(
            (
                {
                    "model_name": model,
                    "sequence_length": 256,
                    "microbatch": 32,
                    "status": "ok",
                    "within_vram_limit": True,
                    "tokens_per_second": 1000.0,
                },
                {
                    "model_name": model,
                    "sequence_length": 256,
                    "microbatch": 64,
                    "status": "ok",
                    "within_vram_limit": True,
                    "tokens_per_second": 1500.0,
                },
                {
                    "model_name": model,
                    "sequence_length": 256,
                    "microbatch": 128,
                    "status": "ok",
                    "within_vram_limit": True,
                    "tokens_per_second": 1400.0,
                },
                {
                    "model_name": model,
                    "sequence_length": 256,
                    "microbatch": 256,
                    "status": "ok",
                    "within_vram_limit": True,
                    "tokens_per_second": 9999.0,
                },
            )
        )
    return {
        "schema_version": 1,
        "mode": "cuda_training_preflight",
        "git_commit": "a" * 40,
        "precision": "bf16",
        "hardware": {"gpu_name": "RTX 4060 Ti"},
        "results": results,
    }


def test_resolution_selects_fastest_case_that_preserves_matched_batch(tmp_path) -> None:
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(_report()), encoding="utf-8")

    runs = resolve_screening_plan_from_preflight(path)

    assert len(runs) == 6
    assert {run.intent.model_name for run in runs} == {"PC-4M", "PC-10M", "PC-18M"}
    assert all(run.microbatch_examples == 64 for run in runs)
    assert all(run.gradient_accumulation_steps == 2 for run in runs)
    assert all(run.effective_tokens_per_optimizer_step == 32_768 for run in runs)
    assert all(run.device_name == "RTX 4060 Ti" for run in runs)
    assert all(run.git_commit == "a" * 40 for run in runs)
    assert len({run.intent.sha256 for run in runs}) == 6


def test_v12_resolution_uses_only_recovery_scales(tmp_path) -> None:
    models = ("PC-29M", "PC-44M", "PC-64M")
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(_report(models)), encoding="utf-8")

    runs = resolve_screening_plan_from_preflight(path, protocol="v1.2")

    assert len(runs) == 6
    assert {run.intent.model_name for run in runs} == set(models)
    assert all(run.intent.experiment_name == "v1.2-screen" for run in runs)
    assert all(run.microbatch_examples == 64 for run in runs)
    assert all(run.gradient_accumulation_steps == 2 for run in runs)


def test_resolution_rejects_report_without_usable_model_case(tmp_path) -> None:
    report = _report()
    report["results"] = [
        item
        for item in report["results"]
        if item["model_name"] != "PC-18M"
    ]
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(PreflightResolutionError, match="PC-18M"):
        resolve_screening_plan_from_preflight(path)


def test_resolution_rejects_unknown_commit(tmp_path) -> None:
    report = _report()
    report["git_commit"] = "unknown"
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(PreflightResolutionError, match="full Git commit"):
        resolve_screening_plan_from_preflight(path)
