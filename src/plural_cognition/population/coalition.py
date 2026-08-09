"""Exact coalition analysis around the bounded visible-only synthesizer."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Callable, Sequence

from plural_cognition.boolean_world.ast import Expr
from plural_cognition.boolean_world.world import PublicTask

from .credit import (
    CoalitionEvaluation,
    evaluate_all_coalitions,
    exact_shapley_values,
    leave_one_out_contributions,
)
from .packet import ValidatedPacket
from .synthesis import (
    SynthesisConfig,
    SynthesisResult,
    SynthesisTrace,
    synthesize_visible,
)

CandidateScore = Callable[[Expr], float]


@dataclass(frozen=True, slots=True)
class SynthesisCoalitionOutcome:
    members: tuple[str, ...]
    score: float
    selected_candidate_id: str | None
    selected_canonical_expression: str | None
    visible_accuracy: float
    selected_source_members: tuple[str, ...]
    novel_semantic_composition: bool
    trace: SynthesisTrace | None

    def __post_init__(self) -> None:
        if tuple(sorted(set(self.members))) != self.members:
            raise ValueError("coalition members must be sorted and unique")
        if not isfinite(float(self.score)):
            raise ValueError("coalition score must be finite")
        if not 0.0 <= self.visible_accuracy <= 1.0:
            raise ValueError("visible_accuracy must be in [0, 1]")
        if tuple(sorted(set(self.selected_source_members))) != self.selected_source_members:
            raise ValueError("selected_source_members must be sorted and unique")
        empty = not self.members
        if empty and any(
            value is not None
            for value in (
                self.selected_candidate_id,
                self.selected_canonical_expression,
                self.trace,
            )
        ):
            raise ValueError("empty coalition must not contain a synthesized result")
        if not empty and any(
            value is None
            for value in (
                self.selected_candidate_id,
                self.selected_canonical_expression,
                self.trace,
            )
        ):
            raise ValueError("non-empty coalition requires a synthesized result")


@dataclass(frozen=True, slots=True)
class RealizedMemberContribution:
    member_id: str
    full_score_drop: float
    shapley_value: float
    changes_selected_semantics: bool
    appears_in_full_provenance: bool

    @property
    def score_necessary(self) -> bool:
        return self.full_score_drop > 0.0

    @property
    def leave_one_out_score_drop(self) -> float:
        """Stable report-facing name for the realized full-coalition score drop."""

        return self.full_score_drop

    @property
    def selected_semantics_changed(self) -> bool:
        """Stable report-facing name for removal changing selected semantics."""

        return self.changes_selected_semantics


@dataclass(frozen=True, slots=True)
class SynthesisCoalitionReport:
    members: tuple[str, ...]
    outcomes: dict[frozenset[str], SynthesisCoalitionOutcome]
    evaluation: CoalitionEvaluation[str]
    contributions: tuple[RealizedMemberContribution, ...]

    def __post_init__(self) -> None:
        if tuple(sorted(set(self.members))) != self.members:
            raise ValueError("report members must be sorted and unique")
        if set(self.outcomes) != set(self.evaluation.values):
            raise ValueError("coalition outcomes and value table must have identical keys")
        if tuple(item.member_id for item in self.contributions) != self.members:
            raise ValueError("contributions must follow the report member order")

    @property
    def full_outcome(self) -> SynthesisCoalitionOutcome:
        return self.outcomes[frozenset(self.members)]

    @property
    def score_necessary_members(self) -> tuple[str, ...]:
        return tuple(
            item.member_id for item in self.contributions if item.score_necessary
        )

    @property
    def full_provenance_members(self) -> tuple[str, ...]:
        return self.full_outcome.selected_source_members


def evaluate_synthesis_coalitions(
    task: PublicTask,
    packets: Sequence[ValidatedPacket],
    score_candidate: CandidateScore,
    *,
    synthesis_config: SynthesisConfig | None = None,
    empty_value: float = 0.0,
) -> SynthesisCoalitionReport:
    """Run visible-only synthesis for every subset and score fixed outputs afterward.

    ``score_candidate`` may use hidden exact evaluation because it is invoked only
    after ``synthesize_visible`` has selected a coalition result. It cannot affect
    candidate generation, pruning, ranking, or selection.
    """

    if not isfinite(float(empty_value)):
        raise ValueError("empty_value must be finite")
    if not packets:
        raise ValueError("at least one validated packet is required")

    packet_by_member: dict[str, ValidatedPacket] = {}
    for packet in packets:
        member_id = packet.packet.member_id
        if member_id in packet_by_member:
            raise ValueError(f"duplicate member ID: {member_id!r}")
        packet_by_member[member_id] = packet
    members = tuple(sorted(packet_by_member))
    outcomes: dict[frozenset[str], SynthesisCoalitionOutcome] = {}

    def value_function(coalition: frozenset[str]) -> float:
        ordered_members = tuple(sorted(coalition))
        if not ordered_members:
            outcome = SynthesisCoalitionOutcome(
                (),
                float(empty_value),
                None,
                None,
                0.0,
                (),
                False,
                None,
            )
            outcomes[coalition] = outcome
            return outcome.score

        result: SynthesisResult = synthesize_visible(
            task,
            tuple(packet_by_member[member] for member in ordered_members),
            synthesis_config,
        )
        selected = result.best
        score = float(score_candidate(selected.expression))
        if not isfinite(score):
            raise ValueError(f"non-finite candidate score for coalition {ordered_members!r}")
        source_members = tuple(sorted({source.member_id for source in selected.sources}))
        outcome = SynthesisCoalitionOutcome(
            ordered_members,
            score,
            selected.candidate_id,
            selected.canonical_expression,
            selected.visible_accuracy,
            source_members,
            selected.novel_semantic_composition,
            result.trace,
        )
        outcomes[coalition] = outcome
        return score

    evaluation = evaluate_all_coalitions(members, value_function)
    shapley = exact_shapley_values(evaluation)
    leave_one_out = leave_one_out_contributions(evaluation)
    full = outcomes[frozenset(members)]
    provenance_members = set(full.selected_source_members)
    full_set = frozenset(members)

    contributions = tuple(
        RealizedMemberContribution(
            member,
            leave_one_out[member],
            shapley[member],
            outcomes[full_set - {member}].selected_candidate_id
            != full.selected_candidate_id,
            member in provenance_members,
        )
        for member in members
    )
    return SynthesisCoalitionReport(members, outcomes, evaluation, contributions)
