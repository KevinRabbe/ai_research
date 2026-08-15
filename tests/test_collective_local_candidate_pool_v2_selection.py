import hashlib
import json
from pathlib import Path

import pytest

from plural_cognition.collective.candidate_pool_v2_operational_freeze import (
    FINAL_CANDIDATE_IDS_V2,
)
from plural_cognition.collective.candidate_pool_v2_selection_protocol import (
    FINAL_SELECTION_PROTOCOL_SHA256_V2,
    SELECTION_TASK_IDS_V2,
)
from plural_cognition.collective.local_candidate_pool_v2_selection import (
    SELECTION_PAIR_SCHEMA_V2,
    _candidate_models,
    _candidate_sources,
    _canonical_json_bytes,
    _finalize_pair,
    _load_command,
    _pair_id,
    _pair_root,
    _preflight_pair_states,
    _validate_completed_pair,
)
from plural_cognition.collective.repository_surgery_selection_freeze_v2 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2,
)


SOFTWARE_REVISION = "a" * 40


def _minimal_pair_payload(candidate_id: str, task_id: str) -> dict[str, object]:
    return {
        "schema": SELECTION_PAIR_SCHEMA_V2,
        "candidate_id": candidate_id,
        "task_id": task_id,
        "pair_id": _pair_id(candidate_id, task_id),
        "software_revision": SOFTWARE_REVISION,
        "protocol_sha256": FINAL_SELECTION_PROTOCOL_SHA256_V2,
        "selection_pack_freeze_sha256": FINAL_REPOSITORY_SURGERY_SELECTION_PACK_FREEZE_SHA256_V2,
        "selection_evidence": True,
    }


def test_selection_candidate_sources_are_exact_five_survivors() -> None:
    sources = _candidate_sources()
    assert tuple(sources) == FINAL_CANDIDATE_IDS_V2
    assert "phi-4-reasoning-plus-14b-q5km" not in sources
    assert all(int(item["artifact_size_bytes"]) > 0 for item in sources.values())
    assert all(len(item["artifact_sha256"]) == 64 for item in sources.values())

    models = _candidate_models(sources)
    assert tuple(item.candidate_id for item in models) == FINAL_CANDIDATE_IDS_V2
    assert tuple(item.mind.mind_id for item in models) == FINAL_CANDIDATE_IDS_V2
    assert all(item.context_tokens == 4096 for item in models)


def test_selection_pair_id_binds_candidate_task_protocol_and_pack() -> None:
    first = _pair_id(FINAL_CANDIDATE_IDS_V2[0], SELECTION_TASK_IDS_V2[0])
    assert len(first) == 64
    assert first != _pair_id(FINAL_CANDIDATE_IDS_V2[1], SELECTION_TASK_IDS_V2[0])
    assert first != _pair_id(FINAL_CANDIDATE_IDS_V2[0], SELECTION_TASK_IDS_V2[1])


def test_completed_selection_pair_is_content_addressed(tmp_path: Path) -> None:
    candidate_id = FINAL_CANDIDATE_IDS_V2[0]
    task_id = SELECTION_TASK_IDS_V2[0]
    root = _pair_root(tmp_path, candidate_id, task_id)
    root.mkdir(parents=True)
    report = _finalize_pair(root, _minimal_pair_payload(candidate_id, task_id))

    _validate_completed_pair(
        report,
        candidate_id=candidate_id,
        task_id=task_id,
        software_revision=SOFTWARE_REVISION,
    )

    tampered = dict(report)
    tampered["candidate_id"] = FINAL_CANDIDATE_IDS_V2[1]
    with pytest.raises(RuntimeError, match="field drifted"):
        _validate_completed_pair(
            tampered,
            candidate_id=candidate_id,
            task_id=task_id,
            software_revision=SOFTWARE_REVISION,
        )


def test_partial_selection_pair_blocks_all_new_inference(tmp_path: Path) -> None:
    root = _pair_root(tmp_path, FINAL_CANDIDATE_IDS_V2[0], SELECTION_TASK_IDS_V2[0])
    root.mkdir(parents=True)
    (root / "attempt.json").write_text("{}", encoding="ascii")

    with pytest.raises(RuntimeError, match="blocks all new inference"):
        _preflight_pair_states(tmp_path, software_revision=SOFTWARE_REVISION)


def test_load_command_preserves_frozen_resource_contract(tmp_path: Path) -> None:
    command = _load_command(
        cli=tmp_path / "llama-cli.exe",
        model_path=tmp_path / "model.gguf",
        prompt=b"prompt-without-terminal-lf",
        capture=tmp_path / "transcript.txt",
    )
    joined = " ".join(command)
    assert "-c 4096" in joined
    assert "-n 2048" in joined
    assert "-ngl all" in joined
    assert "-dev CUDA0" in joined
    assert "-fit off" in joined
    assert "-sm none" in joined
    assert "-ctk f16" in joined and "-ctv f16" in joined
    assert "--offline" in command
    assert "--temp 0" in joined
    assert "--seed 1" in joined
    assert "--log-verbosity 4" in joined
    assert command[-1] == "prompt-without-terminal-lf"


def test_completed_pair_hash_rejects_content_mutation(tmp_path: Path) -> None:
    candidate_id = FINAL_CANDIDATE_IDS_V2[0]
    task_id = SELECTION_TASK_IDS_V2[0]
    root = _pair_root(tmp_path, candidate_id, task_id)
    root.mkdir(parents=True)
    report = _finalize_pair(root, _minimal_pair_payload(candidate_id, task_id))
    mutated = dict(report)
    mutated["unexpected"] = True
    with pytest.raises(RuntimeError, match="content drifted"):
        _validate_completed_pair(
            mutated,
            candidate_id=candidate_id,
            task_id=task_id,
            software_revision=SOFTWARE_REVISION,
        )
