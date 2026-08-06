from plural_cognition.boolean_world import decode_mechanism, encode_mechanism
from plural_cognition.training_data import (
    TrainingDataConfig,
    build_supervised_example,
    derive_example_seed,
    example_at,
    iter_causal_examples,
)


def test_split_seed_derivation_is_deterministic_and_disjoint() -> None:
    assert derive_example_seed(7, "train", 3) == derive_example_seed(7, "train", 3)
    assert len(
        {
            derive_example_seed(7, split, 3)
            for split in ("train", "validation", "test")
        }
    ) == 3
    assert derive_example_seed(7, "train", 3) != derive_example_seed(7, "train", 4)


def test_supervised_target_is_separate_from_public_payload() -> None:
    example = build_supervised_example(12345)
    payload = example.public.to_payload()

    assert "target" not in payload
    assert "semantic" not in payload
    assert example.public.task_id.startswith("BW1S-")
    assert decode_mechanism(
        encode_mechanism(example.target),
        allowed_variables=example.public.variable_order,
    ) == example.target
    assert len(example.causal().token_ids) <= 256


def test_indexed_stream_is_reproducible_without_mutable_rng_state() -> None:
    config = TrainingDataConfig(base_seed=99)
    direct = tuple(example_at("train", index, config).causal() for index in range(3))
    streamed = tuple(iter_causal_examples("train", count=3, config=config))

    assert direct == streamed
    assert direct == tuple(iter_causal_examples("train", count=3, config=config))


def test_splits_produce_different_examples() -> None:
    config = TrainingDataConfig(base_seed=123)
    train = example_at("train", 0, config)
    validation = example_at("validation", 0, config)
    test = example_at("test", 0, config)

    assert len({train.seed, validation.seed, test.seed}) == 3
    assert len(
        {
            train.public.task_id,
            validation.public.task_id,
            test.public.task_id,
        }
    ) == 3
