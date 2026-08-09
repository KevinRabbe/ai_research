"""Strict canonical JSON reconstruction for SI-V1 artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plural_cognition.manifest_io import read_canonical_json, write_canonical_json

from .candidate_pool import FrozenCandidatePool
from .experiment import SearchPhaseResult
from .generation import TargetFreeGenerationArtifact
from .genome import ReasoningPolicyGenome
from .manifests import (
    ExperimentSplit,
    FinalistEntry,
    FinalistManifest,
    FinalistRole,
    SelfImprovementExperimentManifest,
    SplitManifest,
)
from .mutation import MutationRecord
from .policy import ReasoningBudget
from .search import (
    GenomeEvaluationRecord,
    PromotionEvent,
    SearchConfig,
    SearchResult,
    SearchStrategy,
    SplitFitness,
)


class SelfImprovementIOError(ValueError):
    pass


def _object(payload: Any, fields: set[str], name: str) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != fields:
        raise SelfImprovementIOError(f"{name} has wrong fields")
    return payload


def _hex(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise SelfImprovementIOError(f"{field} must contain 64 hexadecimal characters")
    try:
        int(value, 16)
    except ValueError as exc:
        raise SelfImprovementIOError(f"{field} must be hexadecimal") from exc
    return value


def _plain_int(value: Any, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise SelfImprovementIOError(f"{field} must be an integer >= {minimum}")
    return value


def _plain_number(value: Any, field: str) -> float:
    if type(value) not in (int, float):
        raise SelfImprovementIOError(f"{field} must be numeric")
    return float(value)


def _split_fitness(payload: Any) -> SplitFitness:
    raw = _object(
        payload,
        {
            "exact_accuracy",
            "mean_semantic_accuracy",
            "invalid_rate",
            "mean_reasoning_operations",
            "max_reasoning_operations",
            "over_budget_rate",
        },
        "split fitness",
    )
    try:
        return SplitFitness(
            _plain_number(raw["exact_accuracy"], "exact_accuracy"),
            _plain_number(
                raw["mean_semantic_accuracy"],
                "mean_semantic_accuracy",
            ),
            _plain_number(raw["invalid_rate"], "invalid_rate"),
            _plain_number(
                raw["mean_reasoning_operations"],
                "mean_reasoning_operations",
            ),
            _plain_int(
                raw["max_reasoning_operations"],
                "max_reasoning_operations",
            ),
            _plain_number(raw["over_budget_rate"], "over_budget_rate"),
        )
    except ValueError as exc:
        raise SelfImprovementIOError("invalid split fitness") from exc


def _search_config(payload: Any) -> SearchConfig:
    raw = _object(
        payload,
        {
            "generations",
            "max_genome_evaluations",
            "archive_capacity",
            "random_seed",
        },
        "search config",
    )
    try:
        return SearchConfig(
            raw["generations"],
            raw["max_genome_evaluations"],
            raw["archive_capacity"],
            raw["random_seed"],
        )
    except (TypeError, ValueError) as exc:
        raise SelfImprovementIOError("invalid search config") from exc


def _reasoning_budget(payload: Any) -> ReasoningBudget:
    raw = _object(
        payload,
        {
            "max_candidate_inputs",
            "max_packet_extractions",
            "max_reasoning_operations",
        },
        "reasoning budget",
    )
    try:
        return ReasoningBudget(
            raw["max_candidate_inputs"],
            raw["max_packet_extractions"],
            raw["max_reasoning_operations"],
        )
    except (TypeError, ValueError) as exc:
        raise SelfImprovementIOError("invalid reasoning budget") from exc


def _mutation(payload: Any) -> MutationRecord:
    raw = _object(
        payload,
        {
            "parent_sha256",
            "child_sha256",
            "field",
            "old_value",
            "new_value",
            "generation",
            "ordinal",
        },
        "mutation record",
    )
    try:
        return MutationRecord(
            _hex(raw["parent_sha256"], "mutation parent"),
            _hex(raw["child_sha256"], "mutation child"),
            raw["field"],
            raw["old_value"],
            raw["new_value"],
            raw["generation"],
            raw["ordinal"],
        )
    except (TypeError, ValueError) as exc:
        raise SelfImprovementIOError("invalid mutation record") from exc


def _genome_record(payload: Any) -> GenomeEvaluationRecord:
    raw = _object(
        payload,
        {
            "genome",
            "genome_sha256",
            "generation",
            "parent_sha256",
            "mutation",
            "descriptor",
            "discovery",
            "development",
        },
        "genome evaluation record",
    )
    try:
        genome = ReasoningPolicyGenome.from_payload(raw["genome"])
        if _hex(raw["genome_sha256"], "genome SHA") != genome.sha256:
            raise SelfImprovementIOError("genome SHA does not match payload")
        descriptor = raw["descriptor"]
        if not isinstance(descriptor, list) or tuple(descriptor) != genome.descriptor.as_tuple():
            raise SelfImprovementIOError("genome descriptor does not match payload")
        parent = raw["parent_sha256"]
        if parent is not None:
            parent = _hex(parent, "record parent SHA")
        mutation = None if raw["mutation"] is None else _mutation(raw["mutation"])
        return GenomeEvaluationRecord(
            genome,
            _plain_int(raw["generation"], "record generation"),
            parent,
            mutation,
            _split_fitness(raw["discovery"]),
            _split_fitness(raw["development"]),
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, SelfImprovementIOError):
            raise
        raise SelfImprovementIOError("invalid genome evaluation record") from exc


def _promotion(payload: Any) -> PromotionEvent:
    raw = _object(
        payload,
        {
            "generation",
            "child_sha256",
            "replaced_sha256",
            "archive_cell",
            "reason",
        },
        "promotion event",
    )
    replaced = raw["replaced_sha256"]
    if replaced is not None:
        replaced = _hex(replaced, "replaced genome SHA")
    cell = raw["archive_cell"]
    if cell is not None:
        if not isinstance(cell, list) or len(cell) != 4 or any(
            not isinstance(value, str) for value in cell
        ):
            raise SelfImprovementIOError("archive cell must contain four strings")
        cell = tuple(cell)
    try:
        return PromotionEvent(
            raw["generation"],
            _hex(raw["child_sha256"], "promotion child SHA"),
            replaced,
            cell,
            raw["reason"],
        )
    except (TypeError, ValueError) as exc:
        raise SelfImprovementIOError("invalid promotion event") from exc


def search_result_from_payload(payload: Any) -> SearchResult:
    raw = _object(
        payload,
        {
            "schema",
            "strategy",
            "config",
            "evaluated_genome_count",
            "records",
            "promotions",
            "elite_sha256s",
            "champion_sha256",
            "stopped_reason",
        },
        "search result",
    )
    if raw["schema"] != SearchResult.SCHEMA:
        raise SelfImprovementIOError("unsupported search-result schema")
    if not isinstance(raw["records"], list) or not isinstance(raw["promotions"], list):
        raise SelfImprovementIOError("search records and promotions must be lists")
    if not isinstance(raw["elite_sha256s"], list):
        raise SelfImprovementIOError("search elite identities must be a list")
    try:
        result = SearchResult(
            SearchStrategy(raw["strategy"]),
            _search_config(raw["config"]),
            tuple(_genome_record(item) for item in raw["records"]),
            tuple(_promotion(item) for item in raw["promotions"]),
            tuple(_hex(item, "elite genome SHA") for item in raw["elite_sha256s"]),
            _hex(raw["champion_sha256"], "champion genome SHA"),
            raw["stopped_reason"],
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, SelfImprovementIOError):
            raise
        raise SelfImprovementIOError("invalid search result") from exc
    if raw["evaluated_genome_count"] != result.evaluated_genome_count:
        raise SelfImprovementIOError("search evaluated count is inconsistent")
    if result.canonical_payload() != raw:
        raise SelfImprovementIOError("search result payload is not canonical")
    return result


def _split_manifest(payload: Any) -> SplitManifest:
    raw = _object(
        payload,
        {
            "split",
            "candidate_pool_sha256",
            "task_shard_manifest_sha256s",
            "task_count",
        },
        "split manifest",
    )
    if not isinstance(raw["task_shard_manifest_sha256s"], list):
        raise SelfImprovementIOError("task-shard identities must be a list")
    try:
        return SplitManifest(
            ExperimentSplit(raw["split"]),
            _hex(raw["candidate_pool_sha256"], "candidate-pool SHA"),
            tuple(
                _hex(value, "task-shard SHA")
                for value in raw["task_shard_manifest_sha256s"]
            ),
            raw["task_count"],
        )
    except (TypeError, ValueError) as exc:
        raise SelfImprovementIOError("invalid split manifest") from exc


def experiment_manifest_from_payload(payload: Any) -> SelfImprovementExperimentManifest:
    raw = _object(
        payload,
        {
            "schema",
            "checkpoint_sha256",
            "execution_sha256",
            "generation_source_ids",
            "splits",
            "search_config",
            "reasoning_budget",
            "immutable_parent",
            "immutable_parent_sha256",
            "fixed_policy",
            "fixed_policy_sha256",
            "bootstrap_resamples",
            "bootstrap_seed",
            "shuffled_label_seed",
            "minimum_hidden_gain",
        },
        "experiment manifest",
    )
    if raw["schema"] != SelfImprovementExperimentManifest.SCHEMA:
        raise SelfImprovementIOError("unsupported experiment-manifest schema")
    if not isinstance(raw["generation_source_ids"], list) or not isinstance(raw["splits"], list):
        raise SelfImprovementIOError("experiment sources and splits must be lists")
    try:
        parent = ReasoningPolicyGenome.from_payload(raw["immutable_parent"])
        fixed = ReasoningPolicyGenome.from_payload(raw["fixed_policy"])
        if _hex(raw["immutable_parent_sha256"], "parent SHA") != parent.sha256:
            raise SelfImprovementIOError("parent SHA does not match parent genome")
        if _hex(raw["fixed_policy_sha256"], "fixed-policy SHA") != fixed.sha256:
            raise SelfImprovementIOError("fixed-policy SHA does not match genome")
        manifest = SelfImprovementExperimentManifest(
            _hex(raw["checkpoint_sha256"], "checkpoint SHA"),
            _hex(raw["execution_sha256"], "execution SHA"),
            tuple(raw["generation_source_ids"]),
            tuple(_split_manifest(item) for item in raw["splits"]),
            _search_config(raw["search_config"]),
            _reasoning_budget(raw["reasoning_budget"]),
            parent,
            fixed,
            raw["bootstrap_resamples"],
            raw["bootstrap_seed"],
            raw["shuffled_label_seed"],
            raw["minimum_hidden_gain"],
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, SelfImprovementIOError):
            raise
        raise SelfImprovementIOError("invalid experiment manifest") from exc
    if manifest.canonical_payload() != raw:
        raise SelfImprovementIOError("experiment manifest payload is not canonical")
    return manifest


def finalist_manifest_from_payload(payload: Any) -> FinalistManifest:
    raw = _object(
        payload,
        {
            "schema",
            "experiment_sha256",
            "search_result_sha256s",
            "finalists",
        },
        "finalist manifest",
    )
    if raw["schema"] != FinalistManifest.SCHEMA:
        raise SelfImprovementIOError("unsupported finalist-manifest schema")
    if not isinstance(raw["search_result_sha256s"], list) or not isinstance(raw["finalists"], list):
        raise SelfImprovementIOError("finalist search hashes and entries must be lists")
    search_hashes = []
    for item in raw["search_result_sha256s"]:
        entry = _object(item, {"name", "sha256"}, "search-result identity")
        if not isinstance(entry["name"], str) or not entry["name"]:
            raise SelfImprovementIOError("search-result name must not be empty")
        search_hashes.append((entry["name"], _hex(entry["sha256"], "search-result SHA")))
    finalists = []
    for item in raw["finalists"]:
        entry = _object(
            item,
            {"role", "genome", "genome_sha256", "source_search_sha256"},
            "finalist entry",
        )
        genome = ReasoningPolicyGenome.from_payload(entry["genome"])
        if _hex(entry["genome_sha256"], "finalist genome SHA") != genome.sha256:
            raise SelfImprovementIOError("finalist genome SHA does not match payload")
        source = entry["source_search_sha256"]
        if source is not None:
            source = _hex(source, "finalist source search SHA")
        finalists.append(FinalistEntry(FinalistRole(entry["role"]), genome, source))
    try:
        manifest = FinalistManifest(
            _hex(raw["experiment_sha256"], "finalist experiment SHA"),
            tuple(search_hashes),
            tuple(finalists),
        )
    except (TypeError, ValueError) as exc:
        raise SelfImprovementIOError("invalid finalist manifest") from exc
    if manifest.canonical_payload() != raw:
        raise SelfImprovementIOError("finalist manifest payload is not canonical")
    return manifest


def search_phase_from_payload(payload: Any) -> SearchPhaseResult:
    raw = _object(
        payload,
        {
            "schema",
            "experiment_sha256",
            "single_best",
            "archive",
            "random_search",
            "shuffled_labels",
            "finalist_manifest",
            "finalist_manifest_sha256",
        },
        "search phase",
    )
    if raw["schema"] != SearchPhaseResult.SCHEMA:
        raise SelfImprovementIOError("unsupported search-phase schema")
    finalists = finalist_manifest_from_payload(raw["finalist_manifest"])
    if _hex(raw["finalist_manifest_sha256"], "finalist manifest SHA") != finalists.sha256:
        raise SelfImprovementIOError("finalist manifest SHA does not match payload")
    try:
        phase = SearchPhaseResult(
            _hex(raw["experiment_sha256"], "search experiment SHA"),
            search_result_from_payload(raw["single_best"]),
            search_result_from_payload(raw["archive"]),
            search_result_from_payload(raw["random_search"]),
            search_result_from_payload(raw["shuffled_labels"]),
            finalists,
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, SelfImprovementIOError):
            raise
        raise SelfImprovementIOError("invalid search phase") from exc
    if phase.canonical_payload() != raw:
        raise SelfImprovementIOError("search-phase payload is not canonical")
    return phase


def read_generation_artifact(path: str | Path) -> TargetFreeGenerationArtifact:
    return TargetFreeGenerationArtifact.from_payload(read_canonical_json(path))


def write_generation_artifact(path: str | Path, artifact: TargetFreeGenerationArtifact) -> None:
    write_canonical_json(path, artifact.canonical_payload())


def read_candidate_pool(path: str | Path) -> FrozenCandidatePool:
    return FrozenCandidatePool.from_payload(read_canonical_json(path))


def write_candidate_pool(path: str | Path, pool: FrozenCandidatePool) -> None:
    write_canonical_json(path, pool.canonical_payload())


def read_experiment_manifest(path: str | Path) -> SelfImprovementExperimentManifest:
    return experiment_manifest_from_payload(read_canonical_json(path))


def write_experiment_manifest(path: str | Path, manifest: SelfImprovementExperimentManifest) -> None:
    write_canonical_json(path, manifest.canonical_payload())


def read_search_phase(path: str | Path) -> SearchPhaseResult:
    return search_phase_from_payload(read_canonical_json(path))


def write_search_phase(path: str | Path, phase: SearchPhaseResult) -> None:
    write_canonical_json(path, phase.canonical_payload())
