"""Immutable experiment intents and target-machine run manifests."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from math import isfinite
from typing import Literal

from .model import (
    MODEL_CONFIGS,
    V1_1_MODEL_CONFIGS,
    V1_2_MODEL_CONFIGS,
    DecoderConfig,
    expected_parameter_count,
)

Precision = Literal["bf16", "fp16", "fp32"]
_MODEL_BY_NAME = {config.name: config for config in MODEL_CONFIGS}
_VALID_PRECISIONS = ("bf16", "fp16", "fp32")
SCREENING_PROTOCOL_MODELS = {
    "v1.1": V1_1_MODEL_CONFIGS,
    "v1.2": V1_2_MODEL_CONFIGS,
}


@dataclass(frozen=True, slots=True)
class OptimizerIntent:
    learning_rate: float = 3e-4
    beta1: float = 0.9
    beta2: float = 0.95
    weight_decay: float = 0.1
    gradient_clip_norm: float = 1.0
    warmup_tokens: int = 500_000
    minimum_lr_ratio: float = 0.1

    def __post_init__(self) -> None:
        for name in (
            "learning_rate",
            "beta1",
            "beta2",
            "weight_decay",
            "gradient_clip_norm",
            "minimum_lr_ratio",
        ):
            value = float(getattr(self, name))
            if not isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate must be positive")
        if not 0 <= self.beta1 < 1 or not 0 <= self.beta2 < 1:
            raise ValueError("optimizer betas must be in [0, 1)")
        if self.weight_decay < 0 or self.gradient_clip_norm <= 0:
            raise ValueError("weight decay must be non-negative and clipping positive")
        if self.warmup_tokens < 0:
            raise ValueError("warmup_tokens must not be negative")
        if not 0 < self.minimum_lr_ratio <= 1:
            raise ValueError("minimum_lr_ratio must be in (0, 1]")


@dataclass(frozen=True, slots=True)
class RunIntent:
    experiment_name: str
    model_name: str
    initialization_seed: int
    data_seed: int
    token_budget: int = 10_000_000
    sequence_length: int = 256
    target_tokens_per_optimizer_step: int = 32_768
    validation_examples: int = 512
    checkpoint_tokens: tuple[int, ...] = (1_000_000, 2_000_000, 5_000_000, 10_000_000)
    optimizer: OptimizerIntent = OptimizerIntent()

    def __post_init__(self) -> None:
        if not self.experiment_name:
            raise ValueError("experiment_name must not be empty")
        if self.model_name not in _MODEL_BY_NAME:
            raise ValueError(f"unknown model configuration: {self.model_name!r}")
        if type(self.initialization_seed) is not int or type(self.data_seed) is not int:
            raise TypeError("run seeds must be int")
        if self.token_budget < 1 or self.sequence_length < 2:
            raise ValueError("token_budget and sequence_length must be positive")
        if self.sequence_length != _MODEL_BY_NAME[self.model_name].max_seq_len:
            raise ValueError("sequence_length must match the qualified model configuration")
        if self.target_tokens_per_optimizer_step < self.sequence_length:
            raise ValueError("target token batch must contain at least one sequence")
        if self.target_tokens_per_optimizer_step % self.sequence_length:
            raise ValueError("target token batch must be divisible by sequence_length")
        if self.validation_examples < 1:
            raise ValueError("validation_examples must be positive")
        if not self.checkpoint_tokens:
            raise ValueError("at least one checkpoint token must be configured")
        if tuple(sorted(set(self.checkpoint_tokens))) != self.checkpoint_tokens:
            raise ValueError("checkpoint_tokens must be sorted and unique")
        if self.checkpoint_tokens[-1] != self.token_budget:
            raise ValueError("final checkpoint must equal token_budget")
        if self.checkpoint_tokens[0] < 1:
            raise ValueError("checkpoint token values must be positive")

    @property
    def model_config(self) -> DecoderConfig:
        return _MODEL_BY_NAME[self.model_name]

    def canonical_payload(self) -> dict:
        model = self.model_config
        return {
            "schema": "plural-cognition-run-intent-v1",
            "experiment_name": self.experiment_name,
            "model": {
                "name": model.name,
                "layers": model.layers,
                "d_model": model.d_model,
                "heads": model.heads,
                "head_dim": model.head_dim,
                "ffn_dim": model.ffn_dim,
                "max_seq_len": model.max_seq_len,
                "vocab_size": model.vocab_size,
                "parameter_count": expected_parameter_count(model),
            },
            "initialization_seed": self.initialization_seed,
            "data_seed": self.data_seed,
            "token_budget": self.token_budget,
            "sequence_length": self.sequence_length,
            "target_tokens_per_optimizer_step": self.target_tokens_per_optimizer_step,
            "validation_examples": self.validation_examples,
            "checkpoint_tokens": list(self.checkpoint_tokens),
            "optimizer": asdict(self.optimizer),
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()

    @property
    def run_id(self) -> str:
        return f"{self.experiment_name}-{self.model_name.lower()}-{self.sha256[:16]}"


@dataclass(frozen=True, slots=True)
class ResolvedRunManifest:
    intent: RunIntent
    git_commit: str
    precision: Precision
    microbatch_examples: int
    gradient_accumulation_steps: int
    effective_tokens_per_optimizer_step: int
    device_name: str
    preflight_sha256: str

    def __post_init__(self) -> None:
        if len(self.git_commit) != 40:
            raise ValueError("git_commit must be a full 40-character SHA")
        try:
            int(self.git_commit, 16)
        except ValueError as exc:
            raise ValueError("git_commit must be hexadecimal") from exc
        if self.git_commit != self.git_commit.lower():
            raise ValueError("git_commit must use lowercase hexadecimal")
        if self.precision not in _VALID_PRECISIONS:
            raise ValueError(f"unsupported precision: {self.precision!r}")
        if self.microbatch_examples < 1 or self.gradient_accumulation_steps < 1:
            raise ValueError("microbatch and accumulation must be positive")
        expected = (
            self.microbatch_examples
            * self.intent.sequence_length
            * self.gradient_accumulation_steps
        )
        if expected != self.effective_tokens_per_optimizer_step:
            raise ValueError("effective token batch does not match resolved geometry")
        if expected != self.intent.target_tokens_per_optimizer_step:
            raise ValueError("resolved token batch must exactly match the run intent")
        if not self.device_name:
            raise ValueError("device_name must not be empty")
        if len(self.preflight_sha256) != 64:
            raise ValueError("preflight_sha256 must contain 64 hexadecimal characters")
        try:
            int(self.preflight_sha256, 16)
        except ValueError as exc:
            raise ValueError("preflight_sha256 must be hexadecimal") from exc

    def canonical_payload(self) -> dict:
        return {
            "schema": "plural-cognition-resolved-run-v1",
            "intent": self.intent.canonical_payload(),
            "intent_sha256": self.intent.sha256,
            "run_id": self.intent.run_id,
            "git_commit": self.git_commit,
            "precision": self.precision,
            "microbatch_examples": self.microbatch_examples,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "effective_tokens_per_optimizer_step": self.effective_tokens_per_optimizer_step,
            "device_name": self.device_name,
            "preflight_sha256": self.preflight_sha256,
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


def resolve_run_intent(
    intent: RunIntent,
    *,
    git_commit: str,
    precision: Precision,
    microbatch_examples: int,
    device_name: str,
    preflight_sha256: str,
) -> ResolvedRunManifest:
    tokens_per_microbatch = microbatch_examples * intent.sequence_length
    if tokens_per_microbatch > intent.target_tokens_per_optimizer_step:
        raise ValueError(
            "microbatch exceeds the matched target token batch; choose a smaller qualified microbatch"
        )
    if intent.target_tokens_per_optimizer_step % tokens_per_microbatch:
        raise ValueError(
            "microbatch does not divide the matched target token batch exactly"
        )
    accumulation = intent.target_tokens_per_optimizer_step // tokens_per_microbatch
    return ResolvedRunManifest(
        intent,
        git_commit,
        precision,
        microbatch_examples,
        accumulation,
        intent.target_tokens_per_optimizer_step,
        device_name,
        preflight_sha256,
    )


def default_screening_plan(
    *,
    initialization_seeds: tuple[int, ...] = (101, 102),
    data_seed: int = 20260806,
    protocol: str = "v1.1",
) -> tuple[RunIntent, ...]:
    """Return a frozen 3-scale × 2-seed, 10M-token screening matrix."""

    if not initialization_seeds or len(initialization_seeds) != len(set(initialization_seeds)):
        raise ValueError("initialization_seeds must be non-empty and unique")
    try:
        models = SCREENING_PROTOCOL_MODELS[protocol]
    except KeyError as exc:
        raise ValueError(f"unknown screening protocol: {protocol!r}") from exc
    return tuple(
        RunIntent(
            f"{protocol}-screen",
            model.name,
            initialization_seed,
            data_seed,
        )
        for model in models
        for initialization_seed in initialization_seeds
    )
