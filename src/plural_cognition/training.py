"""Deterministic training primitives and atomic checkpoint contracts."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from hashlib import sha256
from math import cos, pi
from pathlib import Path
from typing import Sequence

import torch
from torch import Tensor

from .boolean_world.codec import CausalExample, PAD_ID
from .experiment import OptimizerIntent, ResolvedRunManifest, RunIntent
from .model import PluralDecoder, causal_lm_loss, collate_causal_examples


@dataclass(frozen=True, slots=True)
class TrainingState:
    optimizer_steps: int = 0
    processed_tokens: int = 0
    next_example_index: int = 0

    def __post_init__(self) -> None:
        if min(self.optimizer_steps, self.processed_tokens, self.next_example_index) < 0:
            raise ValueError("training state counters must not be negative")


@dataclass(frozen=True, slots=True)
class OptimizerStepResult:
    mean_loss: float
    learning_rate: float
    gradient_norm: float
    state: TrainingState


@dataclass(frozen=True, slots=True)
class CheckpointRecord:
    path: str
    file_sha256: str
    manifest_sha256: str
    state: TrainingState


def learning_rate_for_tokens(intent: RunIntent, processed_tokens: int) -> float:
    """Token-indexed linear warmup followed by cosine decay."""

    if processed_tokens < 0:
        raise ValueError("processed_tokens must not be negative")
    optimizer = intent.optimizer
    if optimizer.warmup_tokens and processed_tokens < optimizer.warmup_tokens:
        return optimizer.learning_rate * max(
            processed_tokens / optimizer.warmup_tokens,
            1.0 / max(1, optimizer.warmup_tokens),
        )
    remaining = max(1, intent.token_budget - optimizer.warmup_tokens)
    progress = min(
        1.0,
        max(0.0, (processed_tokens - optimizer.warmup_tokens) / remaining),
    )
    cosine = 0.5 * (1.0 + cos(pi * progress))
    ratio = optimizer.minimum_lr_ratio + (
        1.0 - optimizer.minimum_lr_ratio
    ) * cosine
    return optimizer.learning_rate * ratio


def build_optimizer(
    model: PluralDecoder,
    intent: OptimizerIntent,
) -> torch.optim.AdamW:
    return torch.optim.AdamW(
        model.parameters(),
        lr=intent.learning_rate,
        betas=(intent.beta1, intent.beta2),
        weight_decay=intent.weight_decay,
    )


def _fixed_length_batch(
    examples: Sequence[CausalExample],
    sequence_length: int,
) -> tuple[Tensor, Tensor, Tensor]:
    input_ids, attention_mask, label_mask = collate_causal_examples(examples)
    if input_ids.shape[1] > sequence_length:
        raise ValueError("causal example exceeds the fixed training sequence length")
    if input_ids.shape[1] == sequence_length:
        return input_ids, attention_mask, label_mask
    pad = sequence_length - input_ids.shape[1]
    input_ids = torch.nn.functional.pad(input_ids, (0, pad), value=PAD_ID)
    attention_mask = torch.nn.functional.pad(attention_mask, (0, pad), value=False)
    label_mask = torch.nn.functional.pad(label_mask, (0, pad), value=False)
    return input_ids, attention_mask, label_mask


def _autocast_context(device: torch.device, precision: str):
    if precision == "fp32":
        return torch.autocast(device_type=device.type, enabled=False)
    dtype = torch.bfloat16 if precision == "bf16" else torch.float16
    return torch.autocast(device_type=device.type, dtype=dtype, enabled=True)


def optimizer_step(
    model: PluralDecoder,
    optimizer: torch.optim.Optimizer,
    microbatches: Sequence[Sequence[CausalExample]],
    *,
    intent: RunIntent,
    state: TrainingState,
    device: torch.device,
    precision: str = "fp32",
    scaler: torch.amp.GradScaler | None = None,
) -> OptimizerStepResult:
    """Execute one matched-compute optimizer step over fixed-size microbatches."""

    if not microbatches or any(not batch for batch in microbatches):
        raise ValueError("optimizer step requires non-empty microbatches")
    expected_examples = (
        intent.target_tokens_per_optimizer_step // intent.sequence_length
    )
    actual_examples = sum(len(batch) for batch in microbatches)
    if actual_examples != expected_examples:
        raise ValueError(
            f"optimizer step requires {expected_examples} examples, received {actual_examples}"
        )
    if precision not in ("bf16", "fp16", "fp32"):
        raise ValueError("unsupported training precision")
    if precision == "fp16" and device.type != "cuda":
        raise ValueError("fp16 training is restricted to CUDA")

    model.train()
    optimizer.zero_grad(set_to_none=True)
    lr = learning_rate_for_tokens(intent, state.processed_tokens)
    for group in optimizer.param_groups:
        group["lr"] = lr

    use_scaler = precision == "fp16"
    if use_scaler and scaler is None:
        raise ValueError("fp16 training requires a GradScaler")
    losses: list[float] = []
    divisor = len(microbatches)

    for examples in microbatches:
        input_ids, attention_mask, label_mask = _fixed_length_batch(
            examples,
            intent.sequence_length,
        )
        input_ids = input_ids.to(device)
        attention_mask = attention_mask.to(device)
        label_mask = label_mask.to(device)
        with _autocast_context(device, precision):
            logits = model(input_ids, attention_mask)
            raw_loss = causal_lm_loss(logits, input_ids, label_mask)
            loss = raw_loss / divisor
        if not torch.isfinite(raw_loss):
            raise FloatingPointError("non-finite training loss")
        losses.append(float(raw_loss.detach().cpu()))
        if use_scaler:
            assert scaler is not None
            scaler.scale(loss).backward()
        else:
            loss.backward()

    if use_scaler:
        assert scaler is not None
        scaler.unscale_(optimizer)
    gradient_norm_tensor = torch.nn.utils.clip_grad_norm_(
        model.parameters(),
        intent.optimizer.gradient_clip_norm,
        error_if_nonfinite=True,
    )
    if use_scaler:
        assert scaler is not None
        scaler.step(optimizer)
        scaler.update()
    else:
        optimizer.step()

    next_state = TrainingState(
        state.optimizer_steps + 1,
        state.processed_tokens + intent.target_tokens_per_optimizer_step,
        state.next_example_index + actual_examples,
    )
    return OptimizerStepResult(
        sum(losses) / len(losses),
        lr,
        float(gradient_norm_tensor.detach().cpu()),
        next_state,
    )


def _file_sha256(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def save_checkpoint(
    path: str | Path,
    *,
    model: PluralDecoder,
    optimizer: torch.optim.Optimizer,
    manifest: ResolvedRunManifest,
    state: TrainingState,
    scaler: torch.amp.GradScaler | None = None,
) -> CheckpointRecord:
    """Write one atomic resumable checkpoint and return its file digest."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    payload = {
        "schema": "plural-cognition-training-checkpoint-v1",
        "manifest": manifest.canonical_payload(),
        "manifest_sha256": manifest.sha256,
        "state": asdict(state),
        "model_state": model.state_dict(),
        "optimizer_state": optimizer.state_dict(),
        "scaler_state": None if scaler is None else scaler.state_dict(),
        "torch_rng_state": torch.get_rng_state(),
        "cuda_rng_states": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None,
    }
    try:
        with temporary.open("wb") as handle:
            torch.save(payload, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return CheckpointRecord(
        str(destination),
        _file_sha256(destination),
        manifest.sha256,
        state,
    )


def _restore_rng_states(
    torch_rng_state: Tensor,
    cuda_rng_states: Sequence[Tensor] | None,
) -> None:
    """Restore generator states after checkpoint tensors may have been remapped."""

    # torch.set_rng_state and torch.cuda.set_rng_state_all expect CPU ByteTensors.
    # A CUDA map_location is appropriate for model/optimizer tensors but must not
    # leave generator-state tensors resident on CUDA.
    torch.set_rng_state(torch_rng_state.cpu())
    if cuda_rng_states is not None and torch.cuda.is_available():
        torch.cuda.set_rng_state_all(tuple(state.cpu() for state in cuda_rng_states))


def load_checkpoint(
    path: str | Path,
    *,
    model: PluralDecoder,
    optimizer: torch.optim.Optimizer,
    manifest: ResolvedRunManifest,
    scaler: torch.amp.GradScaler | None = None,
    map_location: str | torch.device = "cpu",
) -> TrainingState:
    """Load a checkpoint only when it belongs to the exact resolved run."""

    payload = torch.load(path, map_location=map_location, weights_only=False)
    if payload.get("schema") != "plural-cognition-training-checkpoint-v1":
        raise ValueError("unsupported training checkpoint schema")
    if payload.get("manifest_sha256") != manifest.sha256:
        raise ValueError("checkpoint manifest does not match the requested run")
    if payload.get("manifest") != manifest.canonical_payload():
        raise ValueError("checkpoint manifest payload is inconsistent")
    state = TrainingState(**payload["state"])
    model.load_state_dict(payload["model_state"], strict=True)
    optimizer.load_state_dict(payload["optimizer_state"])
    saved_scaler = payload.get("scaler_state")
    if (saved_scaler is None) != (scaler is None):
        raise ValueError("checkpoint scaler state does not match training precision")
    if scaler is not None:
        scaler.load_state_dict(saved_scaler)
    _restore_rng_states(
        payload["torch_rng_state"],
        payload.get("cuda_rng_states"),
    )
    return state
