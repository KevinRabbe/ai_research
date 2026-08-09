from dataclasses import replace

import pytest

from plural_cognition.self_improvement import (
    IMMUTABLE_PARENT_GENOME,
    PolicyMode,
    ReasoningPolicyGenome,
)


def test_selection_modes_canonicalize_inactive_synthesis_fields() -> None:
    noisy = ReasoningPolicyGenome(
        PolicyMode.COMPLETE_SELECTION,
        synthesis_rounds=3,
        max_unique_candidates=128,
        max_candidate_evaluations=256,
        max_generated_composites=256,
        max_expression_nodes=16,
        max_expression_depth=8,
    )

    assert noisy.normalized() == IMMUTABLE_PARENT_GENOME
    assert noisy.sha256 == IMMUTABLE_PARENT_GENOME.sha256
    assert noisy.canonical_payload() == IMMUTABLE_PARENT_GENOME.canonical_payload()


def test_synthesis_genome_round_trip_is_exact() -> None:
    genome = ReasoningPolicyGenome(
        PolicyMode.VERIFIED_SYNTHESIS,
        synthesis_rounds=2,
        max_unique_candidates=128,
        max_candidate_evaluations=256,
        max_generated_composites=256,
        max_expression_nodes=16,
        max_expression_depth=8,
    )

    reconstructed = ReasoningPolicyGenome.from_payload(genome.canonical_payload())

    assert reconstructed == genome
    assert reconstructed.sha256 == genome.sha256
    assert reconstructed.descriptor.mode_family == "synthesis"
    assert reconstructed.descriptor.verification_class == "strict"
    assert reconstructed.descriptor.synthesis_depth_tier == "medium"
    assert reconstructed.descriptor.compute_tier == "high"


def test_noncanonical_payload_is_rejected() -> None:
    genome = replace(IMMUTABLE_PARENT_GENOME, synthesis_rounds=3)
    payload = {
        "schema": genome.SCHEMA,
        "mode": PolicyMode.COMPLETE_SELECTION.value,
        "synthesis_rounds": 3,
        "max_unique_candidates": 64,
        "max_candidate_evaluations": 128,
        "max_generated_composites": 128,
        "max_expression_nodes": 12,
        "max_expression_depth": 6,
    }

    with pytest.raises(ValueError, match="not normalized"):
        ReasoningPolicyGenome.from_payload(payload)
