"""End-to-end per-task plural-cognition experiment orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from plural_cognition.boolean_world.ast import Expr
from plural_cognition.boolean_world.qualification import HiddenEvaluation, QualificationTask
from plural_cognition.boolean_world.world import evaluate_visible

from .ablation import AblationOutcome, run_ablation_suite
from .coalition import SynthesisCoalitionReport, evaluate_synthesis_coalitions
from .extraction import extract_packet_from_candidate
from .graph import ProvenanceGraph, build_provenance_graph
from .graph_synthesis import integrate_synthesis_result
from .knowledge_metrics import PopulationKnowledgeReport, analyze_population_knowledge
from .packet import ValidatedPacket
from .synthesis import SynthesisConfig, synthesize_visible


@dataclass(frozen=True, slots=True)
class MemberCandidate:
    member_id: str
    expression: Expr | None
    error: str | None = None
    confidence: float = 0.5

    def __post_init__(self) -> None:
        if not self.member_id:
            raise ValueError("member_id must not be empty")
        if (self.expression is None) == (self.error is None):
            raise ValueError("member candidate requires exactly one of expression or error")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class IndividualTaskResult:
    member_id: str
    valid: bool
    error: str | None
    visible_accuracy: float
    hidden: HiddenEvaluation | None
    packet_sha256: str | None
    fragment_count: int

    @property
    def semantic_accuracy(self) -> float:
        return 0.0 if self.hidden is None else self.hidden.semantic_accuracy

    @property
    def exact(self) -> bool:
        return self.hidden is not None and self.hidden.exact


@dataclass(frozen=True, slots=True)
class PopulationTaskReport:
    task_id: str
    individuals: tuple[IndividualTaskResult, ...]
    ablations: tuple[AblationOutcome, ...] | None
    coalition: SynthesisCoalitionReport | None
    knowledge: PopulationKnowledgeReport | None
    graph: ProvenanceGraph | None
    full_synthesis_hidden: HiddenEvaluation | None
    best_individual_semantic_accuracy: float
    synthesis_gain: float
    analysis_available: bool
    unavailable_reason: str | None

    @property
    def full_synthesis_exact(self) -> bool:
        return self.full_synthesis_hidden is not None and self.full_synthesis_hidden.exact

    @property
    def novel_semantic_composition(self) -> bool:
        return (
            self.coalition is not None
            and self.coalition.full_outcome.novel_semantic_composition
        )

    @property
    def full_source_members(self) -> tuple[str, ...]:
        return () if self.coalition is None else self.coalition.full_provenance_members

    @property
    def multi_source_provenance(self) -> bool:
        return len(self.full_source_members) >= 2

    @property
    def score_necessary_members(self) -> tuple[str, ...]:
        return () if self.coalition is None else self.coalition.score_necessary_members

    @property
    def strong_synthesis_event(self) -> bool:
        return (
            self.analysis_available
            and self.full_synthesis_exact
            and self.synthesis_gain > 0.0
            and self.novel_semantic_composition
            and self.multi_source_provenance
            and len(self.score_necessary_members) >= 2
        )


def run_population_task_experiment(
    task: QualificationTask,
    members: Sequence[MemberCandidate],
    *,
    synthesis_config: SynthesisConfig | None = None,
    require_all_members_valid: bool = True,
) -> PopulationTaskReport:
    """Run individual, ablation, synthesis, graph, and coalition analysis.

    Every member output is fixed before this function is called. Hidden evaluation
    is used only after individual or collective candidates have been selected.
    """

    if not members:
        raise ValueError("at least one member candidate is required")
    member_ids = tuple(item.member_id for item in members)
    if len(member_ids) != len(set(member_ids)):
        raise ValueError("member IDs must be unique")

    individuals: list[IndividualTaskResult] = []
    packets: list[ValidatedPacket] = []
    invalid_members: list[str] = []

    for member in sorted(members, key=lambda item: item.member_id):
        if member.expression is None:
            invalid_members.append(member.member_id)
            individuals.append(
                IndividualTaskResult(
                    member.member_id,
                    False,
                    member.error,
                    0.0,
                    None,
                    None,
                    0,
                )
            )
            continue
        visible = evaluate_visible(member.expression, task.public)
        hidden = task.hidden_evaluate(member.expression)
        extracted = extract_packet_from_candidate(
            member.member_id,
            member.expression,
            task.public,
            confidence=member.confidence,
        )
        packets.append(extracted.validated)
        individuals.append(
            IndividualTaskResult(
                member.member_id,
                True,
                None,
                visible.matched / visible.total,
                hidden,
                extracted.validated.canonical_sha256,
                extracted.extracted_fragment_count,
            )
        )

    ordered_individuals = tuple(individuals)
    best_individual = max(item.semantic_accuracy for item in ordered_individuals)
    if invalid_members and require_all_members_valid:
        return PopulationTaskReport(
            task.public.task_id,
            ordered_individuals,
            None,
            None,
            None,
            None,
            None,
            best_individual,
            0.0,
            False,
            "invalid member outputs: " + ", ".join(sorted(invalid_members)),
        )
    if not packets:
        return PopulationTaskReport(
            task.public.task_id,
            ordered_individuals,
            None,
            None,
            None,
            None,
            None,
            best_individual,
            0.0,
            False,
            "no valid member packets",
        )

    def hidden_score(expression: Expr) -> float:
        return task.hidden_evaluate(expression).semantic_accuracy

    packet_tuple = tuple(packets)
    ablations = run_ablation_suite(
        task.public,
        packet_tuple,
        synthesis_config=synthesis_config,
        external_score=hidden_score,
    )
    coalition = evaluate_synthesis_coalitions(
        task.public,
        packet_tuple,
        hidden_score,
        synthesis_config=synthesis_config,
    )
    synthesis = synthesize_visible(task.public, packet_tuple, synthesis_config)
    full_hidden = task.hidden_evaluate(synthesis.best.expression)
    knowledge = analyze_population_knowledge(task.public, packet_tuple)
    graph = integrate_synthesis_result(
        build_provenance_graph(task.public, packet_tuple),
        synthesis,
    )
    return PopulationTaskReport(
        task.public.task_id,
        ordered_individuals,
        ablations,
        coalition,
        knowledge,
        graph,
        full_hidden,
        best_individual,
        full_hidden.semantic_accuracy - best_individual,
        True,
        None,
    )
