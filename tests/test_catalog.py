from plural_cognition.boolean_world import GenerationConfig, build_catalog


def test_catalog_is_deterministic_and_semantically_unique() -> None:
    config = GenerationConfig(variable_count=6, min_atoms=2, max_atoms=5, max_depth=5)
    first = build_catalog(99, 64, config)
    second = build_catalog(99, 64, config)

    assert first.variable_order == config.variable_names()
    assert [entry.semantic_bitset for entry in first.entries] == [
        entry.semantic_bitset for entry in second.entries
    ]
    assert [entry.canonical for entry in first.entries] == [entry.canonical for entry in second.entries]
    assert len({entry.semantic_bitset for entry in first.entries}) == 64
