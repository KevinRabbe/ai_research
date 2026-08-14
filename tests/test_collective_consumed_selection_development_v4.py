from __future__ import annotations

from plural_cognition.collective.consumed_selection_development_v4 import (
    CANDIDATE_OUTPUT_INTERPRETER_V4,
    CONTROL_LINE_GRAMMAR_V4,
    DEVELOPMENT_PROTOCOL_SHA256_V4,
    OUTPUT_CONTRACT_V4,
    PROMPT_SOURCE_REPRESENTATION_V4,
    TERMINAL_LF_SEMANTICS_V4,
    V2_TARGETED_REPORT_SHA256,
    V3_TARGETED_OUTPUT_MANIFEST_SHA256,
    V3_TARGETED_REPORT_SHA256,
    build_solver_prompt_v4,
    development_protocol_payload_v4,
    extract_full_file_patch_v4,
    parse_full_file_replacements_v4,
)
from plural_cognition.collective.local_operational_freeze_v1 import FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1
from plural_cognition.collective.repository_surgery_selection_outcome_freeze_v1 import FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256
from plural_cognition.collective.repository_surgery_selection_pack_v1 import selection_blueprints


def _blueprint(task_id: str):
    return next(item for item in selection_blueprints() if item.task_id == task_id)


def _gold_full_file_output(blueprint) -> bytes:
    buggy = dict(blueprint.buggy_files)
    blocks: list[str] = []
    for path, clean_raw in blueprint.clean_files:
        if clean_raw == buggy[path]:
            continue
        clean = clean_raw.decode("utf-8")
        if clean.endswith("\n"):
            clean = clean[:-1]
        blocks.append(f"FILE {path}\n<<<<<<< CONTENT\n{clean}\n>>>>>>> CONTENT")
    return "\n".join(blocks).encode("utf-8")


def test_v4_protocol_binds_consumed_evidence_and_only_changes_representation() -> None:
    payload = development_protocol_payload_v4()
    assert payload["consumed_selection_outcome_freeze_sha256"] == FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256
    assert payload["operational_config_freeze_sha256"] == FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.sha256
    assert payload["preceding_v2_targeted_report_sha256"] == V2_TARGETED_REPORT_SHA256
    assert payload["preceding_v3_targeted_report_sha256"] == V3_TARGETED_REPORT_SHA256
    assert payload["preceding_v3_output_manifest_sha256"] == V3_TARGETED_OUTPUT_MANIFEST_SHA256
    assert payload["prompt_source_representation"] == PROMPT_SOURCE_REPRESENTATION_V4
    assert payload["output_contract"] == OUTPUT_CONTRACT_V4
    assert payload["candidate_output_interpreter"] == CANDIDATE_OUTPUT_INTERPRETER_V4
    assert payload["control_line_grammar"] == CONTROL_LINE_GRAMMAR_V4
    assert payload["terminal_lf_semantics"] == TERMINAL_LF_SEMANTICS_V4
    assert payload["context_tokens"] == 4096
    assert payload["predict_tokens"] == 2048
    assert payload["temperature"] == 0.0
    assert payload["seed"] == 1
    assert payload["max_attempts"] == 1
    assert payload["fuzzy_matching"] is False
    assert payload["candidate_output_repair"] is False
    assert len(DEVELOPMENT_PROTOCOL_SHA256_V4) == 64


def test_v4_prompt_uses_plain_source_and_whole_file_contract() -> None:
    prompt = build_solver_prompt_v4(_blueprint("repository-surgery-selection-api-contract-0002"))
    assert b"FILE relative/file.py" in prompt
    assert b"<<<<<<< CONTENT" in prompt
    assert b">>>>>>> CONTENT" in prompt
    assert b"complete corrected file" in prompt
    assert b"L0001|" not in prompt
    assert b"<<<<<<< SEARCH" not in prompt
    assert b'"old"' not in prompt
    assert prompt.endswith(b"\n")


def test_v4_gold_full_file_outputs_reconstruct_all_twelve_gold_patches() -> None:
    for blueprint in selection_blueprints():
        patch, mode = extract_full_file_patch_v4(_gold_full_file_output(blueprint), blueprint)
        assert mode == "raw-full-file-replacement"
        assert patch == blueprint.gold_patch


def test_v4_control_lines_accept_horizontal_whitespace_without_touching_payload() -> None:
    blueprint = _blueprint("repository-surgery-selection-error-handling-0001")
    clean = dict(blueprint.clean_files)["app.py"].decode("utf-8")[:-1]
    raw = f"  FILE app.py\t\n \t<<<<<<< CONTENT\t\n{clean}\n  >>>>>>> CONTENT \t".encode("utf-8")
    patch, _ = extract_full_file_patch_v4(raw, blueprint)
    assert patch == blueprint.gold_patch


def test_v4_parser_rejects_explanatory_preface() -> None:
    try:
        parse_full_file_replacements_v4(b"Here is the fix:\nFILE app.py\n<<<<<<< CONTENT\nx\n>>>>>>> CONTENT")
    except ValueError as exc:
        assert "expected FILE header" in str(exc)
    else:
        raise AssertionError("V4 unexpectedly accepted explanatory preface")


def test_v4_rejects_unknown_path_and_unchanged_file() -> None:
    blueprint = _blueprint("repository-surgery-selection-api-contract-0002")
    try:
        extract_full_file_patch_v4(b"FILE nope.py\n<<<<<<< CONTENT\nx\n>>>>>>> CONTENT", blueprint)
    except ValueError as exc:
        assert "not solver-visible" in str(exc)
    else:
        raise AssertionError("V4 unexpectedly accepted unknown file")

    buggy = dict(blueprint.buggy_files)["app.py"].decode("utf-8")[:-1]
    raw = f"FILE app.py\n<<<<<<< CONTENT\n{buggy}\n>>>>>>> CONTENT".encode("utf-8")
    try:
        extract_full_file_patch_v4(raw, blueprint)
    except ValueError as exc:
        assert "leaves file unchanged" in str(exc)
    else:
        raise AssertionError("V4 unexpectedly accepted unchanged file")
