"""Exact generated-program evaluation for frozen supervised validation shards."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Sequence

import torch
from torch import nn

from .boolean_world.ast import Expr
from .boolean_world.codec import (
    BOS_ID,
    EOS_ID,
    CausalExample,
    CodecError,
    decode_mechanism,
    decode_public_task,
)
from .boolean_world.semantics import exact_equivalence, semantic_distance
from .boolean_world.world import PublicTask, evaluate_visible
from .inference import ANSWER_ID, GenerationResult, greedy_generate_mechanism


@dataclass(frozen=True, slots=True)
class DecodedSupervision:
    public: PublicTask
    target: Expr


@dataclass(frozen=True, slots=True)
class ValidationCaseResult:
    case_index: int
    task_id: str
    generation: GenerationResult
    exact: bool
    visible_consistent: bool
    semantic_accuracy: float

    def __post_init__(self) -> None:
        if self.case_index < 0:
            raise ValueError("validation case_index must not be negative")


@dataclass(frozen=True, slots=True)
class ValidationEvaluation:
    cases: tuple[ValidationCaseResult, ...]
    parse_rate: float
    exact_accuracy: float
    visible_consistency_rate: float
    mean_semantic_accuracy: float


def decode_supervised_causal_example(example: CausalExample) -> DecodedSupervision:
    """Recover public input and evaluator-only target from one stored example."""

    if example.token_ids[example.answer_start] != ANSWER_ID:
        raise CodecError("causal example answer boundary token is invalid")
    task_ids = (*example.token_ids[: example.answer_start], EOS_ID)
    answer_ids = (BOS_ID, *example.token_ids[example.answer_start :])
    public = decode_public_task(task_ids)
    target = decode_mechanism(
        answer_ids,
        allowed_variables=public.variable_order,
    )
    return DecodedSupervision(public, target)


def evaluate_validation_examples(
    model: nn.Module,
    examples: Sequence[CausalExample],
    *,
    device: torch.device,
    max_new_tokens: int = 64,
) -> ValidationEvaluation:
    """Generate fixed outputs, then compare them to evaluator-only targets."""

    if not examples:
        raise ValueError("validation evaluation requires at least one example")
    cases: list[ValidationCaseResult] = []
    for case_index, example in enumerate(examples):
        decoded = decode_supervised_causal_example(example)
        generation = greedy_generate_mechanism(
            model,
            decoded.public,
            device=device,
            max_new_tokens=max_new_tokens,
        )
        if generation.valid and generation.expression is not None:
            exact = exact_equivalence(
                generation.expression,
                decoded.target,
                decoded.public.variable_order,
            ).equivalent
            visible = evaluate_visible(generation.expression, decoded.public).consistent
            semantic_accuracy = 1.0 - semantic_distance(
                generation.expression,
                decoded.target,
                decoded.public.variable_order,
            )
        else:
            exact = False
            visible = False
            semantic_accuracy = 0.0
        cases.append(
            ValidationCaseResult(
                case_index,
                decoded.public.task_id,
                generation,
                exact,
                visible,
                semantic_accuracy,
            )
        )

    return ValidationEvaluation(
        tuple(cases),
        mean(float(case.generation.valid) for case in cases),
        mean(float(case.exact) for case in cases),
        mean(float(case.visible_consistent) for case in cases),
        mean(case.semantic_accuracy for case in cases),
    )
