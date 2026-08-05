"""Small decoder-only transformer family for the Version 1 learning preflight."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Sequence

import torch
from torch import Tensor, nn
from torch.nn import functional as F

from .boolean_world.codec import CausalExample, PAD_ID, VOCAB_SIZE


@dataclass(frozen=True, slots=True)
class DecoderConfig:
    name: str
    layers: int
    d_model: int
    heads: int
    max_seq_len: int = 256
    vocab_size: int = VOCAB_SIZE
    ffn_multiplier: int = 4
    rms_norm_eps: float = 1e-6
    dropout: float = 0.0

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("model name must not be empty")
        if self.layers < 1:
            raise ValueError("layers must be positive")
        if self.d_model < 1 or self.heads < 1:
            raise ValueError("d_model and heads must be positive")
        if self.d_model % self.heads != 0:
            raise ValueError("d_model must be divisible by heads")
        if self.head_dim != 64:
            raise ValueError("Version 1 configurations require head dimension 64")
        if self.max_seq_len < 2:
            raise ValueError("max_seq_len must be at least 2")
        if self.vocab_size != VOCAB_SIZE:
            raise ValueError(
                f"vocab_size must match the qualified codec ({VOCAB_SIZE})"
            )
        if self.ffn_multiplier != 4:
            raise ValueError(
                "Version 1 scale comparison fixes ffn_multiplier at 4"
            )
        if self.rms_norm_eps <= 0:
            raise ValueError("rms_norm_eps must be positive")
        if not 0.0 <= self.dropout < 1.0:
            raise ValueError("dropout must be in [0, 1)")

    @property
    def head_dim(self) -> int:
        return self.d_model // self.heads

    @property
    def ffn_dim(self) -> int:
        return self.ffn_multiplier * self.d_model


PC_4M = DecoderConfig("PC-4M", layers=6, d_model=256, heads=4)
PC_10M = DecoderConfig("PC-10M", layers=8, d_model=320, heads=5)
PC_18M = DecoderConfig("PC-18M", layers=10, d_model=384, heads=6)
MODEL_CONFIGS = (PC_4M, PC_10M, PC_18M)


def expected_parameter_count(config: DecoderConfig) -> int:
    """Return the exact count for the fixed Version 1 decoder family."""

    d = config.d_model
    return (
        config.layers * (12 * d * d + 2 * d)
        + config.vocab_size * d
        + d
    )


class RMSNorm(nn.Module):
    def __init__(self, width: int, eps: float) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.ones(width))
        self.eps = eps

    def forward(self, inputs: Tensor) -> Tensor:
        float_inputs = inputs.float()
        normalized = float_inputs * torch.rsqrt(
            float_inputs.pow(2).mean(dim=-1, keepdim=True) + self.eps
        )
        return (normalized * self.weight.float()).to(dtype=inputs.dtype)


def _rotary_frequencies(
    sequence_length: int,
    head_dim: int,
    *,
    device: torch.device,
) -> tuple[Tensor, Tensor]:
    if head_dim % 2 != 0:
        raise ValueError("rotary head dimension must be even")
    positions = torch.arange(
        sequence_length,
        device=device,
        dtype=torch.float32,
    )
    inverse = 1.0 / (
        10000.0
        ** (
            torch.arange(
                0,
                head_dim,
                2,
                device=device,
                dtype=torch.float32,
            )
            / head_dim
        )
    )
    angles = torch.outer(positions, inverse)
    return angles.cos(), angles.sin()


def _apply_rotary(inputs: Tensor, cosine: Tensor, sine: Tensor) -> Tensor:
    # inputs: [batch, heads, sequence, head_dim]
    even = inputs[..., 0::2]
    odd = inputs[..., 1::2]
    cosine = cosine[None, None, :, :].to(dtype=inputs.dtype)
    sine = sine[None, None, :, :].to(dtype=inputs.dtype)
    rotated_even = even * cosine - odd * sine
    rotated_odd = even * sine + odd * cosine
    return torch.stack((rotated_even, rotated_odd), dim=-1).flatten(-2)


class CausalSelfAttention(nn.Module):
    def __init__(self, config: DecoderConfig) -> None:
        super().__init__()
        self.heads = config.heads
        self.head_dim = config.head_dim
        self.dropout = config.dropout
        self.qkv = nn.Linear(
            config.d_model,
            3 * config.d_model,
            bias=False,
        )
        self.output = nn.Linear(
            config.d_model,
            config.d_model,
            bias=False,
        )

    def forward(
        self,
        inputs: Tensor,
        cosine: Tensor,
        sine: Tensor,
        allowed_attention: Tensor | None,
        query_mask: Tensor | None,
    ) -> Tensor:
        batch, sequence_length, width = inputs.shape
        query, key, value = self.qkv(inputs).chunk(3, dim=-1)

        def split_heads(tensor: Tensor) -> Tensor:
            return tensor.view(
                batch,
                sequence_length,
                self.heads,
                self.head_dim,
            ).transpose(1, 2)

        query = _apply_rotary(split_heads(query), cosine, sine)
        key = _apply_rotary(split_heads(key), cosine, sine)
        value = split_heads(value)
        dropout_p = self.dropout if self.training else 0.0

        attended = F.scaled_dot_product_attention(
            query,
            key,
            value,
            attn_mask=allowed_attention,
            dropout_p=dropout_p,
            is_causal=allowed_attention is None,
        )
        if query_mask is not None:
            attended = attended * query_mask[:, None, :, None]

        merged = attended.transpose(1, 2).contiguous().view(
            batch,
            sequence_length,
            width,
        )
        return self.output(merged)


class FeedForward(nn.Module):
    def __init__(self, config: DecoderConfig) -> None:
        super().__init__()
        self.up = nn.Linear(
            config.d_model,
            config.ffn_dim,
            bias=False,
        )
        self.down = nn.Linear(
            config.ffn_dim,
            config.d_model,
            bias=False,
        )

    def forward(self, inputs: Tensor) -> Tensor:
        return self.down(F.gelu(self.up(inputs), approximate="tanh"))


class DecoderBlock(nn.Module):
    def __init__(self, config: DecoderConfig) -> None:
        super().__init__()
        self.attention_norm = RMSNorm(
            config.d_model,
            config.rms_norm_eps,
        )
        self.attention = CausalSelfAttention(config)
        self.ffn_norm = RMSNorm(
            config.d_model,
            config.rms_norm_eps,
        )
        self.feed_forward = FeedForward(config)
        self.dropout = config.dropout

    def forward(
        self,
        inputs: Tensor,
        cosine: Tensor,
        sine: Tensor,
        allowed_attention: Tensor | None,
        query_mask: Tensor | None,
    ) -> Tensor:
        inputs = inputs + F.dropout(
            self.attention(
                self.attention_norm(inputs),
                cosine,
                sine,
                allowed_attention,
                query_mask,
            ),
            p=self.dropout,
            training=self.training,
        )
        return inputs + F.dropout(
            self.feed_forward(self.ffn_norm(inputs)),
            p=self.dropout,
            training=self.training,
        )


class PluralDecoder(nn.Module):
    """Decoder-only model with tied token/output embeddings."""

    def __init__(self, config: DecoderConfig) -> None:
        super().__init__()
        self.config = config
        self.token_embedding = nn.Embedding(
            config.vocab_size,
            config.d_model,
        )
        self.blocks = nn.ModuleList(
            DecoderBlock(config) for _ in range(config.layers)
        )
        self.final_norm = RMSNorm(
            config.d_model,
            config.rms_norm_eps,
        )

        cosine, sine = _rotary_frequencies(
            config.max_seq_len,
            config.head_dim,
            device=torch.device("cpu"),
        )
        self.register_buffer("rotary_cosine", cosine, persistent=False)
        self.register_buffer("rotary_sine", sine, persistent=False)
        self.register_buffer(
            "causal_mask",
            torch.ones(
                config.max_seq_len,
                config.max_seq_len,
                dtype=torch.bool,
            ).tril(),
            persistent=False,
        )
        self.reset_parameters()

        actual = self.parameter_count()
        expected = expected_parameter_count(config)
        if actual != expected:
            raise AssertionError(
                f"parameter contract mismatch for {config.name}: "
                f"actual={actual}, expected={expected}"
            )

    def reset_parameters(self) -> None:
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.normal_(module.weight, mean=0.0, std=0.02)
            elif isinstance(module, nn.Embedding):
                nn.init.normal_(module.weight, mean=0.0, std=0.02)
            elif isinstance(module, RMSNorm):
                nn.init.ones_(module.weight)

        residual_std = 0.02 / sqrt(2 * self.config.layers)
        for block in self.blocks:
            nn.init.normal_(
                block.attention.output.weight,
                mean=0.0,
                std=residual_std,
            )
            nn.init.normal_(
                block.feed_forward.down.weight,
                mean=0.0,
                std=residual_std,
            )

    def parameter_count(self) -> int:
        return sum(
            parameter.numel() for parameter in self.parameters()
        )

    def _validate_inputs(
        self,
        input_ids: Tensor,
        attention_mask: Tensor | None,
    ) -> None:
        if input_ids.ndim != 2:
            raise ValueError("input_ids must have shape [batch, sequence]")
        if input_ids.dtype != torch.long:
            raise TypeError("input_ids must use torch.long")
        if input_ids.shape[1] > self.config.max_seq_len:
            raise ValueError("input sequence exceeds configured maximum")

        if attention_mask is not None:
            if attention_mask.shape != input_ids.shape:
                raise ValueError(
                    "attention_mask must match input_ids shape"
                )
            if attention_mask.dtype != torch.bool:
                raise TypeError("attention_mask must use torch.bool")

    def forward(
        self,
        input_ids: Tensor,
        attention_mask: Tensor | None = None,
    ) -> Tensor:
        self._validate_inputs(input_ids, attention_mask)
        sequence_length = input_ids.shape[1]
        hidden = self.token_embedding(input_ids)
        cosine = self.rotary_cosine[:sequence_length]
        sine = self.rotary_sine[:sequence_length]

        allowed_attention = None
        if attention_mask is not None:
            allowed_attention = (
                self.causal_mask[:sequence_length, :sequence_length][
                    None,
                    None,
                    :,
                    :,
                ]
                & attention_mask[:, None, None, :]
            )

        for block in self.blocks:
            hidden = block(
                hidden,
                cosine,
                sine,
                allowed_attention,
                attention_mask,
            )

        hidden = self.final_norm(hidden)
        return F.linear(hidden, self.token_embedding.weight)


def causal_lm_loss(
    logits: Tensor,
    input_ids: Tensor,
    label_mask: Tensor,
) -> Tensor:
    """Return cross entropy over answer tokens only."""

    if logits.ndim != 3:
        raise ValueError(
            "logits must have shape [batch, sequence, vocabulary]"
        )
    if input_ids.shape != logits.shape[:2]:
        raise ValueError(
            "input_ids must match logits batch and sequence axes"
        )
    if label_mask.shape != input_ids.shape:
        raise ValueError("label_mask must match input_ids shape")
    if input_ids.dtype != torch.long:
        raise TypeError("input_ids must use torch.long")
    if label_mask.dtype != torch.bool:
        raise TypeError("label_mask must use torch.bool")

    shifted_logits = logits[:, :-1, :].contiguous()
    shifted_targets = input_ids[:, 1:].contiguous()
    shifted_mask = label_mask[:, 1:].contiguous()

    losses = F.cross_entropy(
        shifted_logits.view(-1, shifted_logits.shape[-1]),
        shifted_targets.view(-1),
        reduction="none",
    ).view_as(shifted_targets)
    return losses.masked_select(shifted_mask).mean()


def collate_causal_examples(
    examples: Sequence[CausalExample],
    *,
    pad_id: int = PAD_ID,
) -> tuple[Tensor, Tensor, Tensor]:
    """Pad examples into input, attention, and label-mask tensors."""

    if not examples:
        raise ValueError("at least one causal example is required")
    if type(pad_id) is not int or not 0 <= pad_id < VOCAB_SIZE:
        raise ValueError("pad_id must be a valid symbolic token ID")
    if any(not any(example.label_mask) for example in examples):
        raise ValueError(
            "every causal example must score at least one answer token"
        )

    maximum = max(len(example.token_ids) for example in examples)
    input_ids = torch.full(
        (len(examples), maximum),
        pad_id,
        dtype=torch.long,
    )
    attention_mask = torch.zeros(
        (len(examples), maximum),
        dtype=torch.bool,
    )
    label_mask = torch.zeros(
        (len(examples), maximum),
        dtype=torch.bool,
    )

    for row, example in enumerate(examples):
        length = len(example.token_ids)
        input_ids[row, :length] = torch.tensor(
            example.token_ids,
            dtype=torch.long,
        )
        attention_mask[row, :length] = True
        label_mask[row, :length] = torch.tensor(
            example.label_mask,
            dtype=torch.bool,
        )

    return input_ids, attention_mask, label_mask
