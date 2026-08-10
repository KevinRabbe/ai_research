import json

import pytest

from plural_cognition.boolean_world import And, EvidenceCase, PublicTask, Var
from plural_cognition.population import (
    FragmentPrediction,
    FragmentRole,
    HypothesisFragment,
    HypothesisPacket,
    PacketDecodeError,
    decode_validated_packet,
    validate_and_hash_packet,
)


def _task() -> PublicTask:
    return PublicTask(
        task_id="TASK-1",
        variable_order=("A", "B"),
        evidence=(
            EvidenceCase("E0", (False, False), False),
            EvidenceCase("E1", (True, False), False),
            EvidenceCase("E2", (True, True), True),
        ),
        interventions=(),
    )


def _packet() -> HypothesisPacket:
    return HypothesisPacket(
        member_id="M0",
        complete_candidate=And((Var("A"), Var("B"))),
        fragments=(
            HypothesisFragment(
                fragment_id="F1",
                expression=Var("A"),
                role=FragmentRole.ATOM,
                supporting_case_ids=("E2",),
                predictions=(FragmentPrediction("E1", True),),
                confidence=0.75,
            ),
            HypothesisFragment(
                fragment_id="F2",
                expression=Var("B"),
                role=FragmentRole.CONDITION,
                supporting_case_ids=("E2",),
                contradicting_case_ids=("E0",),
                predictions=(FragmentPrediction("E1", False),),
                confidence=0.625,
            ),
        ),
        counterexample_case_ids=("E1",),
        uncertainty_fragment_ids=("F1",),
    )


def _canonical() -> bytes:
    return validate_and_hash_packet(_packet(), _task()).canonical_bytes


def _mutate(mutator) -> bytes:
    payload = json.loads(_canonical().decode("ascii"))
    mutator(payload)
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def test_packet_decoder_exact_round_trip_and_digest_check() -> None:
    original = validate_and_hash_packet(_packet(), _task())
    decoded = decode_validated_packet(
        original.canonical_bytes,
        expected_task=_task(),
        expected_sha256=original.canonical_sha256.upper(),
    )

    assert decoded.task == _task()
    assert decoded.validated.packet == _packet()
    assert decoded.validated.canonical_bytes == original.canonical_bytes
    assert decoded.validated.canonical_sha256 == original.canonical_sha256


def test_packet_decoder_rejects_noncanonical_json_and_duplicate_keys() -> None:
    with pytest.raises(PacketDecodeError, match="not in canonical form"):
        decode_validated_packet(b" " + _canonical())

    duplicate = (
        b'{"schema":"plural-cognition-hypothesis-packet-v1",'
        b'"schema":"plural-cognition-hypothesis-packet-v1"}'
    )
    with pytest.raises(PacketDecodeError, match="duplicate"):
        decode_validated_packet(duplicate)


def test_packet_decoder_rejects_unknown_fields_and_noncanonical_expression() -> None:
    with pytest.raises(PacketDecodeError, match="wrong keys"):
        decode_validated_packet(_mutate(lambda payload: payload.__setitem__("extra", 1)))

    with pytest.raises(PacketDecodeError, match="not in canonical form"):
        decode_validated_packet(
            _mutate(
                lambda payload: payload.__setitem__(
                    "complete_candidate", "AND(B,A)"
                )
            )
        )


def test_packet_decoder_binds_complete_task_and_expected_digest() -> None:
    changed_evidence = _mutate(
        lambda payload: payload["task"]["evidence"][0].__setitem__("output", True)
    )
    with pytest.raises(PacketDecodeError, match="expected task"):
        decode_validated_packet(changed_evidence, expected_task=_task())

    original = validate_and_hash_packet(_packet(), _task())
    with pytest.raises(PacketDecodeError, match="digest"):
        decode_validated_packet(
            original.canonical_bytes,
            expected_sha256="0" * 64,
        )


def test_packet_decoder_rejects_reordering_even_when_semantics_are_unchanged() -> None:
    def reverse_fragments(payload) -> None:
        payload["fragments"].reverse()

    with pytest.raises(PacketDecodeError, match="not in canonical form"):
        decode_validated_packet(_mutate(reverse_fragments))


def test_packet_decoder_rejects_wrong_types_limits_and_non_ascii() -> None:
    with pytest.raises(TypeError, match="bytes"):
        decode_validated_packet(_canonical().decode("ascii"))  # type: ignore[arg-type]
    with pytest.raises(PacketDecodeError, match="byte limit"):
        decode_validated_packet(_canonical(), max_bytes=1)
    with pytest.raises(PacketDecodeError, match="ASCII"):
        decode_validated_packet("é".encode())
    with pytest.raises(ValueError, match="64-character"):
        decode_validated_packet(_canonical(), expected_sha256="bad")
