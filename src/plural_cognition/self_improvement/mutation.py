"""Deterministic one-field mutation neighborhood for reasoning-policy genomes."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .genome import (
    CANDIDATE_EVALUATION_CAPS,
    COMPOSITE_GENERATION_CAPS,
    EXPRESSION_DEPTH_CAPS,
    EXPRESSION_NODE_CAPS,
    POLICY_MODES,
    SYNTHESIS_ROUNDS,
    UNIQUE_CANDIDATE_CAPS,
    PolicyMode,
    ReasoningPolicyGenome,
)


_FIELD_DOMAINS: dict[str, tuple[Any, ...]] = {
    "mode": POLICY_MODES,
    "synthesis_rounds": SYNTHESIS_ROUNDS,
    "max_unique_candidates": UNIQUE_CANDIDATE_CAPS,
    "max_candidate_evaluations": CANDIDATE_EVALUATION_CAPS,
    "max_generated_composites": COMPOSITE_GENERATION_CAPS,
    "max_expression_nodes": EXPRESSION_NODE_CAPS,
    "max_expression_depth": EXPRESSION_DEPTH_CAPS,
}


@dataclass(frozen=True, slots=True)
class MutationRecord:
    parent_sha256: str
    child_sha256: str
    field: str
    old_value: str | int
    new_value: str | int
    generation: int
    ordinal: int

    def __post_init__(self) -> None:
        if len(self.parent_sha256) != 64 or len(self.child_sha256) != 64:
            raise ValueError("mutation hashes must contain 64 characters")
        if self.parent_sha256 == self.child_sha256:
            raise ValueError("mutation must change the normalized genome")
        if self.field not in _FIELD_DOMAINS:
            raise ValueError("mutation field is not part of the genome")
        if self.generation < 1:
            raise ValueError("mutation generation must be positive")
        if self.ordinal < 0:
            raise ValueError("mutation ordinal must not be negative")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "parent_sha256": self.parent_sha256,
            "child_sha256": self.child_sha256,
            "field": self.field,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "generation": self.generation,
            "ordinal": self.ordinal,
        }


@dataclass(frozen=True, slots=True)
class ProposedMutation:
    child: ReasoningPolicyGenome
    record: MutationRecord


def _display(value: object) -> str | int:
    return value.value if isinstance(value, PolicyMode) else value  # type: ignore[return-value]


def _adjacent_values(domain: tuple[Any, ...], value: Any) -> tuple[Any, ...]:
    index = domain.index(value)
    adjacent: list[Any] = []
    if index > 0:
        adjacent.append(domain[index - 1])
    if index + 1 < len(domain):
        adjacent.append(domain[index + 1])
    return tuple(adjacent)


def _active_fields(genome: ReasoningPolicyGenome) -> tuple[str, ...]:
    if genome.normalized().mode.uses_synthesis:
        return tuple(_FIELD_DOMAINS)
    return ("mode",)


def propose_neighbor_mutations(
    parent: ReasoningPolicyGenome,
    *,
    generation: int,
) -> tuple[ProposedMutation, ...]:
    """Return every unique normalized one-step neighbor in deterministic order."""

    if generation < 1:
        raise ValueError("generation must be positive")
    normalized_parent = parent.normalized()
    proposals: dict[str, tuple[ReasoningPolicyGenome, str, object, object]] = {}
    for field in _active_fields(normalized_parent):
        domain = _FIELD_DOMAINS[field]
        old_value = getattr(normalized_parent, field)
        for new_value in _adjacent_values(domain, old_value):
            try:
                raw_child = replace(normalized_parent, **{field: new_value})
                child = raw_child.normalized()
            except ValueError:
                continue
            if child.sha256 == normalized_parent.sha256:
                continue
            proposals.setdefault(
                child.sha256,
                (child, field, old_value, new_value),
            )

    ordered = sorted(
        proposals.values(),
        key=lambda item: (item[0].sha256, item[1], str(item[3])),
    )
    return tuple(
        ProposedMutation(
            child,
            MutationRecord(
                normalized_parent.sha256,
                child.sha256,
                field,
                _display(old_value),
                _display(new_value),
                generation,
                ordinal,
            ),
        )
        for ordinal, (child, field, old_value, new_value) in enumerate(ordered)
    )


def apply_mutation(
    parent: ReasoningPolicyGenome,
    record: MutationRecord,
) -> ReasoningPolicyGenome:
    """Reconstruct a child and verify the complete mutation record."""

    normalized_parent = parent.normalized()
    if normalized_parent.sha256 != record.parent_sha256:
        raise ValueError("mutation record belongs to a different parent")
    domain = _FIELD_DOMAINS[record.field]
    current = getattr(normalized_parent, record.field)
    if _display(current) != record.old_value:
        raise ValueError("mutation old_value does not match parent")
    if record.field == "mode":
        new_value: object = PolicyMode(record.new_value)
    else:
        new_value = record.new_value
    if new_value not in domain:
        raise ValueError("mutation new_value is outside the field domain")
    child = replace(normalized_parent, **{record.field: new_value}).normalized()
    if child.sha256 != record.child_sha256:
        raise ValueError("mutation record child hash does not match reconstruction")
    return child
