"""Functional knowledge-uniqueness metrics for structured population packets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from plural_cognition.boolean_world.ast import And, Const, Expr, Ite, Not, Or, Var
from plural_cognition.boolean_world.semantics import semantic_key
from plural_cognition.boolean_world.world import PublicTask

from .packet import ValidatedPacket
from .verification import audit_visible_packet


@dataclass(frozen=True, slots=True)
class MemberKnowledgeContribution:
    member_id: str
    verified_fragment_semantics: tuple[str, ...]
    unique_verified_fragment_semantics: tuple[str, ...]
    verified_counterexample_case_ids: tuple[str, ...]
    unique_counterexample_case_ids: tuple[str, ...]
    accepted_operators: tuple[str, ...]
    unique_operators: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PopulationKnowledgeReport:
    members: tuple[MemberKnowledgeContribution, ...]
    fragment_owners: tuple[tuple[str, tuple[str, ...]], ...]
    counterexample_owners: tuple[tuple[str, tuple[str, ...]], ...]
    operator_owners: tuple[tuple[str, tuple[str, ...]], ...]

    def for_member(self, member_id: str) -> MemberKnowledgeContribution:
        matches = tuple(item for item in self.members if item.member_id == member_id)
        if len(matches) != 1:
            raise KeyError(member_id)
        return matches[0]


def _semantic_id(expression: Expr, variable_order: tuple[str, ...]) -> str:
    _, bitset = semantic_key(expression, variable_order)
    digits = max(1, ((1 << len(variable_order)) + 3) // 4)
    return f"semantic:{bitset:0{digits}x}"


def _operators(expression: Expr) -> set[str]:
    result: set[str] = set()

    def visit(node: Expr) -> None:
        match node:
            case Const() | Var():
                return
            case Not(child=child):
                result.add("NOT")
                visit(child)
            case And(children=children):
                result.add("AND")
                for child in children:
                    visit(child)
            case Or(children=children):
                result.add("OR")
                for child in children:
                    visit(child)
            case Ite(condition=condition, when_true=when_true, when_false=when_false):
                result.add("ITE")
                visit(condition)
                visit(when_true)
                visit(when_false)
            case _:
                raise TypeError(f"unsupported expression type: {type(node)!r}")

    visit(expression)
    return result


def _owners(values_by_member: dict[str, set[str]]) -> dict[str, tuple[str, ...]]:
    owners: dict[str, set[str]] = {}
    for member_id, values in values_by_member.items():
        for value in values:
            owners.setdefault(value, set()).add(member_id)
    return {
        value: tuple(sorted(member_ids))
        for value, member_ids in sorted(owners.items())
    }


def analyze_population_knowledge(
    task: PublicTask,
    packets: Sequence[ValidatedPacket],
) -> PopulationKnowledgeReport:
    """Measure useful packet diversity using visible-verifiable semantics.

    Textual differences are ignored. Equivalent fragments share one semantic
    identity, and false proof metadata contributes neither fragments nor the
    operators available only inside those rejected fragments.
    """

    if not packets:
        raise ValueError("at least one validated packet is required")
    member_ids = tuple(packet.packet.member_id for packet in packets)
    if len(member_ids) != len(set(member_ids)):
        raise ValueError("population knowledge analysis requires unique member IDs")

    fragments_by_member: dict[str, set[str]] = {}
    counterexamples_by_member: dict[str, set[str]] = {}
    operators_by_member: dict[str, set[str]] = {}

    for validated in packets:
        packet = validated.packet
        audit = audit_visible_packet(validated, task)
        verified_ids = set(audit.verified_fragment_ids)

        fragments = {
            _semantic_id(fragment.expression, task.variable_order)
            for fragment in packet.fragments
            if fragment.fragment_id in verified_ids
        }
        valid_counterexamples = set(packet.counterexample_case_ids).intersection(
            audit.candidate.mismatch_case_ids
        )
        accepted_operators = _operators(packet.complete_candidate)
        for fragment in packet.fragments:
            if fragment.fragment_id in verified_ids:
                accepted_operators.update(_operators(fragment.expression))

        fragments_by_member[packet.member_id] = fragments
        counterexamples_by_member[packet.member_id] = valid_counterexamples
        operators_by_member[packet.member_id] = accepted_operators

    fragment_owners = _owners(fragments_by_member)
    counterexample_owners = _owners(counterexamples_by_member)
    operator_owners = _owners(operators_by_member)

    contributions = tuple(
        MemberKnowledgeContribution(
            member_id,
            tuple(sorted(fragments_by_member[member_id])),
            tuple(
                sorted(
                    value
                    for value in fragments_by_member[member_id]
                    if fragment_owners[value] == (member_id,)
                )
            ),
            tuple(sorted(counterexamples_by_member[member_id])),
            tuple(
                sorted(
                    value
                    for value in counterexamples_by_member[member_id]
                    if counterexample_owners[value] == (member_id,)
                )
            ),
            tuple(sorted(operators_by_member[member_id])),
            tuple(
                sorted(
                    value
                    for value in operators_by_member[member_id]
                    if operator_owners[value] == (member_id,)
                )
            ),
        )
        for member_id in sorted(member_ids)
    )
    return PopulationKnowledgeReport(
        contributions,
        tuple(sorted(fragment_owners.items())),
        tuple(sorted(counterexample_owners.items())),
        tuple(sorted(operator_owners.items())),
    )
