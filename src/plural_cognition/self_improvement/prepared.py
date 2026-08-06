"""Precomputed target-free candidate packets for efficient SI search replay."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Sequence

from plural_cognition.boolean_world import (
    CausalExample,
    Expr,
    PublicTask,
    canonical_text,
    encode_public_task,
    exact_equivalence,
    parse_canonical_text,
    semantic_distance,
)
from plural_cognition.population import (
    AblationMode,
    SynthesisConfig,
    ValidatedPacket,
    extract_packet_from_candidate,
    run_ablation,
)
from plural_cognition.validation import decode_supervised_causal_example

from .candidate_pool import CandidatePoolTask, FrozenCandidatePool
from .evaluation import PolicyEvaluation, PolicyTaskScore
from .genome import PolicyMode, ReasoningPolicyGenome
from .policy import (
    PolicyExecution,
    PolicyResourceTrace,
    ReasoningBudget,
)


@dataclass(frozen=True, slots=True)
class PreparedPolicyTask:
    case_index: int
    public: PublicTask
    candidate_inputs: int
    valid_candidate_inputs: int
    packets: tuple[ValidatedPacket, ...]

    def __post_init__(self) -> None:
        if self.case_index < 0:
            raise ValueError("prepared case index must not be negative")
        if self.candidate_inputs < 1:
            raise ValueError("prepared task requires candidate inputs")
        if not 0 <= self.valid_candidate_inputs <= self.candidate_inputs:
            raise ValueError("prepared valid-candidate count is inconsistent")
        if len(self.packets) != self.valid_candidate_inputs:
            raise ValueError("prepared packet count differs from valid inputs")


@dataclass(frozen=True, slots=True)
class PreparedCandidatePool:
    pool_sha256: str
    tasks: tuple[PreparedPolicyTask, ...]

    def __post_init__(self) -> None:
        if len(self.pool_sha256) != 64:
            raise ValueError("prepared pool SHA must contain 64 characters")
        int(self.pool_sha256, 16)
        if not self.tasks:
            raise ValueError("prepared pool requires tasks")
        if tuple(task.case_index for task in self.tasks) != tuple(range(len(self.tasks))):
            raise ValueError("prepared task indices must be contiguous")


def prepare_candidate_pool(pool: FrozenCandidatePool) -> PreparedCandidatePool:
    tasks = []
    for task in pool.tasks:
        public = task.public_task
        packets = []
        for candidate in task.candidates:
            if not candidate.valid:
                continue
            if candidate.expression_text is None:
                raise AssertionError("valid frozen candidate lost its expression")
            expression = parse_canonical_text(
                candidate.expression_text,
                allowed_variables=public.variable_order,
            )
            packets.append(
                extract_packet_from_candidate(
                    candidate.source_id,
                    expression,
                    public,
                ).validated
            )
        tasks.append(
            PreparedPolicyTask(
                task.case_index,
                public,
                len(task.candidates),
                len(packets),
                tuple(packets),
            )
        )
    return PreparedCandidatePool(pool.sha256, tuple(tasks))


def _mode_to_ablation(mode: PolicyMode) -> AblationMode:
    return {
        PolicyMode.COMPLETE_SELECTION: AblationMode.COMPLETE_SELECTION,
        PolicyMode.VERIFIED_FRAGMENT_SELECTION: AblationMode.VERIFIED_FRAGMENT_SELECTION,
        PolicyMode.VERIFIED_SYNTHESIS: AblationMode.VERIFIED_SYNTHESIS,
        PolicyMode.UNVERIFIED_SYNTHESIS: AblationMode.UNVERIFIED_SYNTHESIS,
    }[mode]


def execute_prepared_policy(
    genome: ReasoningPolicyGenome,
    task: PreparedPolicyTask,
    *,
    budget: ReasoningBudget | None = None,
) -> PolicyExecution:
    normalized = genome.normalized()
    active_budget = budget or ReasoningBudget()
    packet_count = len(task.packets)
    if task.candidate_inputs > active_budget.max_candidate_inputs:
        resources = PolicyResourceTrace(
            task.candidate_inputs,
            task.valid_candidate_inputs,
            0,
            0,
            0,
            0,
            0,
            task.candidate_inputs,
            False,
        )
        return PolicyExecution(
            task.case_index,
            normalized.sha256,
            False,
            None,
            None,
            0,
            len(task.public.evidence),
            (),
            "candidate input count exceeds reasoning budget",
            resources,
        )
    if not task.packets:
        resources = PolicyResourceTrace(
            task.candidate_inputs,
            0,
            0,
            0,
            0,
            0,
            0,
            task.candidate_inputs,
            True,
        )
        return PolicyExecution(
            task.case_index,
            normalized.sha256,
            False,
            None,
            None,
            0,
            len(task.public.evidence),
            (),
            "frozen candidate pool contains no valid expressions",
            resources,
        )
    if packet_count > active_budget.max_packet_extractions:
        resources = PolicyResourceTrace(
            task.candidate_inputs,
            task.valid_candidate_inputs,
            0,
            0,
            0,
            0,
            0,
            task.candidate_inputs,
            False,
        )
        return PolicyExecution(
            task.case_index,
            normalized.sha256,
            False,
            None,
            None,
            0,
            len(task.public.evidence),
            (),
            "packet extraction count exceeds reasoning budget",
            resources,
        )

    config = SynthesisConfig(
        max_rounds=normalized.synthesis_rounds,
        max_unique_candidates=normalized.max_unique_candidates,
        max_candidate_evaluations=normalized.max_candidate_evaluations,
        max_generated_composites=normalized.max_generated_composites,
        max_expression_nodes=normalized.max_expression_nodes,
        max_expression_depth=normalized.max_expression_depth,
        require_verified_fragment_metadata=(
            normalized.mode is not PolicyMode.UNVERIFIED_SYNTHESIS
        ),
    )
    try:
        outcome = run_ablation(
            task.public,
            task.packets,
            _mode_to_ablation(normalized.mode),
            synthesis_config=config,
        )
    except (RuntimeError, TypeError, ValueError) as exc:
        operations = task.candidate_inputs + packet_count
        resources = PolicyResourceTrace(
            task.candidate_inputs,
            task.valid_candidate_inputs,
            packet_count,
            0,
            0,
            0,
            normalized.synthesis_rounds if normalized.mode.uses_synthesis else 0,
            operations,
            operations <= active_budget.max_reasoning_operations,
        )
        return PolicyExecution(
            task.case_index,
            normalized.sha256,
            False,
            None,
            None,
            0,
            len(task.public.evidence),
            (),
            f"policy execution failed: {exc}",
            resources,
        )

    fragment_audits = (
        packet_count
        if normalized.mode
        in {
            PolicyMode.VERIFIED_FRAGMENT_SELECTION,
            PolicyMode.VERIFIED_SYNTHESIS,
        }
        else 0
    )
    rounds = normalized.synthesis_rounds if normalized.mode.uses_synthesis else 0
    operations = (
        task.candidate_inputs
        + packet_count
        + fragment_audits
        + outcome.candidate_evaluations
        + outcome.generated_composites
    )
    within_budget = operations <= active_budget.max_reasoning_operations
    resources = PolicyResourceTrace(
        task.candidate_inputs,
        task.valid_candidate_inputs,
        packet_count,
        fragment_audits,
        outcome.candidate_evaluations,
        outcome.generated_composites,
        rounds,
        operations,
        within_budget,
    )
    sources = tuple(
        sorted({source.member_id for source in outcome.selected.sources})
    )
    if not within_budget:
        return PolicyExecution(
            task.case_index,
            normalized.sha256,
            False,
            None,
            None,
            outcome.selected.visible_matched,
            outcome.selected.visible_total,
            sources,
            "reasoning operation count exceeds budget",
            resources,
        )
    expression: Expr = outcome.selected.expression
    return PolicyExecution(
        task.case_index,
        normalized.sha256,
        True,
        expression,
        canonical_text(expression),
        outcome.selected.visible_matched,
        outcome.selected.visible_total,
        sources,
        None,
        resources,
    )


def evaluate_prepared_policy_on_split(
    genome: ReasoningPolicyGenome,
    prepared: PreparedCandidatePool,
    examples: Sequence[CausalExample],
    *,
    budget: ReasoningBudget | None = None,
    target_source_indices: Sequence[int] | None = None,
) -> PolicyEvaluation:
    if len(prepared.tasks) != len(examples):
        raise ValueError("prepared pool and split examples have different lengths")
    for index, (task, example) in enumerate(zip(prepared.tasks, examples, strict=True)):
        decoded = decode_supervised_causal_example(example)
        if tuple(encode_public_task(decoded.public)) != tuple(encode_public_task(task.public)):
            raise ValueError(f"prepared public task differs at case {index}")

    indices = tuple(range(len(examples)))
    targets = indices if target_source_indices is None else tuple(target_source_indices)
    if len(targets) != len(indices):
        raise ValueError("target-source mapping length differs from split")
    if any(type(index) is not int or not 0 <= index < len(examples) for index in targets):
        raise ValueError("target-source mapping contains an out-of-range index")

    cases = []
    for case_index, target_index in zip(indices, targets, strict=True):
        execution = execute_prepared_policy(
            genome,
            prepared.tasks[case_index],
            budget=budget,
        )
        target = decode_supervised_causal_example(examples[target_index]).target
        variable_order = prepared.tasks[case_index].public.variable_order
        if execution.valid and execution.expression is not None:
            exact = exact_equivalence(
                execution.expression,
                target,
                variable_order,
            ).equivalent
            semantic_accuracy = 1.0 - semantic_distance(
                execution.expression,
                target,
                variable_order,
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
