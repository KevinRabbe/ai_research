from dataclasses import dataclass

import pytest
import torch

from plural_cognition.boolean_world.codec import CausalExample
from plural_cognition.experiment import OptimizerIntent, RunIntent, resolve_run_intent
from plural_cognition.model import DecoderConfig, PluralDecoder
from plural_cognition.training import (
    TrainingState,
    build_optimizer,
    learning_rate_for_tokens,
    load_checkpoint,
    optimizer_step,
    save_checkpoint,
)


@dataclass(frozen=True)
class _SmokeIntent:
    sequence_length: int = 8
    target_tokens_per_optimizer_step: int = 16
    token_budget: int = 64
    optimizer: OptimizerIntent = OptimizerIntent(
        learning_rate=1e-3,
        warmup_tokens=16,
        weight_decay=0.0,
    )


def _example() -> CausalExample:
    return CausalExample(
        token_ids=(1, 2, 3, 4),
        label_mask=(False, False, True, True),
        answer_start=1,
    )


def test_token_scheduler_warms_up_and_decays() -> None:
    intent = RunIntent("screen", "PC-4M", 1, 2)

    start = learning_rate_for_tokens(intent, 0)
    warm = learning_rate_for_tokens(intent, intent.optimizer.warmup_tokens)
    end = learning_rate_for_tokens(intent, intent.token_budget)

    assert 0 < start < warm
    assert warm == pytest.approx(intent.optimizer.learning_rate)
    assert end == pytest.approx(
        intent.optimizer.learning_rate * intent.optimizer.minimum_lr_ratio
    )


def test_cpu_optimizer_step_is_finite_and_advances_exact_counters() -> None:
    torch.manual_seed(7)
    model = PluralDecoder(DecoderConfig("SMOKE", 1, 64, 1, max_seq_len=8))
    optimizer = build_optimizer(model, _SmokeIntent().optimizer)
    result = optimizer_step(
        model,
        optimizer,
        ((_example(),), (_example(),)),
        intent=_SmokeIntent(),
        state=TrainingState(),
        device=torch.device("cpu"),
        precision="fp32",
    )

    assert result.mean_loss > 0
    assert result.gradient_norm >= 0
    assert result.state == TrainingState(1, 16, 2)
    assert optimizer.param_groups[0]["lr"] == result.learning_rate


def test_optimizer_step_rejects_unmatched_compute_geometry() -> None:
    model = PluralDecoder(DecoderConfig("SMOKE", 1, 64, 1, max_seq_len=8))
    optimizer = build_optimizer(model, _SmokeIntent().optimizer)

    with pytest.raises(ValueError, match="requires 2 examples"):
        optimizer_step(
            model,
            optimizer,
            ((_example(),),),
            intent=_SmokeIntent(),
            state=TrainingState(),
            device=torch.device("cpu"),
        )


def test_checkpoint_round_trip_restores_model_optimizer_and_state(tmp_path) -> None:
    intent = RunIntent("screen", "PC-4M", 1, 2)
    manifest = resolve_run_intent(
        intent,
        git_commit="a" * 40,
        precision="fp32",
        microbatch_examples=128,
        device_name="CPU qualification",
        preflight_sha256="b" * 64,
    )
    torch.manual_seed(11)
    model = PluralDecoder(intent.model_config)
    optimizer = build_optimizer(model, intent.optimizer)
    state = TrainingState(3, 98_304, 384)
    path = tmp_path / "checkpoint.pt"
    record = save_checkpoint(
        path,
        model=model,
        optimizer=optimizer,
        manifest=manifest,
        state=state,
    )

    original = {name: value.detach().clone() for name, value in model.state_dict().items()}
    with torch.no_grad():
        next(model.parameters()).add_(1.0)
    restored = load_checkpoint(
        path,
        model=model,
        optimizer=optimizer,
        manifest=manifest,
    )

    assert restored == state
    assert record.state == state
    assert len(record.file_sha256) == 64
    assert all(torch.equal(model.state_dict()[name], value) for name, value in original.items())


def test_checkpoint_rejects_different_resolved_manifest(tmp_path) -> None:
    first_intent = RunIntent("screen", "PC-4M", 1, 2)
    second_intent = RunIntent("screen", "PC-4M", 2, 2)

    def resolved(intent):
        return resolve_run_intent(
            intent,
            git_commit="a" * 40,
            precision="fp32",
            microbatch_examples=128,
            device_name="CPU qualification",
            preflight_sha256="b" * 64,
        )

    model = PluralDecoder(first_intent.model_config)
    optimizer = build_optimizer(model, first_intent.optimizer)
    path = tmp_path / "checkpoint.pt"
    save_checkpoint(
        path,
        model=model,
        optimizer=optimizer,
        manifest=resolved(first_intent),
        state=TrainingState(),
    )

    with pytest.raises(ValueError, match="manifest"):
        load_checkpoint(
            path,
            model=model,
            optimizer=optimizer,
            manifest=resolved(second_intent),
        )
