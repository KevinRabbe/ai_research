import pytest

from plural_cognition.self_improvement import (
    IMMUTABLE_PARENT_GENOME,
    PolicyMode,
    ReasoningPolicyGenome,
    apply_mutation,
    propose_neighbor_mutations,
)


def test_parent_neighbors_are_deterministic_and_one_step() -> None:
    first = propose_neighbor_mutations(IMMUTABLE_PARENT_GENOME, generation=1)
    second = propose_neighbor_mutations(IMMUTABLE_PARENT_GENOME, generation=1)

    assert first == second
    assert len(first) == 1
    proposal = first[0]
    assert proposal.child.mode is PolicyMode.VERIFIED_FRAGMENT_SELECTION
    assert proposal.record.field == "mode"
    assert proposal.record.old_value == PolicyMode.COMPLETE_SELECTION.value
    assert proposal.record.new_value == PolicyMode.VERIFIED_FRAGMENT_SELECTION.value
    assert apply_mutation(IMMUTABLE_PARENT_GENOME, proposal.record) == proposal.child


def test_synthesis_neighbors_mutate_only_active_fields() -> None:
    parent = ReasoningPolicyGenome(PolicyMode.VERIFIED_SYNTHESIS)
    proposals = propose_neighbor_mutations(parent, generation=3)

    assert proposals
    assert len({item.child.sha256 for item in proposals}) == len(proposals)
    assert [item.record.ordinal for item in proposals] == list(range(len(proposals)))
    for proposal in proposals:
        assert proposal.record.parent_sha256 == parent.sha256
        assert proposal.record.child_sha256 == proposal.child.sha256
        assert apply_mutation(parent, proposal.record) == proposal.child


def test_mutation_record_rejects_unrelated_parent() -> None:
    proposal = propose_neighbor_mutations(IMMUTABLE_PARENT_GENOME, generation=1)[0]
    other = ReasoningPolicyGenome(PolicyMode.VERIFIED_SYNTHESIS)

    with pytest.raises(ValueError, match="different parent"):
        apply_mutation(other, proposal.record)
