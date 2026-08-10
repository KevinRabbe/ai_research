import json

from plural_cognition.manifest_io import read_screening_plan
from plural_cognition.recovery_cli import (
    T30M_CHECKPOINT_TOKENS,
    T30M_EXPERIMENT_NAME,
    T30M_TOKEN_BUDGET,
    resolve_t30m_screening_main,
    t30m_screening_intents,
)


def _preflight_payload():
    geometry = {"PC-29M": 32, "PC-44M": 32, "PC-64M": 16}
    return {
        "schema_version": 1,
        "mode": "cuda_training_preflight",
        "git_commit": "a" * 40,
        "precision": "bf16",
        "hardware": {"gpu_name": "RTX 4060 Ti"},
        "results": [
            {
                "model_name": model,
                "sequence_length": 256,
                "microbatch": microbatch,
                "status": "ok",
                "within_vram_limit": True,
                "tokens_per_second": 1000.0,
            }
            for model, microbatch in geometry.items()
        ],
    }


def test_t30m_intents_extend_training_horizon_only() -> None:
    intents = t30m_screening_intents()

    assert len(intents) == 6
    assert {intent.model_name for intent in intents} == {"PC-29M", "PC-44M", "PC-64M"}
    assert {intent.initialization_seed for intent in intents} == {101, 102}
    assert all(intent.experiment_name == T30M_EXPERIMENT_NAME for intent in intents)
    assert all(intent.token_budget == T30M_TOKEN_BUDGET for intent in intents)
    assert all(intent.checkpoint_tokens == T30M_CHECKPOINT_TOKENS for intent in intents)
    assert all(intent.sequence_length == 256 for intent in intents)
    assert all(intent.target_tokens_per_optimizer_step == 32_768 for intent in intents)
    assert all(intent.validation_examples == 512 for intent in intents)
    assert all(intent.data_seed == 20260806 for intent in intents)
    assert all(intent.optimizer.learning_rate == 3e-4 for intent in intents)


def test_resolve_t30m_screening_preserves_measured_geometry(tmp_path) -> None:
    preflight = tmp_path / "preflight.json"
    preflight.write_text(json.dumps(_preflight_payload()), encoding="utf-8")
    output = tmp_path / "screening-plan.json"

    assert resolve_t30m_screening_main(
        ("--preflight", str(preflight), "--output", str(output))
    ) == 0

    runs = read_screening_plan(output)
    assert len(runs) == 6
    assert all(run.intent.token_budget == 30_000_000 for run in runs)
    assert all(run.optimizer_steps == 916 for run in runs)
    assert all(run.required_training_examples == 117_248 for run in runs)
    assert {
        run.intent.model_name: (
            run.microbatch_examples,
            run.gradient_accumulation_steps,
        )
        for run in runs
    } == {
        "PC-29M": (32, 4),
        "PC-44M": (32, 4),
        "PC-64M": (16, 8),
    }
