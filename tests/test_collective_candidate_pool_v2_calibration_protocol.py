from __future__ import annotations

import inspect

from plural_cognition.collective import candidate_pool_v2_calibration_protocol as protocol
from plural_cognition.collective import candidate_pool_v2_full_file as full_file
from plural_cognition.collective.local_raw_calibration import validate_patch_against_blueprint
from plural_cognition.collective.repository_surgery_calibration_matrix import calibration_blueprints


def _blueprints():
    return calibration_blueprints()


def test_v2_calibration_protocol_identity_and_gate() -> None:
    payload = protocol.candidate_pool_v2_calibration_protocol_payload()
    assert protocol.FINAL_CALIBRATION_PROTOCOL_SHA256_V2 == protocol.EXPECTED_CALIBRATION_PROTOCOL_SHA256_V2
    assert protocol.FINAL_CALIBRATION_PROTOCOL_SHA256_V2 == "99b1584dbc91c8dc0c96ad0e3cb212e965dffdde1a63b03c5be8fff81a8b2cc1"
    assert tuple(payload["candidate_ids"]) == protocol.CANDIDATE_IDS_V2
    assert len(protocol.CANDIDATE_IDS_V2) == 6
    assert tuple(payload["calibration_matrix"]["task_ids"]) == protocol.CALIBRATION_TASK_IDS_V2
    assert payload["calibration_matrix"]["task_count_per_candidate"] == 6
    assert payload["gate"]["required_parse_valid_count"] == 6
    assert payload["gate"]["minimum_solved_count"] == 4
    assert payload["representation"]["max_attempts"] == 1
    assert payload["representation"]["self_review"] is False
    assert payload["representation"]["candidate_output_repair"] is False
    assert payload["representation"]["fuzzy_matching"] is False
    assert payload["gate"]["per_candidate_prompt_tuning_after_observation"] is False
    assert payload["gate"]["reruns_for_failed_candidates"] is False
    assert payload["evidence_policy"]["selection_evidence"] is False
    budget = payload["resource_budget"]
    assert budget["context_tokens"] == 4096
    assert budget["predict_tokens"] == 2048
    assert budget["gpu_layers"] == "all"
    assert budget["device"] == "CUDA0"
    assert budget["fit"] == "off"
    assert budget["split_mode"] == "none"
    assert budget["cache_type_k"] == budget["cache_type_v"] == "f16"
    assert budget["load_mode"] == "mmap"
    assert budget["offline"] is True


def test_v2_calibration_protocol_binds_successful_load_repair() -> None:
    payload = protocol.candidate_pool_v2_calibration_protocol_payload()
    repair = payload["load_observer_repair"]
    assert repair["software_revision"] == "15b55a51e3fa35e4f146009d3af18c4769cfafb1"
    assert repair["suite_file_sha256"] == "5d8a0e0d0ff63944d4e94e52ee3fb33a09065e925cd31bc82242b088c8190952"
    assert repair["suite_report_sha256"] == "7315b0faf8c912ef353376c38d1c238e53e2b0cd1900d1f406a95f25cd01faec"
    assert repair["qualified_count"] == 3
    assert repair["failed_count"] == 0


def test_v2_calibration_matrix_is_exactly_six_frozen_defect_tasks() -> None:
    blueprints = _blueprints()
    assert tuple(item.task_id for item in blueprints) == protocol.CALIBRATION_TASK_IDS_V2
    assert len(blueprints) == 6
    assert len({item.mutation_kind for item in blueprints}) == 6


def test_v2_whole_file_prompt_has_one_output_contract() -> None:
    for blueprint in _blueprints():
        prompt = full_file.build_solver_prompt_v2(blueprint)
        assert prompt.endswith(b"\n")
        assert b"FILE relative/file.py" in prompt
        assert b"<<<<<<< CONTENT" in prompt
        assert b">>>>>>> CONTENT" in prompt
        assert b"complete corrected file" in prompt
        assert b"return a unified diff only" not in prompt.lower()
        assert b"```" not in prompt
        transported = full_file.solver_prompt_transport_v2(blueprint)
        assert transported == prompt[:-1]
        assert not transported.endswith(b"\n")


def test_v2_issue_normalization_changes_only_obsolete_serialization_clause() -> None:
    for blueprint in _blueprints():
        original = blueprint.issue_prompt.decode("utf-8").strip()
        assert original.count(full_file.OBSOLETE_SERIALIZATION_CLAUSE) == 1
        expected = original.replace(full_file.OBSOLETE_SERIALIZATION_CLAUSE, ".", 1)
        assert full_file.normalized_issue_text_v2(blueprint) == expected


def test_v2_gold_full_file_outputs_reconstruct_clean_files_and_valid_patches() -> None:
    for blueprint in _blueprints():
        raw = full_file.gold_full_file_output_v2(blueprint)
        blocks = full_file.parse_full_file_replacements_v2(raw)
        changed = full_file._materialize_replacements_v2(blueprint=blueprint, blocks=blocks)
        clean = {path: data.decode("utf-8") for path, data in blueprint.clean_files}
        buggy = {path: data.decode("utf-8") for path, data in blueprint.buggy_files}
        assert changed
        assert set(changed) == {path for path in clean if clean[path] != buggy[path]}
        assert all(changed[path] == clean[path] for path in changed)
        patch, mode = full_file.extract_full_file_patch_v2(raw, blueprint)
        assert mode == "raw-full-file-replacement"
        validate_patch_against_blueprint(patch, blueprint)


def test_v2_whole_file_parser_preserves_payload_and_allows_wrapper_whitespace() -> None:
    blueprint = next(item for item in _blueprints() if item.task_id.endswith("boundary-0001"))
    clean = dict(blueprint.clean_files)["app.py"].decode("utf-8")[:-1]
    raw = f"  FILE app.py\t\n \t<<<<<<< CONTENT\t\n{clean}\n  >>>>>>> CONTENT \t".encode("utf-8")
    patch, _ = full_file.extract_full_file_patch_v2(raw, blueprint)
    validate_patch_against_blueprint(patch, blueprint)


def test_v2_calibration_modules_do_not_import_selection_material() -> None:
    source = inspect.getsource(protocol) + inspect.getsource(full_file)
    assert "repository_surgery_selection" not in source
    assert "selection_blueprints" not in source
