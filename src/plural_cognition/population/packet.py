"""Immutable, canonical hypothesis packets published by population members."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from math import isfinite
from typing import Any, Iterable

from plural_cognition.boolean_world.ast import Expr, variables
from plural_cognition.boolean_world.canonical import (
    CanonicalParseError,
    canonical_text,
    parse_canonical_text,
)
from plural_cognition.boolean_world.world import (
    EvidenceCase,
    InterventionCase,
    PublicTask,
)

PACKET_SCHEMA = "plural-cognition-hypothesis-packet-v1"
MAX_PACKET_BYTES = 1_048_576


class PacketDecodeError(ValueError):
    """Raised when serialized hypothesis-packet data violates the exact schema."""


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
        if type(self.confidence) not in (int, float):
            raise TypeError("confidence must be a plain int or float")
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


@dataclass(frozen=True, slots=True)
class DecodedPacket:
    task: PublicTask
    validated: ValidatedPacket


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


def _canonical_task_payload(task: PublicTask) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "variable_order": list(task.variable_order),
        "evidence": [
            {
                "case_id": case.case_id,
                "assignment": list(case.assignment),
                "output": case.output,
            }
            for case in sorted(task.evidence, key=lambda item: item.case_id)
        ],
        "interventions": [
            {
                "intervention_id": item.intervention_id,
                "variable": item.variable,
                "before_case_id": item.before_case_id,
                "after_case_id": item.after_case_id,
                "changed_output": item.changed_output,
            }
            for item in sorted(
                task.interventions, key=lambda intervention: intervention.intervention_id
            )
        ],
    }


def _canonical_payload(packet: HypothesisPacket, task: PublicTask) -> dict[str, Any]:
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
        "schema": PACKET_SCHEMA,
        "task": _canonical_task_payload(task),
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


def _reject_duplicate_object_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PacketDecodeError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise PacketDecodeError(f"non-finite JSON constant is prohibited: {value}")


def _mapping(value: Any, field: str, keys: set[str]) -> dict[str, Any]:
    if type(value) is not dict:
        raise PacketDecodeError(f"{field} must be a JSON object")
    actual = set(value)
    if actual != keys:
        missing = sorted(keys.difference(actual))
        extra = sorted(actual.difference(keys))
        raise PacketDecodeError(
            f"{field} has wrong keys; missing={missing!r}, extra={extra!r}"
        )
    return value


def _list(value: Any, field: str) -> list[Any]:
    if type(value) is not list:
        raise PacketDecodeError(f"{field} must be a JSON array")
    return value


def _string(value: Any, field: str) -> str:
    if type(value) is not str or not value:
        raise PacketDecodeError(f"{field} must be a non-empty string")
    return value


def _boolean(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise PacketDecodeError(f"{field} must be a Boolean")
    return value


def _string_tuple(value: Any, field: str) -> tuple[str, ...]:
    return tuple(
        _string(item, f"{field}[{index}]")
        for index, item in enumerate(_list(value, field))
    )


def _decode_task(value: Any) -> PublicTask:
    task_data = _mapping(
        value,
        "task",
        {"task_id", "variable_order", "evidence", "interventions"},
    )
    variable_order = _string_tuple(task_data["variable_order"], "task.variable_order")

    evidence: list[EvidenceCase] = []
    for index, raw_case in enumerate(_list(task_data["evidence"], "task.evidence")):
        case = _mapping(
            raw_case,
            f"task.evidence[{index}]",
            {"case_id", "assignment", "output"},
        )
        assignment = tuple(
            _boolean(bit, f"task.evidence[{index}].assignment[{bit_index}]")
            for bit_index, bit in enumerate(
                _list(case["assignment"], f"task.evidence[{index}].assignment")
            )
        )
        evidence.append(
            EvidenceCase(
                _string(case["case_id"], f"task.evidence[{index}].case_id"),
                assignment,
                _boolean(case["output"], f"task.evidence[{index}].output"),
            )
        )

    interventions: list[InterventionCase] = []
    for index, raw_item in enumerate(
        _list(task_data["interventions"], "task.interventions")
    ):
        item = _mapping(
            raw_item,
            f"task.interventions[{index}]",
            {
                "intervention_id",
                "variable",
                "before_case_id",
                "after_case_id",
                "changed_output",
            },
        )
        interventions.append(
            InterventionCase(
                _string(
                    item["intervention_id"],
                    f"task.interventions[{index}].intervention_id",
                ),
                _string(item["variable"], f"task.interventions[{index}].variable"),
                _string(
                    item["before_case_id"],
                    f"task.interventions[{index}].before_case_id",
                ),
                _string(
                    item["after_case_id"],
                    f"task.interventions[{index}].after_case_id",
                ),
                _boolean(
                    item["changed_output"],
                    f"task.interventions[{index}].changed_output",
                ),
            )
        )

    try:
        return PublicTask(
            _string(task_data["task_id"], "task.task_id"),
            variable_order,
            tuple(evidence),
            tuple(interventions),
        )
    except (TypeError, ValueError) as exc:
        raise PacketDecodeError(f"invalid public task: {exc}") from exc


def _decode_expression(value: Any, field: str, variables: tuple[str, ...]) -> Expr:
    text = _string(value, field)
    try:
        return parse_canonical_text(text, allowed_variables=variables)
    except (CanonicalParseError, TypeError, ValueError) as exc:
        raise PacketDecodeError(f"invalid {field}: {exc}") from exc


def _decode_packet_payload(payload: dict[str, Any], task: PublicTask) -> HypothesisPacket:
    allowed_variables = task.variable_order
    fragments: list[HypothesisFragment] = []
    for index, raw_fragment in enumerate(_list(payload["fragments"], "fragments")):
        fragment = _mapping(
            raw_fragment,
            f"fragments[{index}]",
            {
                "fragment_id",
                "expression",
                "role",
                "supporting_case_ids",
                "contradicting_case_ids",
                "predictions",
                "confidence",
            },
        )
        predictions: list[FragmentPrediction] = []
        for prediction_index, raw_prediction in enumerate(
            _list(fragment["predictions"], f"fragments[{index}].predictions")
        ):
            prediction = _mapping(
                raw_prediction,
                f"fragments[{index}].predictions[{prediction_index}]",
                {"case_id", "output"},
            )
            predictions.append(
                FragmentPrediction(
                    _string(
                        prediction["case_id"],
                        f"fragments[{index}].predictions[{prediction_index}].case_id",
                    ),
                    _boolean(
                        prediction["output"],
                        f"fragments[{index}].predictions[{prediction_index}].output",
                    ),
                )
            )

        confidence = fragment["confidence"]
        if type(confidence) not in (int, float):
            raise PacketDecodeError(
                f"fragments[{index}].confidence must be a plain number"
            )
        try:
            role = FragmentRole(_string(fragment["role"], f"fragments[{index}].role"))
        except ValueError as exc:
            raise PacketDecodeError(
                f"fragments[{index}].role is not a recognized role"
            ) from exc

        fragments.append(
            HypothesisFragment(
                fragment_id=_string(
                    fragment["fragment_id"], f"fragments[{index}].fragment_id"
                ),
                expression=_decode_expression(
                    fragment["expression"],
                    f"fragments[{index}].expression",
                    allowed_variables,
                ),
                role=role,
                supporting_case_ids=_string_tuple(
                    fragment["supporting_case_ids"],
                    f"fragments[{index}].supporting_case_ids",
                ),
                contradicting_case_ids=_string_tuple(
                    fragment["contradicting_case_ids"],
                    f"fragments[{index}].contradicting_case_ids",
                ),
                predictions=tuple(predictions),
                confidence=float(confidence),
            )
        )

    try:
        return HypothesisPacket(
            member_id=_string(payload["member_id"], "member_id"),
            complete_candidate=_decode_expression(
                payload["complete_candidate"],
                "complete_candidate",
                allowed_variables,
            ),
            fragments=tuple(fragments),
            counterexample_case_ids=_string_tuple(
                payload["counterexample_case_ids"], "counterexample_case_ids"
            ),
            uncertainty_fragment_ids=_string_tuple(
                payload["uncertainty_fragment_ids"], "uncertainty_fragment_ids"
            ),
        )
    except (TypeError, ValueError) as exc:
        raise PacketDecodeError(f"invalid hypothesis packet: {exc}") from exc


def decode_validated_packet(
    canonical_bytes: bytes,
    *,
    expected_task: PublicTask | None = None,
    expected_sha256: str | None = None,
    max_bytes: int = MAX_PACKET_BYTES,
) -> DecodedPacket:
    """Decode only the exact canonical packet representation.

    The decoder reconstructs the public task and packet, revalidates every
    reference, reserializes the result, and requires byte-for-byte identity.
    """

    if type(canonical_bytes) is not bytes:
        raise TypeError("canonical packet input must be bytes")
    if not canonical_bytes:
        raise PacketDecodeError("canonical packet input must not be empty")
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    if len(canonical_bytes) > max_bytes:
        raise PacketDecodeError("canonical packet exceeds byte limit")

    try:
        text = canonical_bytes.decode("ascii")
    except UnicodeDecodeError as exc:
        raise PacketDecodeError("canonical packet must contain ASCII JSON") from exc

    try:
        raw = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_object_keys,
            parse_constant=_reject_json_constant,
        )
    except PacketDecodeError:
        raise
    except json.JSONDecodeError as exc:
        raise PacketDecodeError(f"invalid JSON: {exc.msg}") from exc

    payload = _mapping(
        raw,
        "packet",
        {
            "schema",
            "task",
            "member_id",
            "complete_candidate",
            "fragments",
            "counterexample_case_ids",
            "uncertainty_fragment_ids",
        },
    )
    if payload["schema"] != PACKET_SCHEMA:
        raise PacketDecodeError(f"unsupported packet schema: {payload['schema']!r}")

    task = _decode_task(payload["task"])
    if expected_task is not None and _canonical_task_payload(task) != _canonical_task_payload(
        expected_task
    ):
        raise PacketDecodeError("serialized public task does not match expected task")

    packet = _decode_packet_payload(payload, task)
    try:
        validated = validate_and_hash_packet(packet, task)
    except (TypeError, ValueError) as exc:
        raise PacketDecodeError(f"packet validation failed: {exc}") from exc

    if validated.canonical_bytes != canonical_bytes:
        raise PacketDecodeError("packet JSON is valid but not in canonical form")

    if expected_sha256 is not None:
        if type(expected_sha256) is not str or len(expected_sha256) != 64:
            raise ValueError("expected_sha256 must be a 64-character hexadecimal string")
        try:
            int(expected_sha256, 16)
        except ValueError as exc:
            raise ValueError(
                "expected_sha256 must be a 64-character hexadecimal string"
            ) from exc
        if validated.canonical_sha256 != expected_sha256.lower():
            raise PacketDecodeError("packet SHA-256 does not match expected digest")

    return DecodedPacket(task, validated)
