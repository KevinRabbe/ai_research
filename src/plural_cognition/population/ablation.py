"""Executable matched-input ablations for population selection and synthesis."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Sequence

from plural_cognition.boolean_world.ast import Expr, depth, node_count
from plural_cognition.boolean_world.canonical import canonical_text, normalize
from plural_cognition.boolean_world.semantics import semantic_key
from plural_cognition.boolean_world.world import PublicTask, evaluate_visible

from .graph import SourceRef
from .packet import ValidatedPacket
from .synthesis import SynthesisConfig, SynthesisResult, synthesize_visible
from .verification import audit_visible_packet


class AblationMode(str, Enum):
    COMPLETE_SELECTION = "complete-selection"
    VERIFIED_FRAGMENT_SELECTION = "verified-fragment-selection"
    VERIFIED_SYNTHESIS = "verified-synthesis"
    UNVERIFIED_SYNTHESIS = "unverified-synthesis"


@dataclass(frozen=True, slots=True)
class SelectedCandidate:
    candidate_id: str
    expression: Expr
    canonical_expression: str
    visible_matched: int
    visible_total: int
    sources: tuple[SourceRef, ...]
    initial_complete_semantics: bool

    @property
    def visible_accuracy(self) -> float:
        return self.visible_matched / self.visible_total


@dataclass(frozen=True, slots=True)
class AblationOutcome:
    mode: AblationMode
    selected: SelectedCandidate
    generated_composites: int
    candidate_evaluations: int
    external_score: float | None = None


ExternalScore = Callable[[Expr], float]


def _candidate_id(bitset: int, variable_count: int) -> str:
    digits = max(1, ((1 << variable_count) + 3) // 4)
    return f"candidate:{bitset:0{digits}x}"


def _rank(candidate: SelectedCandidate) -> tuple:
    return (
        -candidate.visible_matched,
        node_count(candidate.expression),
        depth(candidate.expression),
        candidate.canonical_expression,
        candidate.candidate_id,
    )


def select_initial_candidates(
    task: PublicTask,
    packets: Sequence[ValidatedPacket],
    *,
    include_verified_fragments: bool,
) -> SelectedCandidate:
    """Select from supplied complete answers and optionally verified fragments."""

    if not packets:
        raise ValueError("at least one validated packet is required")
    records: dict[int, tuple[Expr, set[SourceRef], bool]] = {}

    def add(expression: Expr, source: SourceRef, complete: bool) -> None:
        normalized = normalize(expression)
        _, bitset = semantic_key(normalized, task.variable_order)
        if bitset not in records:
            records[bitset] = (normalized, {source}, complete)
            return
        existing_expression, sources, existing_complete = records[bitset]
        sources.add(source)
        representative = min(
            (existing_expression, normalized),
            key=canonical_text,
        )
        records[bitset] = (
            representative,
            sources,
            existing_complete or complete,
        )

    for validated in sorted(packets, key=lambda item: item.canonical_sha256):
        packet = validated.packet
        add(
            packet.complete_candidate,
            SourceRef(packet.member_id, validated.canonical_sha256, "complete_candidate"),
            True,
        )
        if not include_verified_fragments:
            continue
        verified = set(audit_visible_packet(validated, task).verified_fragment_ids)
        for fragment in packet.fragments:
            if fragment.fragment_id not in verified:
                continue
            add(
                fragment.expression,
                SourceRef(packet.member_id, validated.canonical_sha256, fragment.fragment_id),
                False,
            )

    candidates = []
    for bitset, (expression, sources, complete) in records.items():
        visible = evaluate_visible(expression, task)
        if not visible.valid:
            raise ValueError("validated candidate failed visible evaluation")
        candidates.append(
            SelectedCandidate(
                _candidate_id(bitset, len(task.variable_order)),
                expression,
                canonical_text(expression),
                visible.matched,
                visible.total,
                tuple(sorted(sources)),
                complete,
            )
        )
    return min(candidates, key=_rank)


def _from_synthesis(result: SynthesisResult) -> SelectedCandidate:
    best = result.best
    return SelectedCandidate(
        best.candidate_id,
        best.expression,
        best.canonical_expression,
        best.visible_matched,
        best.visible_total,
        best.sources,
        not best.novel_semantic_composition,
    )


def run_ablation(
    task: PublicTask,
    packets: Sequence[ValidatedPacket],
    mode: AblationMode,
    *,
    synthesis_config: SynthesisConfig | None = None,
    external_score: ExternalScore | None = None,
) -> AblationOutcome:
    """Fix one ablation output using visible information, then score it externally."""

    if mode is AblationMode.COMPLETE_SELECTION:
        selected = select_initial_candidates(
            task, packets, include_verified_fragments=False
        )
        generated = 0
        evaluations = len(
            {
                semantic_key(packet.packet.complete_candidate, task.variable_order)[1]
                for packet in packets
            }
        )
    elif mode is AblationMode.VERIFIED_FRAGMENT_SELECTION:
        selected = select_initial_candidates(
            task, packets, include_verified_fragments=True
        )
        generated = 0
        evaluations = 1
        # Exact count is intentionally recomputed through the public candidate set.
        semantics = set()
        for packet in packets:
            semantics.add(
                semantic_key(packet.packet.complete_candidate, task.variable_order)[1]
            )
            verified = set(audit_visible_packet(packet, task).verified_fragment_ids)
            semantics.update(
                semantic_key(fragment.expression, task.variable_order)[1]
                for fragment in packet.packet.fragments
                if fragment.fragment_id in verified
            )
        evaluations = len(semantics)
    elif mode in (
        AblationMode.VERIFIED_SYNTHESIS,
        AblationMode.UNVERIFIED_SYNTHESIS,
    ):
        base = synthesis_config or SynthesisConfig()
        config = SynthesisConfig(
            max_rounds=base.max_rounds,
            max_unique_candidates=base.max_unique_candidates,
            max_candidate_evaluations=base.max_candidate_evaluations,
            max_generated_composites=base.max_generated_composites,
            max_expression_nodes=base.max_expression_nodes,
            max_expression_depth=base.max_expression_depth,
            require_verified_fragment_metadata=(
                mode is AblationMode.VERIFIED_SYNTHESIS
            ),
        )
        result = synthesize_visible(task, packets, config)
        selected = _from_synthesis(result)
        generated = result.trace.generated_composites
        evaluations = result.trace.candidate_evaluations
    else:
        raise ValueError(f"unsupported ablation mode: {mode!r}")

    score = None if external_score is None else float(external_score(selected.expression))
    return AblationOutcome(mode, selected, generated, evaluations, score)


def run_ablation_suite(
    task: PublicTask,
    packets: Sequence[ValidatedPacket],
    *,
    synthesis_config: SynthesisConfig | None = None,
    external_score: ExternalScore | None = None,
) -> tuple[AblationOutcome, ...]:
    return tuple(
        run_ablation(
            task,
            packets,
            mode,
            synthesis_config=synthesis_config,
            external_score=external_score,
        )
        for mode in AblationMode
    )
