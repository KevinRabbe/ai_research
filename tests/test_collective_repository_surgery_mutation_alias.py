from plural_cognition.collective.repository_surgery import MutationKind


def test_multi_file_alias_preserves_canonical_mutation_identity() -> None:
    assert MutationKind.MULTI_FILE is MutationKind.MULTI_FILE_BEHAVIOR
    assert MutationKind.MULTI_FILE.value == "multi-file-behavior"
    assert [kind.value for kind in MutationKind].count("multi-file-behavior") == 1
