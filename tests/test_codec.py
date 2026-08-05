import pytest

from plural_cognition.boolean_world import (
    And,
    Const,
    EvidenceCase,
    InterventionCase,
    Ite,
    Not,
    Or,
    PublicTask,
    Var,
    normalize,
)
from plural_cognition.boolean_world.codec import (
    CodecError,
    VOCAB_SIZE,
    decode_mechanism,
    decode_public_task,
    decode_tokens,
    encode_causal_example,
    encode_mechanism,
    encode_public_task,
    encode_tokens,
)


def _task() -> PublicTask:
    return PublicTask(
        "BW1-deadbeef",
        ("V0", "V1", "V2"),
        (
            EvidenceCase("E0000", (False, False, False), False),
            EvidenceCase("E0001", (True, False, False), True),
            EvidenceCase("E0007", (True, True, True), False),
        ),
        (
            InterventionCase(
                "I000", "V0", "E0000", "E0001", True
            ),
        ),
    )


def test_vocabulary_is_fixed_and_below_the_planned_96_tokens() -> None:
    assert VOCAB_SIZE == 75
    assert VOCAB_SIZE <= 96


def test_token_codec_rejects_unknown_values() -> None:
    with pytest.raises(CodecError):
        encode_tokens(["NOPE"])
    with pytest.raises(CodecError):
        decode_tokens([VOCAB_SIZE])
    with pytest.raises(CodecError):
        decode_tokens([True])


def test_public_task_round_trip_preserves_model_visible_semantics() -> None:
    encoded = encode_public_task(_task())
    decoded = decode_public_task(encoded)

    assert decoded.variable_order == _task().variable_order
    assert [
        (case.assignment, case.output) for case in decoded.evidence
    ] == [
        (case.assignment, case.output) for case in _task().evidence
    ]
    assert [
        (
            item.variable,
            item.before_case_id,
            item.after_case_id,
            item.changed_output,
        )
        for item in decoded.interventions
    ] == [("V0", "C0", "C1", True)]
    assert len(encoded) < 256


def test_task_encoding_is_independent_of_opaque_ids() -> None:
    original = _task()
    renamed = PublicTask(
        "other",
        original.variable_order,
        tuple(
            EvidenceCase(f"X{index}", case.assignment, case.output)
            for index, case in enumerate(original.evidence)
        ),
        (InterventionCase("Y", "V0", "X0", "X1", True),),
    )

    assert encode_public_task(original) == encode_public_task(renamed)


def test_task_decoder_rejects_trailing_and_truncated_sequences() -> None:
    encoded = encode_public_task(_task())
    with pytest.raises(CodecError):
        decode_public_task(encoded[:-1])
    with pytest.raises(CodecError):
        decode_public_task((*encoded, encoded[-1]))


def test_task_decoder_rejects_out_of_range_intervention_index() -> None:
    tokens = list(decode_tokens(encode_public_task(_task())))
    after = tokens.index("<AFTER>")
    tokens[after + 1] = "N31"

    with pytest.raises(CodecError):
        decode_public_task(encode_tokens(tokens))


def test_task_encoder_enforces_context_limit() -> None:
    with pytest.raises(CodecError):
        encode_public_task(_task(), max_tokens=10)


def test_mechanism_round_trip_is_canonical() -> None:
    expr = And((Var("V1"), Var("V0"), Var("V1")))

    assert decode_mechanism(
        encode_mechanism(expr),
        allowed_variables=("V0", "V1"),
    ) == normalize(expr)


def test_mechanism_codec_supports_all_node_types() -> None:
    expr = Ite(
        Var("V0"),
        Or((Var("V1"), Not(Var("V2")))),
        And((Const(True), Var("V2"))),
    )

    decoded = decode_mechanism(
        encode_mechanism(expr),
        allowed_variables=("V0", "V1", "V2"),
    )
    assert decoded == normalize(expr)


def test_decoder_rejects_unknown_variable_before_normalization() -> None:
    raw = encode_tokens(
        (
            "<BOS>",
            "<ANSWER>",
            "<OR>",
            "N2",
            "<TRUE>",
            "V19",
            "<EOS>",
        )
    )

    with pytest.raises(CodecError):
        decode_mechanism(raw, allowed_variables=("V0",))


def test_mechanism_decoder_rejects_wrong_arity_and_trailing_tokens() -> None:
    malformed = encode_tokens(
        ("<BOS>", "<ANSWER>", "<AND>", "N0", "<EOS>")
    )
    with pytest.raises(CodecError):
        decode_mechanism(malformed)

    valid = encode_mechanism(Var("V0"))
    with pytest.raises(CodecError):
        decode_mechanism((*valid, valid[-1]))


def test_mechanism_decoder_rejects_missing_eos() -> None:
    valid = encode_mechanism(Var("V0"))
    with pytest.raises(CodecError):
        decode_mechanism(valid[:-1])


def test_full_public_task_shape_fits_256_tokens() -> None:
    variable_order = tuple(f"V{index}" for index in range(10))
    assignments = tuple(
        tuple(
            bool((value >> (9 - index)) & 1)
            for index in range(10)
        )
        for value in range(16)
    )
    evidence = tuple(
        EvidenceCase(f"E{index:04d}", assignment, bool(index & 1))
        for index, assignment in enumerate(assignments)
    )
    interventions = (
        InterventionCase("I0", "V9", "E0000", "E0001", True),
        InterventionCase("I1", "V9", "E0002", "E0003", True),
        InterventionCase("I2", "V9", "E0004", "E0005", True),
    )

    encoded = encode_public_task(
        PublicTask("BW1-max", variable_order, evidence, interventions)
    )
    assert len(encoded) == 251
    assert len(encoded) <= 256


def test_codec_rejects_inconsistent_intervention_metadata() -> None:
    bad = PublicTask(
        "bad",
        ("V0", "V1"),
        (
            EvidenceCase("A", (False, False), False),
            EvidenceCase("B", (True, False), True),
        ),
        (InterventionCase("I", "V1", "A", "B", True),),
    )

    with pytest.raises(CodecError):
        encode_public_task(bad)


def test_causal_example_has_one_sequence_and_answer_only_loss_mask() -> None:
    answer = And((Var("V0"), Not(Var("V1"))))
    example = encode_causal_example(_task(), answer)
    tokens = decode_tokens(example.token_ids)

    assert tokens[0] == "<BOS>"
    assert tokens[-1] == "<EOS>"
    assert tokens.count("<BOS>") == 1
    assert tokens.count("<EOS>") == 1
    assert tokens[example.answer_start] == "<ANSWER>"
    assert not any(example.label_mask[: example.answer_start + 1])
    assert all(example.label_mask[example.answer_start + 1 :])


def test_default_six_variable_training_shape_fits_256_tokens() -> None:
    variable_order = tuple(f"V{index}" for index in range(6))
    evidence = tuple(
        EvidenceCase(
            f"E{value:04d}",
            tuple(
                bool((value >> (5 - index)) & 1)
                for index in range(6)
            ),
            bool(value & 1),
        )
        for value in range(16)
    )
    interventions = (
        InterventionCase("I0", "V5", "E0000", "E0001", True),
        InterventionCase("I1", "V5", "E0002", "E0003", True),
        InterventionCase("I2", "V5", "E0004", "E0005", True),
    )
    answer = Ite(
        Var("V0"),
        And((Var("V1"), Not(Var("V2")))),
        Or((Var("V3"), And((Var("V4"), Var("V5"))))),
    )

    example = encode_causal_example(
        PublicTask(
            "BW1-default-max",
            variable_order,
            evidence,
            interventions,
        ),
        answer,
    )
    assert len(example.token_ids) <= 256


def test_large_task_and_complex_answer_require_larger_context() -> None:
    variable_order = tuple(f"V{index}" for index in range(10))
    evidence = tuple(
        EvidenceCase(
            f"E{value:04d}",
            tuple(
                bool((value >> (9 - index)) & 1)
                for index in range(10)
            ),
            bool(value & 1),
        )
        for value in range(16)
    )
    interventions = (
        InterventionCase("I0", "V9", "E0000", "E0001", True),
        InterventionCase("I1", "V9", "E0002", "E0003", True),
        InterventionCase("I2", "V9", "E0004", "E0005", True),
    )
    answer = Ite(
        Var("V0"),
        And((Var("V1"), Var("V2"))),
        Or((Var("V3"), Var("V4"))),
    )

    with pytest.raises(CodecError):
        encode_causal_example(
            PublicTask("BW1-large", variable_order, evidence, interventions),
            answer,
            max_tokens=256,
        )
