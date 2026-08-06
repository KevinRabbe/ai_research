"""Deterministic visible-only packet extraction from one generated program."""

from __future__ import annotations

from dataclasses import dataclass

from plural_cognition.boolean_world.ast import (
    And,
    Const,
    Expr,
    Ite,
    Not,
    Or,
    Var,
    node_count,
)
from plural_cognition.boolean_world.canonical import canonical_text, normalize
from plural_cognition.boolean_world.semantics import evaluate, semantic_key
from plural_cognition.boolean_world.world import (
    PublicTask,
    assignment_mapping,
    evaluate_visible,
)

from .packet import (
    FragmentRole,
    HypothesisFragment,
    HypothesisPacket,
    ValidatedPacket,
    validate_and_hash_packet,
)


_ROLE_PRIORITY = {
    FragmentRole.CONDITION: 0,
    FragmentRole.EXCEPTION: 1,
    FragmentRole.REPAIR: 2,
    FragmentRole.CLAUSE: 3,
    FragmentRole.ATOM: 4,
    FragmentRole.ALTERNATIVE: 5,
    FragmentRole.COUNTEREXAMPLE: 6,
}


@dataclass(frozen=True, slots=True)
class ExtractedPacket:
    validated: ValidatedPacket
    extracted_fragment_count: int
    candidate_visible_accuracy: float


def _semantic_id(expression: Expr, variable_order: tuple[str, ...]) -> str:
    _, bitset = semantic_key(expression, variable_order)
    digits = max(1, ((1 << len(variable_order)) + 3) // 4)
    return f"F{bitset:0{digits}x}"


def _default_role(expression: Expr) -> FragmentRole:
    match expression:
        case Const() | Var() | Not(child=Var()):
            return FragmentRole.ATOM
        case And() | Or():
            return FragmentRole.CLAUSE
        case Not():
            return FragmentRole.EXCEPTION
        case Ite():
            return FragmentRole.ALTERNATIVE
        case _:
            raise TypeError(f"unsupported expression type: {type(expression)!r}")


def _collect_occurrences(expression: Expr) -> list[tuple[Expr, FragmentRole]]:
    occurrences: list[tuple[Expr, FragmentRole]] = []

    def visit(node: Expr, role: FragmentRole | None, *, root: bool = False) -> None:
        if not root:
            occurrences.append((normalize(node), role or _default_role(node)))
        match node:
            case Const() | Var():
                return
            case Not(child=child):
                visit(child, FragmentRole.ATOM)
            case And(children=children) | Or(children=children):
                for child in children:
                    visit(child, _default_role(child))
            case Ite(condition=condition, when_true=when_true, when_false=when_false):
                visit(condition, FragmentRole.CONDITION)
                visit(when_true, _default_role(when_true))
                visit(when_false, FragmentRole.EXCEPTION)
            case _:
                raise TypeError(f"unsupported expression type: {type(node)!r}")

    visit(normalize(expression), None, root=True)
    return occurrences


def extract_packet_from_candidate(
    member_id: str,
    candidate: Expr,
    task: PublicTask,
    *,
    confidence: float = 0.5,
    max_fragments: int = 32,
) -> ExtractedPacket:
    """Convert one fixed candidate into a verified, auditable packet.

    Only syntactic subexpressions of the generated candidate are admitted. Public
    evidence labels each fragment's support and contradiction sets; no hidden
    assignment or target mechanism is available to this function.
    """

    if not member_id:
        raise ValueError("member_id must not be empty")
    if max_fragments < 1:
        raise ValueError("max_fragments must be positive")
    if not 0.0 <= float(confidence) <= 1.0:
        raise ValueError("confidence must be in [0, 1]")

    normalized_candidate = normalize(candidate)
    occurrences = _collect_occurrences(normalized_candidate)
    by_semantics: dict[int, tuple[Expr, set[FragmentRole]]] = {}
    for expression, role in occurrences:
        _, bitset = semantic_key(expression, task.variable_order)
        if bitset not in by_semantics:
            by_semantics[bitset] = (expression, {role})
        else:
            representative, roles = by_semantics[bitset]
            if canonical_text(expression) < canonical_text(representative):
                representative = expression
            roles.add(role)
            by_semantics[bitset] = (representative, roles)

    if not by_semantics:
        _, bitset = semantic_key(normalized_candidate, task.variable_order)
        by_semantics[bitset] = (
            normalized_candidate,
            {FragmentRole.ALTERNATIVE},
        )

    selected = sorted(
        by_semantics.items(),
        key=lambda item: (
            -node_count(item[1][0]),
            canonical_text(item[1][0]),
            item[0],
        ),
    )[:max_fragments]

    case_assignments = {
        case.case_id: assignment_mapping(task.variable_order, case.assignment)
        for case in task.evidence
    }
    observed = {case.case_id: case.output for case in task.evidence}
    fragments: list[HypothesisFragment] = []
    for _, (expression, roles) in selected:
        outputs = {
            case_id: evaluate(expression, assignment)
            for case_id, assignment in case_assignments.items()
        }
        support = tuple(
            sorted(
                case_id
                for case_id, output in outputs.items()
                if output == observed[case_id]
            )
        )
        contradiction = tuple(
            sorted(
                case_id
                for case_id, output in outputs.items()
                if output != observed[case_id]
            )
        )
        role = min(roles, key=lambda item: (_ROLE_PRIORITY[item], item.value))
        fragments.append(
            HypothesisFragment(
                _semantic_id(expression, task.variable_order),
                expression,
                role,
                supporting_case_ids=support,
                contradicting_case_ids=contradiction,
                confidence=float(confidence),
            )
        )

    visible = evaluate_visible(normalized_candidate, task)
    if not visible.valid:
        raise ValueError(f"candidate cannot be evaluated on public task: {visible.error}")
    packet = HypothesisPacket(
        member_id,
        normalized_candidate,
        tuple(sorted(fragments, key=lambda item: item.fragment_id)),
        counterexample_case_ids=visible.mismatch_case_ids,
    )
    return ExtractedPacket(
        validate_and_hash_packet(packet, task),
        len(fragments),
        visible.matched / visible.total,
    )
