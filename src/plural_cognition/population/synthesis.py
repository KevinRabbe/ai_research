"""Bounded, visible-only symbolic synthesis from verified member proposals."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import combinations_with_replacement, product
from typing import Iterable, Sequence

from plural_cognition.boolean_world.ast import (
    And,
    Const,
    Expr,
    Ite,
    Not,
    Or,
    Var,
    depth,
    node_count,
)
from plural_cognition.boolean_world.canonical import canonical_text, normalize
from plural_cognition.boolean_world.semantics import semantic_key
from plural_cognition.boolean_world.world import PublicTask, evaluate_visible

from .packet import ValidatedPacket
from .graph import SourceRef
from .verification import audit_visible_packet


class SynthesisRule(str, Enum):
    INITIAL_CANDIDATE = "initial-candidate"
    INITIAL_FRAGMENT = "initial-fragment"
    NOT = "not"
    AND = "and"
    OR = "or"
    ITE = "ite"


@dataclass(frozen=True, order=True, slots=True)
class Derivation:
    rule: SynthesisRule
    parent_candidate_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if tuple(sorted(set(self.parent_candidate_ids))) != self.parent_candidate_ids:
            raise ValueError("derivation parents must be sorted and unique")
        if self.rule in (
            SynthesisRule.INITIAL_CANDIDATE,
            SynthesisRule.INITIAL_FRAGMENT,
        ) and self.parent_candidate_ids:
            raise ValueError("initial derivations must not have parents")
        if self.rule not in (
            SynthesisRule.INITIAL_CANDIDATE,
            SynthesisRule.INITIAL_FRAGMENT,
        ) and not self.parent_candidate_ids:
            raise ValueError("composite derivations require parents")


@dataclass(frozen=True, slots=True)
class SynthesizedCandidate:
    candidate_id: str
    expression: Expr
    canonical_expression: str
    equivalent_forms: tuple[str, ...]
    visible_matched: int
    visible_total: int
    mismatch_case_ids: tuple[str, ...]
    sources: tuple[SourceRef, ...]
    derivations: tuple[Derivation, ...]
    initial_semantics: bool

    @property
    def visible_accuracy(self) -> float:
        if self.visible_total == 0:
            return 0.0
        return self.visible_matched / self.visible_total

    @property
    def visible_consistent(self) -> bool:
        return self.visible_matched == self.visible_total

    @property
    def novel_semantic_composition(self) -> bool:
        return not self.initial_semantics


@dataclass(frozen=True, slots=True)
class SynthesisConfig:
    max_rounds: int = 2
    max_unique_candidates: int = 256
    max_candidate_evaluations: int = 2048
    max_generated_composites: int = 2048
    max_expression_nodes: int = 32
    max_expression_depth: int = 8
    require_verified_fragment_metadata: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "max_rounds",
            "max_unique_candidates",
            "max_candidate_evaluations",
            "max_generated_composites",
            "max_expression_nodes",
            "max_expression_depth",
        ):
            if getattr(self, field_name) < 1:
                raise ValueError(f"{field_name} must be positive")


@dataclass(frozen=True, slots=True)
class SynthesisTrace:
    allowed_operators: tuple[str, ...]
    initial_expressions: int
    candidate_evaluations: int
    generated_composites: int
    unique_semantics: int
    semantic_duplicates: int
    pruned_node_limit: int
    pruned_depth_limit: int
    excluded_unverified_fragments: int
    stopped_reason: str


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    candidates: tuple[SynthesizedCandidate, ...]
    trace: SynthesisTrace

    @property
    def best(self) -> SynthesizedCandidate:
        if not self.candidates:
            raise RuntimeError("synthesis produced no candidates")
        return self.candidates[0]


@dataclass(slots=True)
class _Record:
    candidate_id: str
    expression: Expr
    forms: set[str]
    visible_matched: int
    visible_total: int
    mismatch_case_ids: tuple[str, ...]
    sources: set[SourceRef]
    derivations: set[Derivation]
    initial_semantics: bool


@dataclass(slots=True)
class _Counters:
    candidate_evaluations: int = 0
    generated_composites: int = 0
    semantic_duplicates: int = 0
    pruned_node_limit: int = 0
    pruned_depth_limit: int = 0
    excluded_unverified_fragments: int = 0
    stopped_reason: str = "completed"


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

    visit(normalize(expression))
    return result


def _candidate_id(bitset: int, variable_count: int) -> str:
    digits = max(1, ((1 << variable_count) + 3) // 4)
    return f"candidate:{bitset:0{digits}x}"


def _rank_key(candidate: SynthesizedCandidate) -> tuple:
    return (
        -candidate.visible_matched,
        node_count(candidate.expression),
        depth(candidate.expression),
        candidate.canonical_expression,
        candidate.candidate_id,
    )


def synthesize_visible(
    task: PublicTask,
    packets: Sequence[ValidatedPacket],
    config: SynthesisConfig | None = None,
) -> SynthesisResult:
    """Compose member proposals under deterministic visible-only resource bounds."""

    if not packets:
        raise ValueError("at least one validated packet is required")
    effective = config or SynthesisConfig()
    counters = _Counters()
    records: dict[int, _Record] = {}
    canonical_seen: set[str] = set()
    allowed_operators: set[str] = set()
    initial_expressions = 0

    audits = {
        packet.canonical_sha256: audit_visible_packet(packet, task)
        for packet in packets
    }

    def add_expression(
        expression: Expr,
        sources: Iterable[SourceRef],
        derivation: Derivation,
        *,
        initial: bool,
        generated: bool,
    ) -> bool:
        nonlocal initial_expressions
        normalized = normalize(expression)
        if node_count(normalized) > effective.max_expression_nodes:
            counters.pruned_node_limit += 1
            return True
        if depth(normalized) > effective.max_expression_depth:
            counters.pruned_depth_limit += 1
            return True
        if counters.candidate_evaluations >= effective.max_candidate_evaluations:
            counters.stopped_reason = "candidate-evaluation-limit"
            return False
        if generated and counters.generated_composites >= effective.max_generated_composites:
            counters.stopped_reason = "generated-composite-limit"
            return False

        text = canonical_text(normalized)
        if generated:
            counters.generated_composites += 1
        if initial:
            initial_expressions += 1
        counters.candidate_evaluations += 1
        _, bitset = semantic_key(normalized, task.variable_order)
        visible = evaluate_visible(normalized, task)
        candidate_id = _candidate_id(bitset, len(task.variable_order))
        source_set = set(sources)

        record = records.get(bitset)
        if record is None:
            if len(records) >= effective.max_unique_candidates:
                counters.stopped_reason = "unique-candidate-limit"
                return False
            records[bitset] = _Record(
                candidate_id,
                normalized,
                {text},
                visible.matched,
                visible.total,
                visible.mismatch_case_ids,
                source_set,
                {derivation},
                initial,
            )
        else:
            counters.semantic_duplicates += 1
            record.forms.add(text)
            record.sources.update(source_set)
            record.derivations.add(derivation)
            record.initial_semantics = record.initial_semantics or initial
            if text < canonical_text(record.expression):
                record.expression = normalized
        canonical_seen.add(text)
        return True

    for packet in sorted(packets, key=lambda item: item.canonical_sha256):
        member = packet.packet.member_id
        allowed_operators.update(_operators(packet.packet.complete_candidate))
        candidate_source = SourceRef(
            member, packet.canonical_sha256, "complete_candidate"
        )
        if not add_expression(
            packet.packet.complete_candidate,
            (candidate_source,),
            Derivation(SynthesisRule.INITIAL_CANDIDATE, ()),
            initial=True,
            generated=False,
        ):
            break

        verified_ids = set(audits[packet.canonical_sha256].verified_fragment_ids)
        for fragment in sorted(packet.packet.fragments, key=lambda item: item.fragment_id):
            allowed_operators.update(_operators(fragment.expression))
            if (
                effective.require_verified_fragment_metadata
                and fragment.fragment_id not in verified_ids
            ):
                counters.excluded_unverified_fragments += 1
                continue
            source = SourceRef(member, packet.canonical_sha256, fragment.fragment_id)
            if not add_expression(
                fragment.expression,
                (source,),
                Derivation(SynthesisRule.INITIAL_FRAGMENT, ()),
                initial=True,
                generated=False,
            ):
                break

    if not records:
        raise RuntimeError("no candidate survived initial synthesis validation")

    def snapshot() -> tuple[_Record, ...]:
        return tuple(
            sorted(
                records.values(),
                key=lambda record: (
                    canonical_text(record.expression),
                    record.candidate_id,
                ),
            )
        )

    stop = counters.stopped_reason != "completed"
    for _round in range(effective.max_rounds):
        if stop:
            break
        current = snapshot()

        if "NOT" in allowed_operators:
            for record in current:
                if not add_expression(
                    Not(record.expression),
                    record.sources,
                    Derivation(SynthesisRule.NOT, (record.candidate_id,)),
                    initial=False,
                    generated=True,
                ):
                    stop = True
                    break
        if stop:
            break

        for operator, rule in (("AND", SynthesisRule.AND), ("OR", SynthesisRule.OR)):
            if operator not in allowed_operators:
                continue
            for left, right in combinations_with_replacement(current, 2):
                expression: Expr
                if operator == "AND":
                    expression = And((left.expression, right.expression))
                else:
                    expression = Or((left.expression, right.expression))
                if not add_expression(
                    expression,
                    left.sources.union(right.sources),
                    Derivation(
                        rule,
                        tuple(sorted({left.candidate_id, right.candidate_id})),
                    ),
                    initial=False,
                    generated=True,
                ):
                    stop = True
                    break
            if stop:
                break
        if stop:
            break

        if "ITE" in allowed_operators:
            for condition, when_true, when_false in product(current, repeat=3):
                if not add_expression(
                    Ite(
                        condition.expression,
                        when_true.expression,
                        when_false.expression,
                    ),
                    condition.sources.union(when_true.sources).union(
                        when_false.sources
                    ),
                    Derivation(
                        SynthesisRule.ITE,
                        tuple(
                            sorted(
                                {
                                    condition.candidate_id,
                                    when_true.candidate_id,
                                    when_false.candidate_id,
                                }
                            )
                        ),
                    ),
                    initial=False,
                    generated=True,
                ):
                    stop = True
                    break

    candidates = tuple(
        sorted(
            (
                SynthesizedCandidate(
                    record.candidate_id,
                    record.expression,
                    canonical_text(record.expression),
                    tuple(sorted(record.forms)),
                    record.visible_matched,
                    record.visible_total,
                    record.mismatch_case_ids,
                    tuple(sorted(record.sources)),
                    tuple(sorted(record.derivations)),
                    record.initial_semantics,
                )
                for record in records.values()
            ),
            key=_rank_key,
        )
    )
    trace = SynthesisTrace(
        tuple(sorted(allowed_operators)),
        initial_expressions,
        counters.candidate_evaluations,
        counters.generated_composites,
        len(records),
        counters.semantic_duplicates,
        counters.pruned_node_limit,
        counters.pruned_depth_limit,
        counters.excluded_unverified_fragments,
        counters.stopped_reason,
    )
    return SynthesisResult(candidates, trace)
