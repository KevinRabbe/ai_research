from __future__ import annotations

from plural_cognition.collective.consumed_selection_development_v2 import (
    CANDIDATE_OUTPUT_INTERPRETER,
    DEVELOPMENT_PROTOCOL_SHA256_V2,
    OUTPUT_CONTRACT,
    PROMPT_SOURCE_REPRESENTATION,
    build_solver_prompt_v2,
    development_protocol_payload_v2,
    extract_line_span_patch,
    parse_line_span_edits,
)
from plural_cognition.collective.local_operational_freeze_v1 import (
    FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1,
)
from plural_cognition.collective.repository_surgery_selection_outcome_freeze_v1 import (
    FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256,
)
from plural_cognition.collective.repository_surgery_selection_pack_v1 import selection_blueprints


def _blueprint(task_id: str):
    return next(item for item in selection_blueprints() if item.task_id == task_id)


def _line_number(blueprint, path: str, needle: str) -> int:
    text = dict(blueprint.buggy_files)[path].decode("utf-8")
    return next(index for index, line in enumerate(text.splitlines(), start=1) if needle in line)


def test_protocol_binds_consumed_outcome_and_only_changes_representation() -> None:
    payload = development_protocol_payload_v2()
    assert payload["consumed_selection_outcome_freeze_sha256"] == FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256
    assert payload["operational_config_freeze_sha256"] == FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.sha256
    assert payload["prompt_source_representation"] == PROMPT_SOURCE_REPRESENTATION
    assert payload["output_contract"] == OUTPUT_CONTRACT
    assert payload["candidate_output_interpreter"] == CANDIDATE_OUTPUT_INTERPRETER
    assert payload["context_tokens"] == 4096
    assert payload["predict_tokens"] == 2048
    assert payload["temperature"] == 0.0
    assert payload["seed"] == 1
    assert payload["max_attempts"] == 1
    assert payload["fuzzy_matching"] is False
    assert payload["candidate_output_repair"] is False
    assert len(DEVELOPMENT_PROTOCOL_SHA256_V2) == 64


def test_prompt_numbers_source_and_removes_json_edit_contract() -> None:
    blueprint = _blueprint("repository-surgery-selection-api-contract-0002")
    prompt = build_solver_prompt_v2(blueprint)
    assert b"L0001|import json" in prompt
    assert b"EDIT relative/file.py START DELETE INSERT" in prompt
    assert b"Do not use markdown fences or JSON." in prompt
    assert b'"old"' not in prompt
    assert b'"new"' not in prompt
    assert prompt.endswith(b"\n")


def test_one_line_span_materializes_exact_canonical_repair() -> None:
    blueprint = _blueprint("repository-surgery-selection-api-contract-0002")
    line = _line_number(blueprint, "app.py", 'sys.stdout.write(json.dumps({"value": total}')
    raw = (
        f"EDIT app.py {line} 1 1\n"
        '    sys.stdout.write(json.dumps({"total": total}, sort_keys=True, separators=(",", ":")) + "\\n")'
    ).encode("utf-8")
    patch, mode = extract_line_span_patch(raw, blueprint)
    assert mode == "original-line-span-raw"
    assert patch == blueprint.gold_patch


def test_multiline_repair_needs_no_json_newline_escaping() -> None:
    blueprint = _blueprint("repository-surgery-selection-error-handling-0002")
    line = _line_number(blueprint, "app.py", 'if mode == "sum":')
    raw = (
        f"EDIT app.py {line} 3 5\n"
        '    if mode == "sum":\n'
        '        return sum(values)\n'
        '    if mode == "max":\n'
        '        return max(values)\n'
        '    raise ValueError("unsupported mode")'
    ).encode("utf-8")
    patch, _ = extract_line_span_patch(raw, blueprint)
    assert patch == blueprint.gold_patch


def test_parser_is_strict_and_does_not_salvage() -> None:
    try:
        parse_line_span_edits(b"Here is the fix:\nEDIT app.py 1 1 1\nx")
    except ValueError as exc:
        assert "expected EDIT header" in str(exc)
    else:
        raise AssertionError("explanatory preface was unexpectedly accepted")


def test_line_span_out_of_bounds_fails_closed() -> None:
    blueprint = _blueprint("repository-surgery-selection-boundary-0001")
    try:
        extract_line_span_patch(b"EDIT app.py 999 1 1\nx", blueprint)
    except ValueError as exc:
        assert "outside app.py" in str(exc)
    else:
        raise AssertionError("out-of-range edit was unexpectedly accepted")
