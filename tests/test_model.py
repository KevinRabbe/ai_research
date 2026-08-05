import gc

import pytest
import torch

from plural_cognition.boolean_world import (
    And,
    EvidenceCase,
    PublicTask,
    Var,
    encode_causal_example,
)
from plural_cognition.model import (
    MODEL_CONFIGS,
    PC_4M,
    DecoderConfig,
    PluralDecoder,
    causal_lm_loss,
    collate_causal_examples,
    expected_parameter_count,
)

EXPECTED_PARAMETERS = {
    "PC-4M": 4_741_120,
    "PC-10M": 9_859_840,
    "PC-18M": 17_731_584,
}


def test_exact_parameter_counts() -> None:
    for config in MODEL_CONFIGS:
        model = PluralDecoder(config)
        assert expected_parameter_count(config) == EXPECTED_PARAMETERS[
            config.name
        ]
        assert model.parameter_count() == EXPECTED_PARAMETERS[config.name]
        del model
        gc.collect()


def test_config_rejects_non_64_head_dimension() -> None:
    with pytest.raises(ValueError):
        DecoderConfig("bad", layers=1, d_model=96, heads=2)


def test_forward_is_deterministic_and_has_expected_shape() -> None:
    torch.manual_seed(123)
    model = PluralDecoder(PC_4M).eval()
    input_ids = torch.randint(0, PC_4M.vocab_size, (2, 12))

    first = model(input_ids)
    second = model(input_ids)

    assert first.shape == (2, 12, PC_4M.vocab_size)
    assert torch.equal(first, second)


def test_padding_does_not_change_valid_prefix_logits() -> None:
    torch.manual_seed(1)
    model = PluralDecoder(
        DecoderConfig("smoke", layers=1, d_model=64, heads=1)
    ).eval()
    unpadded = torch.tensor([[1, 2, 3]])
    padded = torch.tensor([[1, 2, 3, 0, 0]])
    mask = torch.tensor([[True, True, True, False, False]])

    plain_logits = model(unpadded)
    padded_logits = model(padded, mask)

    assert torch.isfinite(padded_logits).all()
    assert torch.allclose(
        plain_logits,
        padded_logits[:, :3],
        atol=1e-6,
    )


def test_cpu_forward_backward_and_answer_only_loss() -> None:
    task = PublicTask(
        "smoke",
        ("V0", "V1"),
        (
            EvidenceCase("A", (False, False), False),
            EvidenceCase("B", (True, False), True),
        ),
        (),
    )
    examples = (
        encode_causal_example(
            task,
            And((Var("V0"), Var("V1"))),
        ),
        encode_causal_example(task, Var("V0")),
    )
    input_ids, attention_mask, label_mask = collate_causal_examples(
        examples
    )

    torch.manual_seed(7)
    model = PluralDecoder(
        DecoderConfig("smoke", layers=2, d_model=64, heads=1)
    )
    logits = model(input_ids, attention_mask)
    loss = causal_lm_loss(logits, input_ids, label_mask)

    assert torch.isfinite(loss)
    loss.backward()
    assert model.token_embedding.weight.grad is not None
    assert torch.isfinite(model.token_embedding.weight.grad).all()


def test_model_rejects_invalid_inputs() -> None:
    model = PluralDecoder(
        DecoderConfig("smoke", layers=1, d_model=64, heads=1)
    )

    with pytest.raises(TypeError):
        model(torch.ones((1, 2), dtype=torch.float32))
    with pytest.raises(IndexError):
        model(torch.tensor([[0, model.config.vocab_size]]))
    with pytest.raises(TypeError):
        model(torch.tensor([[1, 2]]), torch.ones((1, 2)))


def test_all_three_configs_complete_cpu_forward_backward() -> None:
    for index, config in enumerate(MODEL_CONFIGS):
        torch.manual_seed(100 + index)
        model = PluralDecoder(config)
        input_ids = torch.randint(0, config.vocab_size, (1, 8))
        attention_mask = torch.ones_like(input_ids, dtype=torch.bool)
        label_mask = torch.zeros_like(input_ids, dtype=torch.bool)
        label_mask[:, 4:] = True

        loss = causal_lm_loss(
            model(input_ids, attention_mask),
            input_ids,
            label_mask,
        )
        assert torch.isfinite(loss)
        loss.backward()
        assert model.token_embedding.weight.grad is not None
        assert torch.isfinite(model.token_embedding.weight.grad).all()

        del model
        gc.collect()
