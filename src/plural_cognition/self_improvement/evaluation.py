"""Split-scoped scoring after target-free policy outputs are fixed."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Sequence

from plural_cognition.boolean_world import (
    CausalExample,
    encode_public_task,
    exact_equivalence,
    semantic_distance,
)
from plural_cognition.validation import decode_supervised_causal_example

from .candidate_pool import FrozenCandidatePool
from .genome import ReasoningPolicyGenome
from .policy import PolicyExecution, ReasoningBudget, execute_reasoning_policy


@dataclass(frozen=True, slots=True)
class PolicyTaskScore:
    case_index: int
    execution: PolicyExecution
    exact: bool
    semantic_accuracy: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.semantic_accuracy <= 1.0:
            raise ValueError("semantic_accuracy must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class PolicyEvaluation:
    genome_sha256: str
    task_indices: tuple[int, ...]
    cases: tuple[PolicyTaskScore, ...]
    exact_accuracy: float
    mean_semantic_accuracy: float
    visible_consistency_rate: float
    invalid_rate: float
    mean_reasoning_operations: float
    max_reasoning_operations: int
    over_budget_rate: float

    def __post_init__(self) -> None:
        if not self.cases:
            raise ValueError("policy evaluation requires at least one case")
        if self.task_indices != tuple(case.case_index for case in self.cases):
            raise ValueError("policy evaluation task identity is inconsistent")
        for field in (
            "exact_accuracy",
            "mean_semantic_accuracy",
            "visible_consistency_rate",
            "invalid_rate",
            "mean_reasoning_operations",
            "over_budget_rate",
        ):
            value = getattr(self, field)
            if type(value) not in (int, float):
                raise ValueError(f"{field} must be numeric")
            object.__setattr__(self, field, float(value))
        for value in (
            self.exact_accuracy,
            self.mean_semantic_accuracy,
            self.visible_consistency_rate,
            self.invalid_rate,
            self.over_budget_rate,
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError("evaluation rates must be in [0, 1]")
        if self.mean_reasoning_operations < 0.0:
            raise ValueError("mean reasoning operations must not be negative")
        if type(self.max_reasoning_operations) is not int or self.max_reasoning_operations < 0:
            raise ValueError("max reasoning operations must be a non-negative integer")

    @property
    def fitness_key(self) -> tuple[float, float, float, float, int, str]:
        """Deterministic development ordering; smaller tuple is better."""

        return (
            -self.mean_semantic_accuracy,
            -self.exact_accuracy,
            self.invalid_rate,
            self.mean_reasoning_operations,
            self.max_reasoning_operations,
            self.genome_sha256,
        )


def _validate_inputs(
    pool: FrozenCandidatePool,
    examples: Sequence[CausalExample],
) -> None:
    if len(pool.tasks) != len(examples):
        raise ValueError("candidate pool and evaluation examples have different lengths")
    for index, (task, example) in enumerate(zip(pool.tasks, examples, strict=True)):
        decoded = decode_supervised_causal_example(example)
        if tuple(encode_public_task(decoded.public)) != task.public_task_token_ids:
            raise ValueError(f"candidate pool public task differs at case {index}")


def evaluate_policy_on_split(
    genome: ReasoningPolicyGenome,
    pool: FrozenCandidatePool,
    examples: Sequence[CausalExample],
    *,
    task_indices: Sequence[int] | None = None,
    budget: ReasoningBudget | None = None,
    target_source_indices: Sequence[int] | None = None,
) -> PolicyEvaluation:
    """Execute target-free policies first, then score fixed outputs.

    ``target_source_indices`` supports the deterministic shuffled-label negative
    control. It changes only the scorer target; public tasks and candidate pools
    remain fixed.
    """

    _validate_inputs(pool, examples)
    indices = (
        tuple(range(len(examples)))
        if task_indices is None
        else tuple(task_indices)
    )
    if not indices:
        raise ValueError("policy split must contain at least one task")
    if len(set(indices)) != len(indices):
        raise ValueError("policy split task indices must be unique")
    if any(type(index) is not int or not 0 <= index < len(examples) for index in indices):
        raise ValueError("policy split contains an out-of-range task index")

    if target_source_indices is None:
        target_indices = indices
    else:
        target_indices = tuple(target_source_indices)
        if len(target_indices) != len(indices):
            raise ValueError("target-source mapping length differs from task split")
        if any(
            type(index) is not int or not 0 <= index < len(examples)
            for index in target_indices
        ):
            raise ValueError("target-source mapping contains an out-of-range index")

    cases: list[PolicyTaskScore] = []
    for case_index, target_index in zip(indices, target_indices, strict=True):
        execution = execute_reasoning_policy(
            genome,
            pool.tasks[case_index],
            budget=budget,
        )
        decoded_public = decode_supervised_causal_example(examples[case_index])
        decoded_target = decode_supervised_causal_example(examples[target_index])
        variable_order = decoded_public.public.variable_order
        if variable_order != decoded_target.public.variable_order:
            raise ValueError("shuffled target uses a different variable order")
        if execution.valid and execution.expression is not None:
            exact = exact_equivalence(
                execution.expression,
                decoded_target.target,
                variable_order,
            ).equivalent
            distance = semantic_distance(
                execution.expression,
                decoded_target.target,
                variable_order,
            )
            semantic_accuracy = 1.0 - (
                distance / (1 << len(variable_order))
            )
        else:
            exact = False
            semantic_accuracy = 0.0
        cases.append(
            PolicyTaskScore(
                case_index,
                execution,
                exact,
                semantic_accuracy,
            )
        )

    operations = tuple(case.execution.resources.reasoning_operations for case in cases)
    return PolicyEvaluation(
        genome.normalized().sha256,
        indices,
        tuple(cases),
        mean(float(case.exact) for case in cases),
        mean(case.semantic_accuracy for case in cases),
        mean(
            float(
                case.execution.valid
                and case.execution.visible_matched == case.execution.visible_total
            )
            for case in cases
        ),
        mean(float(not case.execution.valid) for case in cases),
        mean(operations),
        max(operations),
        mean(float(not case.execution.resources.within_budget) for case in cases),
    )
