"""Canonical bounded genomes for frozen-weight reasoning-policy evolution."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
from typing import ClassVar


class PolicyMode(str, Enum):
    COMPLETE_SELECTION = "complete-selection"
    VERIFIED_FRAGMENT_SELECTION = "verified-fragment-selection"
    VERIFIED_SYNTHESIS = "verified-synthesis"
    UNVERIFIED_SYNTHESIS = "unverified-synthesis"

    @property
    def uses_synthesis(self) -> bool:
        return self in {
            PolicyMode.VERIFIED_SYNTHESIS,
            PolicyMode.UNVERIFIED_SYNTHESIS,
        }


SYNTHESIS_ROUNDS = (1, 2, 3)
UNIQUE_CANDIDATE_CAPS = (32, 64, 128)
CANDIDATE_EVALUATION_CAPS = (64, 128, 256)
COMPOSITE_GENERATION_CAPS = (64, 128, 256)
EXPRESSION_NODE_CAPS = (8, 12, 16)
EXPRESSION_DEPTH_CAPS = (4, 6, 8)
POLICY_MODES = tuple(PolicyMode)


@dataclass(frozen=True, slots=True)
class BehaviorDescriptor:
    mode_family: str
    verification_class: str
    synthesis_depth_tier: str
    compute_tier: str

    def __post_init__(self) -> None:
        if self.mode_family not in {"selection", "synthesis"}:
            raise ValueError("invalid mode_family")
        if self.verification_class not in {"none", "strict", "permissive"}:
            raise ValueError("invalid verification_class")
        if self.synthesis_depth_tier not in {"none", "shallow", "medium", "deep"}:
            raise ValueError("invalid synthesis_depth_tier")
        if self.compute_tier not in {"low", "medium", "high"}:
            raise ValueError("invalid compute_tier")

    def as_tuple(self) -> tuple[str, str, str, str]:
        return (
            self.mode_family,
            self.verification_class,
            self.synthesis_depth_tier,
            self.compute_tier,
        )


@dataclass(frozen=True, slots=True)
class ReasoningPolicyGenome:
    """One immutable external reasoning architecture.

    Selection-only modes canonicalize all synthesis fields to the fixed defaults.
    This prevents inactive parameters from creating false genome or archive diversity.
    """

    mode: PolicyMode = PolicyMode.COMPLETE_SELECTION
    synthesis_rounds: int = 1
    max_unique_candidates: int = 64
    max_candidate_evaluations: int = 128
    max_generated_composites: int = 128
    max_expression_nodes: int = 12
    max_expression_depth: int = 6

    SCHEMA: ClassVar[str] = "plural-cognition-si-policy-genome-v1"
    INACTIVE_DEFAULTS: ClassVar[dict[str, int]] = {
        "synthesis_rounds": 1,
        "max_unique_candidates": 64,
        "max_candidate_evaluations": 128,
        "max_generated_composites": 128,
        "max_expression_nodes": 12,
        "max_expression_depth": 6,
    }

    def __post_init__(self) -> None:
        if not isinstance(self.mode, PolicyMode):
            raise TypeError("mode must be a PolicyMode")
        self._validate_domain("synthesis_rounds", self.synthesis_rounds, SYNTHESIS_ROUNDS)
        self._validate_domain(
            "max_unique_candidates",
            self.max_unique_candidates,
            UNIQUE_CANDIDATE_CAPS,
        )
        self._validate_domain(
            "max_candidate_evaluations",
            self.max_candidate_evaluations,
            CANDIDATE_EVALUATION_CAPS,
        )
        self._validate_domain(
            "max_generated_composites",
            self.max_generated_composites,
            COMPOSITE_GENERATION_CAPS,
        )
        self._validate_domain(
            "max_expression_nodes",
            self.max_expression_nodes,
            EXPRESSION_NODE_CAPS,
        )
        self._validate_domain(
            "max_expression_depth",
            self.max_expression_depth,
            EXPRESSION_DEPTH_CAPS,
        )
        if self.max_expression_depth > self.max_expression_nodes:
            raise ValueError("expression depth cap cannot exceed node cap")
        if self.max_candidate_evaluations < self.max_unique_candidates:
            raise ValueError(
                "candidate-evaluation cap cannot be below unique-candidate cap"
            )

    @staticmethod
    def _validate_domain(name: str, value: int, domain: tuple[int, ...]) -> None:
        if type(value) is not int or value not in domain:
            raise ValueError(f"{name} must be one of {domain!r}")

    def normalized(self) -> ReasoningPolicyGenome:
        if self.mode.uses_synthesis:
            return self
        normalized = self
        for field, value in self.INACTIVE_DEFAULTS.items():
            if getattr(normalized, field) != value:
                normalized = replace(normalized, **{field: value})
        return normalized

    def canonical_payload(self) -> dict[str, object]:
        normalized = self.normalized()
        return {
            "schema": self.SCHEMA,
            "mode": normalized.mode.value,
            "synthesis_rounds": normalized.synthesis_rounds,
            "max_unique_candidates": normalized.max_unique_candidates,
            "max_candidate_evaluations": normalized.max_candidate_evaluations,
            "max_generated_composites": normalized.max_generated_composites,
            "max_expression_nodes": normalized.max_expression_nodes,
            "max_expression_depth": normalized.max_expression_depth,
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()

    @property
    def complexity(self) -> tuple[int, int, int, int, int, int, int]:
        normalized = self.normalized()
        mode_rank = POLICY_MODES.index(normalized.mode)
        return (
            mode_rank,
            normalized.synthesis_rounds,
            normalized.max_unique_candidates,
            normalized.max_candidate_evaluations,
            normalized.max_generated_composites,
            normalized.max_expression_nodes,
            normalized.max_expression_depth,
        )

    @property
    def descriptor(self) -> BehaviorDescriptor:
        normalized = self.normalized()
        if normalized.mode.uses_synthesis:
            mode_family = "synthesis"
            verification = (
                "strict"
                if normalized.mode is PolicyMode.VERIFIED_SYNTHESIS
                else "permissive"
            )
            depth_tier = {1: "shallow", 2: "medium", 3: "deep"}[
                normalized.synthesis_rounds
            ]
            compute_score = (
                normalized.max_unique_candidates
                + normalized.max_candidate_evaluations
                + normalized.max_generated_composites
            )
            compute_tier = (
                "low"
                if compute_score <= 224
                else "medium"
                if compute_score <= 448
                else "high"
            )
        else:
            mode_family = "selection"
            verification = (
                "strict"
                if normalized.mode is PolicyMode.VERIFIED_FRAGMENT_SELECTION
                else "none"
            )
            depth_tier = "none"
            compute_tier = "low"
        return BehaviorDescriptor(
            mode_family,
            verification,
            depth_tier,
            compute_tier,
        )

    @classmethod
    def from_payload(cls, payload: object) -> ReasoningPolicyGenome:
        if not isinstance(payload, dict):
            raise ValueError("policy genome payload must be an object")
        expected = {
            "schema",
            "mode",
            "synthesis_rounds",
            "max_unique_candidates",
            "max_candidate_evaluations",
            "max_generated_composites",
            "max_expression_nodes",
            "max_expression_depth",
        }
        if set(payload) != expected:
            raise ValueError("policy genome payload has wrong fields")
        if payload["schema"] != cls.SCHEMA:
            raise ValueError("unsupported policy genome schema")
        try:
            genome = cls(
                PolicyMode(payload["mode"]),
                payload["synthesis_rounds"],
                payload["max_unique_candidates"],
                payload["max_candidate_evaluations"],
                payload["max_generated_composites"],
                payload["max_expression_nodes"],
                payload["max_expression_depth"],
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid policy genome payload") from exc
        if genome.canonical_payload() != payload:
            raise ValueError("policy genome payload is not normalized")
        return genome


IMMUTABLE_PARENT_GENOME = ReasoningPolicyGenome()
