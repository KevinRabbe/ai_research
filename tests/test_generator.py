from plural_cognition.boolean_world import (
    Const,
    GenerationConfig,
    Var,
    canonical_text,
    depth,
    generate_mechanism,
    semantic_key,
    variables,
)


def test_generation_is_seed_deterministic() -> None:
    config = GenerationConfig(variable_count=6, min_atoms=3, max_atoms=5, max_depth=5)
    first = generate_mechanism(12345, config)
    second = generate_mechanism(12345, config)
    assert first == second
    assert canonical_text(first) == canonical_text(second)


def test_generated_mechanisms_satisfy_contracts_over_many_seeds() -> None:
    config = GenerationConfig(variable_count=6, min_atoms=2, max_atoms=5, max_depth=5)
    outputs: set[str] = set()

    for seed in range(100):
        expr = generate_mechanism(seed, config)
        assert not isinstance(expr, (Const, Var))
        assert depth(expr) <= config.max_depth
        assert len(variables(expr)) >= 2

        order, bitset = semantic_key(expr, config.variable_names())
        assignment_count = 1 << len(order)
        assert bitset != 0
        assert bitset != (1 << assignment_count) - 1
        outputs.add(canonical_text(expr))

    assert len(outputs) >= 50


def test_invalid_generation_config_is_rejected() -> None:
    try:
        GenerationConfig(variable_count=1)
    except ValueError as exc:
        assert "variable_count" in str(exc)
    else:
        raise AssertionError("invalid config was accepted")
