from plural_cognition.boolean_world import And, EvidenceCase, PublicTask, Var
from plural_cognition.population import audit_visible_packet, extract_packet_from_candidate


def _task() -> PublicTask:
    return PublicTask(
        "TASK-EXTRACT",
        ("A", "B"),
        (
            EvidenceCase("E00", (False, False), False),
            EvidenceCase("E01", (False, True), False),
            EvidenceCase("E10", (True, False), False),
            EvidenceCase("E11", (True, True), True),
        ),
        (),
    )


def test_extractor_builds_verified_subexpression_fragments() -> None:
    extracted = extract_packet_from_candidate(
        "M0", And((Var("A"), Var("B"))), _task()
    )
    packet = extracted.validated.packet

    assert extracted.extracted_fragment_count == 2
    assert extracted.candidate_visible_accuracy == 1.0
    assert {fragment.expression for fragment in packet.fragments} == {Var("A"), Var("B")}
    assert audit_visible_packet(extracted.validated, _task()).metadata_verified is True


def test_extractor_records_wrong_candidate_counterexample() -> None:
    extracted = extract_packet_from_candidate("M0", Var("A"), _task())

    assert extracted.extracted_fragment_count == 1
    assert extracted.validated.packet.counterexample_case_ids == ("E10",)
    assert audit_visible_packet(extracted.validated, _task()).metadata_verified is True


def test_extraction_is_deterministic_and_bounded() -> None:
    candidate = And((Var("A"), Var("B")))
    first = extract_packet_from_candidate("M0", candidate, _task(), max_fragments=1)
    second = extract_packet_from_candidate("M0", candidate, _task(), max_fragments=1)

    assert first == second
    assert first.extracted_fragment_count == 1
