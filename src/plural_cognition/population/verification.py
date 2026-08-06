"""Visible-only verification for member candidates and proof-carrying fragments."""

from __future__ import annotations

from dataclasses import dataclass

from plural_cognition.boolean_world.canonical import canonical_text
from plural_cognition.boolean_world.semantics import evaluate
from plural_cognition.boolean_world.world import (
    PublicTask,
    VisibleEvaluation,
    assignment_mapping,
    evaluate_visible,
)

from .packet import ValidatedPacket, validate_and_hash_packet


@dataclass(frozen=True, slots=True)
class FragmentVisibleAudit:
    fragment_id: str
    canonical_expression: str
    matched_visible: int
    visible_total: int
    mismatch_case_ids: tuple[str, ...]
    metadata_errors: tuple[str, ...]

    @property
    def visible_accuracy(self) -> float:
        if self.visible_total == 0:
            return 0.0
        return self.matched_visible / self.visible_total

    @property
    def metadata_verified(self) -> bool:
        return not self.metadata_errors


@dataclass(frozen=True, slots=True)
class PacketVisibleAudit:
    member_id: str
    packet_sha256: str
    candidate: VisibleEvaluation
    fragments: tuple[FragmentVisibleAudit, ...]
    counterexample_errors: tuple[str, ...]

    @property
    def metadata_verified(self) -> bool:
        return not self.counterexample_errors and all(
            fragment.metadata_verified for fragment in self.fragments
        )

    @property
    def verified_fragment_ids(self) -> tuple[str, ...]:
        return tuple(
            fragment.fragment_id
            for fragment in self.fragments
            if fragment.metadata_verified
        )


def audit_visible_packet(
    validated: ValidatedPacket,
    task: PublicTask,
) -> PacketVisibleAudit:
    """Audit packet claims using only evidence visible to every member.

    This function never receives a qualification target or hidden assignments.
    A supporting-case claim means the fragment agrees with the observed output on
    that case. A contradicting-case claim means it disagrees. A prediction claim
    must equal the fragment's own deterministic output on the referenced case.
    """

    recomputed = validate_and_hash_packet(validated.packet, task)
    if (
        recomputed.canonical_sha256 != validated.canonical_sha256
        or recomputed.canonical_bytes != validated.canonical_bytes
    ):
        raise ValueError("validated packet does not belong to the supplied public task")

    packet = recomputed.packet
    cases = {case.case_id: case for case in task.evidence}
    assignments = {
        case.case_id: assignment_mapping(task.variable_order, case.assignment)
        for case in task.evidence
    }
    candidate = evaluate_visible(packet.complete_candidate, task)

    fragment_audits: list[FragmentVisibleAudit] = []
    for fragment in sorted(packet.fragments, key=lambda item: item.fragment_id):
        outputs = {
            case_id: evaluate(fragment.expression, assignment)
            for case_id, assignment in assignments.items()
        }
        mismatches = tuple(
            sorted(
                case_id
                for case_id, output in outputs.items()
                if output != cases[case_id].output
            )
        )
        errors: list[str] = []

        for case_id in fragment.supporting_case_ids:
            if outputs[case_id] != cases[case_id].output:
                errors.append(f"support claim fails on {case_id}")
        for case_id in fragment.contradicting_case_ids:
            if outputs[case_id] == cases[case_id].output:
                errors.append(f"contradiction claim fails on {case_id}")
        for prediction in fragment.predictions:
            if outputs[prediction.case_id] != prediction.output:
                errors.append(f"prediction claim fails on {prediction.case_id}")

        fragment_audits.append(
            FragmentVisibleAudit(
                fragment.fragment_id,
                canonical_text(fragment.expression),
                len(task.evidence) - len(mismatches),
                len(task.evidence),
                mismatches,
                tuple(sorted(errors)),
            )
        )

    candidate_outputs = {
        case_id: evaluate(packet.complete_candidate, assignment)
        for case_id, assignment in assignments.items()
    }
    counterexample_errors = tuple(
        sorted(
            f"counterexample claim fails on {case_id}"
            for case_id in packet.counterexample_case_ids
            if candidate_outputs[case_id] == cases[case_id].output
        )
    )

    return PacketVisibleAudit(
        packet.member_id,
        recomputed.canonical_sha256,
        candidate,
        tuple(fragment_audits),
        counterexample_errors,
    )
