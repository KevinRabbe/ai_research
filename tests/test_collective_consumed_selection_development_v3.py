from __future__ import annotations

from plural_cognition.collective.consumed_selection_development_v3 import (
    CANDIDATE_OUTPUT_INTERPRETER,
    DEVELOPMENT_PROTOCOL_SHA256_V3,
    OUTPUT_CONTRACT,
    PROMPT_SOURCE_REPRESENTATION,
    build_solver_prompt_v3,
    development_protocol_payload_v3,
    extract_search_replace_patch,
    parse_search_replace_blocks,
)
from plural_cognition.collective.local_operational_freeze_v1 import FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1
from plural_cognition.collective.repository_surgery_selection_outcome_freeze_v1 import FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256
from plural_cognition.collective.repository_surgery_selection_pack_v1 import selection_blueprints


def _blueprint(task_id: str):
    return next(item for item in selection_blueprints() if item.task_id == task_id)


def test_protocol_binds_consumed_outcome_and_preserves_frozen_resources() -> None:
    payload = development_protocol_payload_v3()
    assert payload["consumed_selection_outcome_freeze_sha256"] == FINAL_REPOSITORY_SURGERY_SELECTION_OUTCOME_FREEZE_SHA256
    assert payload["operational_config_freeze_sha256"] == FINAL_LOCAL_OPERATIONAL_CONFIG_FREEZE_V1.sha256
    assert payload["prompt_source_representation"] == PROMPT_SOURCE_REPRESENTATION
    assert payload["output_contract"] == OUTPUT_CONTRACT
    assert payload["candidate_output_interpreter"] == CANDIDATE_OUTPUT_INTERPRETER
    assert payload["replacement_semantics"] == "exactly-once-current-file-state-v1"
    assert payload["context_tokens"] == 4096
    assert payload["predict_tokens"] == 2048
    assert payload["temperature"] == 0.0
    assert payload["seed"] == 1
    assert payload["max_attempts"] == 1
    assert payload["fuzzy_matching"] is False
    assert payload["candidate_output_repair"] is False
    assert payload["protected_evaluator_visible_to_interpreter"] is False
    assert len(DEVELOPMENT_PROTOCOL_SHA256_V3) == 64


def test_prompt_uses_plain_source_and_literal_search_replace_contract() -> None:
    blueprint = _blueprint("repository-surgery-selection-api-contract-0002")
    prompt = build_solver_prompt_v3(blueprint)
    assert b"FILE relative/file.py" in prompt
    assert b"<<<<<<< SEARCH" in prompt
    assert b">>>>>>> REPLACE" in prompt
    assert b'json.dumps({"value": total}' in prompt
    assert b"L0001|" not in prompt
    assert b'"old"' not in prompt
    assert prompt.endswith(b"\n")


def test_api_contract_fragment_materializes_gold_patch() -> None:
    blueprint = _blueprint("repository-surgery-selection-api-contract-0002")
    raw = b"FILE app.py\n<<<<<<< SEARCH\n{\"value\": total}\n=======\n{\"total\": total}\n>>>>>>> REPLACE"
    patch, mode = extract_search_replace_patch(raw, blueprint)
    assert mode == "raw-search-replace"
    assert patch == blueprint.gold_patch


def test_error_handling_one_line_fragment_materializes_gold_patch() -> None:
    blueprint = _blueprint("repository-surgery-selection-error-handling-0001")
    raw = b"FILE app.py\n<<<<<<< SEARCH\nport < 0\n=======\nport <= 0\n>>>>>>> REPLACE"
    patch, _ = extract_search_replace_patch(raw, blueprint)
    assert patch == blueprint.gold_patch


def test_error_handling_multiline_replacement_materializes_gold_patch() -> None:
    blueprint = _blueprint("repository-surgery-selection-error-handling-0002")
    raw = (
        b"FILE app.py\n<<<<<<< SEARCH\n    return max(values)\n=======\n"
        b"    if mode == \"max\":\n        return max(values)\n    raise ValueError(\"unsupported mode\")\n"
        b">>>>>>> REPLACE"
    )
    patch, _ = extract_search_replace_patch(raw, blueprint)
    assert patch == blueprint.gold_patch


def test_parser_is_strict_and_does_not_salvage_preface() -> None:
    try:
        parse_search_replace_blocks(
            b"Here is the fix:\nFILE app.py\n<<<<<<< SEARCH\nx\n=======\ny\n>>>>>>> REPLACE"
        )
    except ValueError as exc:
        assert "expected FILE header" in str(exc)
    else:
        raise AssertionError("explanatory preface was unexpectedly accepted")


def test_exact_search_mismatch_fails_closed_without_fuzzy_matching() -> None:
    blueprint = _blueprint("repository-surgery-selection-api-contract-0002")
    raw = (
        b"FILE app.py\n<<<<<<< SEARCH\n"
        b"sys.stdout.write(json.dumps({\"value\": total}, sort_keys=True, separators=(\",\":)) + \"\\n\")\n"
        b"=======\n"
        b"sys.stdout.write(json.dumps({\"total\": total}, sort_keys=True, separators=(\",\":)) + \"\\n\")\n"
        b">>>>>>> REPLACE"
    )
    try:
        extract_search_replace_patch(raw, blueprint)
    except ValueError as exc:
        assert "must occur exactly once" in str(exc)
    else:
        raise AssertionError("inexact SEARCH text was unexpectedly repaired or fuzzy-matched")
