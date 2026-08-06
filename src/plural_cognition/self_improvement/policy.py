"""Target-free execution of frozen-weight reasoning-policy genomes."""

from __future__ import annotations

from dataclasses import dataclass

from plural_cognition.boolean_world import Expr, canonical_text, parse_canonical_text
from plural_cognition.population import (
    AblationMode,
    SynthesisConfig,
    extract_packet_from_candidate,
    run_ablation,
)

from .candidate_pool import CandidatePoolTask
from .genome import PolicyMode, ReasoningPolicyGenome


@dataclass(frozen=True, slots=True)
class ReasoningBudget:
    max_candidate_inputs: int = 8
    max_packet_extractions: int = 8
    max_reasoning_operations: int = 1024

    def __post_init__(self) -> None:
        for field in (
            "max_candidate_inputs",
            "max_packet_extractions",
            "max_reasoning_operations",
        ):
            if type(getattr(self, field)) is not int or getattr(self, field) < 1:
                raise ValueError(f"{field} must be a positive integer")


@dataclass(frozen=True, slots=True)
class PolicyResourceTrace:
    candidate_inputs: int
    valid_candidate_inputs: int
    packet_extractions: int
    fragment_audits: int
    candidate_evaluations: int
    generated_composites: int
    synthesis_rounds: int
    reasoning_operations: int
    within_budget: bool


@dataclass(frozen=True, slots=True)
class PolicyExecution:
    case_index: int
    genome_sha256: str
    valid: bool
    expression: Expr | None
    canonical_expression: str | None
    visible_matched: int
    visible_total: int
    source_ids: tuple[str, ...]
    error: str | None
    resources: PolicyResourceTrace

    @property
    def visible_accuracy(self) -> float:
        if self.visible_total == 0:
            return 0.0
        return self.visible_matched / self.visible_total


def _mode_to_ablation(mode: PolicyMode) -> AblationMode:
    return {
        PolicyMode.COMPLETE_SELECTION: AblationMode.COMPLETE_SELECTION,
        PolicyMode.VERIFIED_FRAGMENT_SELECTION: (
            AblationMode.VERIFIED_FRAGMENT_SELECTION
        ),
        PolicyMode.VERIFIED_SYNTHESIS: AblationMode.VERIFIED_SYNTHESIS,
        PolicyMode.UNVERIFIED_SYNTHESIS: AblationMode.UNVERIFIED_SYNTHESIS,
    }[mode]


def _empty_trace(candidate_inputs: int, valid_inputs: int) -> PolicyResourceTrace:
    operations = candidate_inputs
    return PolicyResourceTrace(
        candidate_inputs,
        valid_inputs,
        0,
        0,
        0,
        0,
        0,
        operations,
        False,
    )


def execute_reasoning_policy(
    genome: ReasoningPolicyGenome,
    task: CandidatePoolTask,
    *,
    budget: ReasoningBudget | None = None,
) -> PolicyExecution:
    """Fix one output using only public evidence and frozen candidate paths."""

    normalized = genome.normalized()
    active_budget = budget or ReasoningBudget()
    candidate_inputs = len(task.candidates)
    valid_inputs = sum(candidate.valid for candidate in task.candidates)
    if candidate_inputs > active_budget.max_candidate_inputs:
        return PolicyExecution(
            task.case_index,
            normalized.sha256,
            False,
            None,
            None,
            0,
            len(task.public_task.evidence),
            (),
            "candidate input count exceeds reasoning budget",
            _empty_trace(candidate_inputs, valid_inputs),
        )

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
        extracted = extract_packet_from_candidate(
            candidate.source_id,
            expression,
            public,
        )
        packets.append(extracted.validated)

    if not packets:
        return PolicyExecution(
            task.case_index,
            normalized.sha256,
            False,
            None,
            None,
            0,
            len(public.evidence),
            (),
            "frozen candidate pool contains no valid expressions",
            _empty_trace(candidate_inputs, valid_inputs),
        )
    if len(packets) > active_budget.max_packet_extractions:
        return PolicyExecution(
            task.case_index,
            normalized.sha256,
            False,
            None,
            None,
            0,
            len(public.evidence),
            (),
            "packet extraction count exceeds reasoning budget",
            _empty_trace(candidate_inputs, valid_inputs),
        )

    synthesis_config = SynthesisConfig(
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
            public,
            tuple(packets),
            _mode_to_ablation(normalized.mode),
            synthesis_config=synthesis_config,
        )
    except (RuntimeError, TypeError, ValueError) as exc:
        packet_count = len(packets)
        operations = candidate_inputs + packet_count
        trace = PolicyResourceTrace(
            candidate_inputs,
            valid_inputs,
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
            len(public.evidence),
            (),
            f"policy execution failed: {exc}",
            trace,
        )

    packet_count = len(packets)
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
        candidate_inputs
        + packet_count
        + fragment_audits
        + outcome.candidate_evaluations
        + outcome.generated_composites
    )
    within_budget = operations <= active_budget.max_reasoning_operations
    resources = PolicyResourceTrace(
        candidate_inputs,
        valid_inputs,
        packet_count,
        fragment_audits,
        outcome.candidate_evaluations,
        outcome.generated_composites,
        rounds,
        operations,
        within_budget,
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
            tuple(sorted({source.member_id for source in outcome.selected.sources})),
            "reasoning operation count exceeds budget",
            resources,
        )

    expression = outcome.selected.expression
    return PolicyExecution(
        task.case_index,
        normalized.sha256,
        True,
        expression,
        canonical_text(expression),
        outcome.selected.visible_matched,
        outcome.selected.visible_total,
        tuple(sorted({source.member_id for source in outcome.selected.sources})),
        None,
        resources,
    )
