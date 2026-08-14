from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from plural_cognition.collective import local_consumed_selection_development_v5_self_review_recovery as recovery
from plural_cognition.collective.consumed_selection_development_v5_self_review import (
    TARGET_CANDIDATE_IDS_V5,
    TARGET_TASK_IDS_V5,
)


def _fake_prompts() -> dict[tuple[str, str], tuple[bytes, str]]:
    result: dict[tuple[str, str], tuple[bytes, str]] = {}
    for candidate_id in TARGET_CANDIDATE_IDS_V5:
        for task_id in TARGET_TASK_IDS_V5:
            prompt = f"{candidate_id}|{task_id}".encode("utf-8")
            result[(candidate_id, task_id)] = (prompt, hashlib.sha256(prompt).hexdigest())
    return result


def _populate_first_ten(root: Path, prompts: dict[tuple[str, str], tuple[bytes, str]]) -> None:
    for candidate_id, task_id in recovery.PARTIAL_REUSED_PAIRS_V5:
        _prompt, prompt_sha256 = prompts[(candidate_id, task_id)]
        path = root / "llama-output" / candidate_id / f"{prompt_sha256}.transcript.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"captured")


def test_recovery_pair_partition_is_exact_and_no_repeat() -> None:
    assert len(recovery._EXPECTED_PAIR_ORDER_V5) == 12
    assert len(recovery.PARTIAL_REUSED_PAIRS_V5) == 10
    assert len(recovery.RECOVERY_NEW_PAIRS_V5) == 2
    assert recovery.PARTIAL_REUSED_PAIRS_V5 + recovery.RECOVERY_NEW_PAIRS_V5 == recovery._EXPECTED_PAIR_ORDER_V5
    assert recovery.RECOVERY_NEW_PAIRS_V5 == (
        ("deepseek-coder-v2-lite-q5km", "repository-surgery-selection-multi-file-0001"),
        ("deepseek-coder-v2-lite-q5km", "repository-surgery-selection-multi-file-0002"),
    )


def test_durable_sidecar_write_recreates_missing_parent(tmp_path: Path) -> None:
    path = tmp_path / "candidate" / "answer.transcript.process-stdout.bin"
    assert not path.parent.exists()
    recovery._write_bytes_durable(path, b"abc")
    assert path.read_bytes() == b"abc"


def test_partial_manifest_rejects_complete_report_or_manifest(tmp_path: Path) -> None:
    root = tmp_path / "partial"
    root.mkdir()
    (root / "consumed-selection-development-v5-self-review.json").write_text("{}", encoding="ascii")
    with pytest.raises(ValueError, match="complete report"):
        recovery._partial_manifest(root)
    (root / "consumed-selection-development-v5-self-review.json").unlink()
    (root / "output-channel-manifest.json").write_text("{}", encoding="ascii")
    with pytest.raises(ValueError, match="final output manifest"):
        recovery._partial_manifest(root)


def test_validate_partial_root_accepts_only_first_ten_transcripts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    prompts = _fake_prompts()
    monkeypatch.setattr(recovery, "_expected_prompts", lambda **_kwargs: ({}, {}, prompts))
    root = tmp_path / "partial"
    root.mkdir()
    _populate_first_ten(root, prompts)

    boundary = recovery.validate_partial_v5_root(
        partial_root=root,
        v4_targeted_root=tmp_path / "v4-targeted",
        v4_remainder_root=tmp_path / "v4-remainder",
    )
    assert len(boundary["reused_pairs"]) == 10
    assert len(boundary["new_pairs"]) == 2
    assert len(boundary["partial_manifest"]["sha256"]) == 64

    candidate_id, task_id = recovery.RECOVERY_NEW_PAIRS_V5[0]
    _prompt, prompt_sha256 = prompts[(candidate_id, task_id)]
    repeated = root / "llama-output" / candidate_id / f"{prompt_sha256}.transcript.txt"
    repeated.parent.mkdir(parents=True, exist_ok=True)
    repeated.write_bytes(b"would-repeat")
    with pytest.raises(ValueError, match="transcript count drifted|would repeat"):
        recovery.validate_partial_v5_root(
            partial_root=root,
            v4_targeted_root=tmp_path / "v4-targeted",
            v4_remainder_root=tmp_path / "v4-remainder",
        )
