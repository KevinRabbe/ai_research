"""Strict symbolic generation and hidden exact checkpoint evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Sequence

import torch
from torch import Tensor, nn

from .boolean_world.ast import Expr
from .boolean_world.codec import (
    BOS_ID,
    EOS_ID,
    CodecError,
    decode_mechanism,
    encode_public_task,
    encode_tokens,
)
from .boolean_world.qualification import HiddenEvaluation, QualificationTask
from .boolean_world.world import PublicTask

ANSWER_ID = encode_tokens(("<ANSWER>",))[0]


@dataclass(frozen=True, slots=True)
class GenerationResult:
    valid: bool
    expression: Expr | None
    generated_token_ids: tuple[int, ...]
    error: str | None = None


@dataclass(frozen=True, slots=True)
class EvaluatedGeneration:
    task_id: str
    generation: GenerationResult
    hidden: HiddenEvaluation | None


@dataclass(frozen=True, slots=True)
class CheckpointEvaluation:
    cases: tuple[EvaluatedGeneration, ...]
    parse_rate: float
    exact_accuracy: float
    visible_consistency_rate: float
    mean_semantic_accuracy: float
    mean_hidden_accuracy: float


def encode_inference_prompt(task: PublicTask) -> tuple[int, ...]:
    """Return the model-visible task followed by one answer boundary token."""

    encoded = encode_public_task(task)
    if encoded[-1] != EOS_ID:
        raise AssertionError("public task codec no longer ends with EOS")
    return (*encoded[:-1], ANSWER_ID)


def _decode_generated(
    generated: list[int],
    task: PublicTask,
    max_new_tokens: int,
) -> GenerationResult:
    if not generated or generated[-1] != EOS_ID:
        return GenerationResult(
            False,
            None,
            tuple(generated),
            "generation did not terminate with EOS",
        )
    try:
        expression = decode_mechanism(
            (BOS_ID, ANSWER_ID, *generated),
            allowed_variables=task.variable_order,
            max_tokens=max_new_tokens + 2,
        )
    except CodecError as exc:
        return GenerationResult(False, None, tuple(generated), str(exc))
    return GenerationResult(True, expression, tuple(generated))


def greedy_generate_mechanism(
    model: nn.Module,
    task: PublicTask,
    *,
    device: torch.device,
    max_new_tokens: int = 64,
) -> GenerationResult:
    """Generate one deterministic canonical mechanism or return a parse failure."""

    if max_new_tokens < 1:
        raise ValueError("max_new_tokens must be positive")
    prompt = encode_inference_prompt(task)
    configured_max = getattr(getattr(model, "config", None), "max_seq_len", None)
    if configured_max is None:
        raise ValueError("model must expose config.max_seq_len")
    if len(prompt) >= configured_max:
        return GenerationResult(False, None, (), "prompt leaves no answer capacity")

    input_ids = torch.tensor((prompt,), dtype=torch.long, device=device)
    attention_mask = torch.ones_like(input_ids, dtype=torch.bool)
    generated: list[int] = []
    model.eval()

    with torch.inference_mode():
        for _ in range(max_new_tokens):
            if input_ids.shape[1] >= configured_max:
                return GenerationResult(
                    False,
                    None,
                    tuple(generated),
                    "generation reached model context limit before EOS",
                )
            logits: Tensor = model(input_ids, attention_mask)
            if logits.ndim != 3 or logits.shape[:2] != input_ids.shape:
                raise ValueError("model returned logits with an invalid shape")
            next_token = int(torch.argmax(logits[0, -1]).item())
            generated.append(next_token)
            next_tensor = torch.tensor(((next_token,),), dtype=torch.long, device=device)
            input_ids = torch.cat((input_ids, next_tensor), dim=1)
            attention_mask = torch.cat(
                (
                    attention_mask,
                    torch.ones((1, 1), dtype=torch.bool, device=device),
                ),
                dim=1,
            )
            if next_token == EOS_ID:
                break
    return _decode_generated(generated, task, max_new_tokens)


def sample_generate_mechanism(
    model: nn.Module,
    task: PublicTask,
    *,
    device: torch.device,
    seed: int,
    temperature: float = 1.0,
    top_k: int | None = None,
    max_new_tokens: int = 64,
) -> GenerationResult:
    """Sample one reproducible symbolic path for same-weight and extra-sampling controls."""

    if max_new_tokens < 1:
        raise ValueError("max_new_tokens must be positive")
    if temperature <= 0.0 or not torch.isfinite(torch.tensor(temperature)):
        raise ValueError("temperature must be finite and positive")
    if top_k is not None and top_k < 1:
        raise ValueError("top_k must be positive when supplied")
    prompt = encode_inference_prompt(task)
    configured_max = getattr(getattr(model, "config", None), "max_seq_len", None)
    if configured_max is None:
        raise ValueError("model must expose config.max_seq_len")
    if len(prompt) >= configured_max:
        return GenerationResult(False, None, (), "prompt leaves no answer capacity")

    input_ids = torch.tensor((prompt,), dtype=torch.long, device=device)
    attention_mask = torch.ones_like(input_ids, dtype=torch.bool)
    generator = torch.Generator(device=device)
    generator.manual_seed(seed)
    generated: list[int] = []
    model.eval()

    with torch.inference_mode():
        for _ in range(max_new_tokens):
            if input_ids.shape[1] >= configured_max:
                return GenerationResult(
                    False,
                    None,
                    tuple(generated),
                    "generation reached model context limit before EOS",
                )
            logits: Tensor = model(input_ids, attention_mask)
            if logits.ndim != 3 or logits.shape[:2] != input_ids.shape:
                raise ValueError("model returned logits with an invalid shape")
            scores = logits[0, -1].float() / float(temperature)
            if top_k is not None and top_k < scores.numel():
                values, indices = torch.topk(scores, top_k)
                restricted = torch.full_like(scores, float("-inf"))
                restricted.scatter_(0, indices, values)
                scores = restricted
            probabilities = torch.softmax(scores, dim=-1)
            if not torch.isfinite(probabilities).all() or probabilities.sum() <= 0:
                return GenerationResult(
                    False,
                    None,
                    tuple(generated),
                    "sampling distribution is non-finite or empty",
                )
            next_token = int(
                torch.multinomial(
                    probabilities,
                    1,
                    generator=generator,
                ).item()
            )
            generated.append(next_token)
            next_tensor = torch.tensor(((next_token,),), dtype=torch.long, device=device)
            input_ids = torch.cat((input_ids, next_tensor), dim=1)
            attention_mask = torch.cat(
                (
                    attention_mask,
                    torch.ones((1, 1), dtype=torch.bool, device=device),
                ),
                dim=1,
            )
            if next_token == EOS_ID:
                break
    return _decode_generated(generated, task, max_new_tokens)


def evaluate_checkpoint(
    model: nn.Module,
    tasks: Sequence[QualificationTask],
    *,
    device: torch.device,
    max_new_tokens: int = 64,
) -> CheckpointEvaluation:
    """Generate first, then score fixed outputs through each hidden evaluator."""

    if not tasks:
        raise ValueError("at least one qualification task is required")
    cases: list[EvaluatedGeneration] = []
    for task in tasks:
        generation = greedy_generate_mechanism(
            model,
            task.public,
            device=device,
            max_new_tokens=max_new_tokens,
        )
        hidden = (
            task.hidden_evaluate(generation.expression)
            if generation.valid and generation.expression is not None
            else None
        )
        cases.append(EvaluatedGeneration(task.public.task_id, generation, hidden))

    count = len(cases)
    valid = [case for case in cases if case.generation.valid]
    exact = [case for case in valid if case.hidden is not None and case.hidden.exact]
    visible = [
        case
        for case in valid
        if case.hidden is not None and case.hidden.visible_consistent
    ]
    semantic = [
        case.hidden.semantic_accuracy
        if case.hidden is not None
        else 0.0
        for case in cases
    ]
    hidden_accuracy = [
        case.hidden.hidden_accuracy
        if case.hidden is not None
        else 0.0
        for case in cases
    ]
    return CheckpointEvaluation(
        tuple(cases),
        len(valid) / count,
        len(exact) / count,
        len(visible) / count,
        mean(semantic),
        mean(hidden_accuracy),
    )
