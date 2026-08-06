"""Immutable, canonical hypothesis packets published by population members."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from math import isfinite

from plural_cognition.boolean_world.ast import Expr, variables
from plural_cognition.boolean_world.canonical import canonical_text
from plural_cognition.boolean_world.world import PublicTask


class FragmentRole(str, Enum):
    ATOM = "atom"
    CLAUSE = "clause"
    CONDITION = "condition"
    EXCEPTION = "exception"
    REPAIR = "repair"
    COUNTEREXAMPLE = "counterexample"
    ALTERNATIVE = "alternative"


@dataclass(frozen=True, slots=True)
class FragmentPrediction:
    case_id: str
    output: bool

    def __post_init__(self) -> None:
        if not self.case_id:
            raise ValueError("prediction case_id must not be empty")
        if type(self.output) is not bool:
            raise TypeError("prediction output must be bool")


@dataclass(frozen=True, slots=True)
class HypothesisFragment:
    fragment_id: str
    expression: Expr
    role: FragmentRole
    supporting_case_ids: tuple[str, ...] = ()
    contradicting_case_ids: tuple[str, ...] = ()
    predictions: tuple[FragmentPrediction, ...] = ()
    confidence: float = 0.5

    def __post_init__(self) -> None:
        if not self.fragment_id:
            raise ValueError("fragment_id must not be empty")
        if not isinstance(self.role, FragmentRole):
            raise TypeError("role must be FragmentRole")
        _validate_unique_nonempty(self.supporting_case_ids, "supporting_case_ids")
        _validate_unique_nonempty(self.contradicting_case_ids, "contradicting_case_ids")
        if set(self.supporting_case_ids).intersection(self.contradicting_case_ids):
            raise ValueError("a case cannot both support and contradict one fragment")
        prediction_ids = tuple(item.case_id for item in self.predictions)
        _validate_unique_nonempty(prediction_ids, "prediction case IDs")
        confidence = float(self.confidence)
        if not isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be finite and in [0, 1]")


@dataclass(frozen=True, slots=True)
class HypothesisPacket:
    member_id: str
    complete_candidate: Expr
    fragments: tuple[HypothesisFragment, ...]
    counterexample_case_ids: tuple[str, ...] = ()
    uncertainty_fragment_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.member_id:
            raise ValueError("member_id must not be empty")
        if not self.fragments:
            raise ValueError("a hypothesis packet requires at least one fragment")
        fragment_ids = tuple(fragment.fragment_id for fragment in self.fragments)
        _validate_unique_nonempty(fragment_ids, "fragment IDs")
        _validate_unique_nonempty(self.counterexample_case_ids, "counterexample_case_ids")
        _validate_unique_nonempty(self.uncertainty_fragment_ids, "uncertainty_fragment_ids")
        unknown = set(self.uncertainty_fragment_ids).difference(fragment_ids)
        if unknown:
            raise ValueError(
                f"uncertainty_fragment_ids reference unknown fragments: {sorted(unknown)!r}"
            )


@dataclass(frozen=True, slots=True)
class ValidatedPacket:
    packet: HypothesisPacket
    task_id: str
    canonical_sha256: str
    canonical_bytes: bytes


def _validate_unique_nonempty(values: tuple[str, ...], field: str) -> None:
    if any(not value for value in values):
        raise ValueError(f"{field} must not contain empty strings")
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must not contain duplicates")


def _validate_expression_variables(
    expression: Expr, allowed_variables: set[str], field: str
) -> None:
    unknown = set(variables(expression)).difference(allowed_variables)
    if unknown:
        raise ValueError(f"{field} references out-of-task variables: {sorted(unknown)!r}")


def _canonical_payload(packet: HypothesisPacket, task: PublicTask) -> dict:
    fragments = []
    for fragment in sorted(packet.fragments, key=lambda item: item.fragment_id):
        fragments.append(
            {
                "fragment_id": fragment.fragment_id,
                "expression": canonical_text(fragment.expression),
                "role": fragment.role.value,
                "supporting_case_ids": sorted(fragment.supporting_case_ids),
                "contradicting_case_ids": sorted(fragment.contradicting_case_ids),
                "predictions": [
                    {"case_id": prediction.case_id, "output": prediction.output}
                    for prediction in sorted(
                        fragment.predictions, key=lambda item: item.case_id
                    )
                ],
                "confidence": float(fragment.confidence),
            }
        )

    return {
        "schema": "plural-cognition-hypothesis-packet-v1",
        "task_id": task.task_id,
        "variable_order": list(task.variable_order),
        "member_id": packet.member_id,
        "complete_candidate": canonical_text(packet.complete_candidate),
        "fragments": fragments,
        "counterexample_case_ids": sorted(packet.counterexample_case_ids),
        "uncertainty_fragment_ids": sorted(packet.uncertainty_fragment_ids),
    }


def validate_and_hash_packet(
    packet: HypothesisPacket, task: PublicTask
) -> ValidatedPacket:
    """Validate packet references and return its canonical immutable representation."""

    allowed_variables = set(task.variable_order)
    case_ids = {case.case_id for case in task.evidence}
    _validate_expression_variables(
        packet.complete_candidate, allowed_variables, "complete_candidate"
    )

    fragment_ids = {fragment.fragment_id for fragment in packet.fragments}
    for fragment in packet.fragments:
        _validate_expression_variables(
            fragment.expression,
            allowed_variables,
            f"fragment {fragment.fragment_id!r}",
        )
        referenced_cases = (
            set(fragment.supporting_case_ids)
            | set(fragment.contradicting_case_ids)
            | {prediction.case_id for prediction in fragment.predictions}
        )
        unknown_cases = referenced_cases.difference(case_ids)
        if unknown_cases:
            raise ValueError(
                f"fragment {fragment.fragment_id!r} references unknown cases: "
                f"{sorted(unknown_cases)!r}"
            )

    unknown_counterexamples = set(packet.counterexample_case_ids).difference(case_ids)
    if unknown_counterexamples:
        raise ValueError(
            "counterexample_case_ids reference unknown cases: "
            f"{sorted(unknown_counterexamples)!r}"
        )
    if not set(packet.uncertainty_fragment_ids).issubset(fragment_ids):
        raise AssertionError("packet uncertainty validation contract was bypassed")

    payload = _canonical_payload(packet, task)
    canonical_bytes = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    digest = sha256(canonical_bytes).hexdigest()
    return ValidatedPacket(packet, task.task_id, digest, canonical_bytes)
