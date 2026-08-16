import hashlib

from plural_cognition.collective.candidate_pool_v2_calibration_protocol import (
    CALIBRATION_TASK_IDS_V2,
)
from plural_cognition.collective.candidate_pool_v2_selection_protocol import (
    SELECTION_TASK_IDS_V2,
)
from plural_cognition.collective.candidate_pool_v3_full_file import (
    extract_full_file_patch_v3,
    gold_full_file_output_v3,
    solver_prompt_transport_v3,
)
from plural_cognition.collective.candidate_pool_v3_representation_protocol import (
    V3_DEVELOPMENT_CANDIDATE_IDS,
    V3_DEFECT_FAMILIES,
)
from plural_cognition.collective.repository_surgery_calibration_pack_v3 import (
    CALIBRATION_SEEDS_V3,
    CALIBRATION_TASK_IDS_V3,
    calibration_blueprints_v3,
    validate_calibration_pack_v3_freshness,
)


def test_v3_calibration_pack_is_fresh_balanced_and_candidate_agnostic() -> None:
    validate_calibration_pack_v3_freshness()
    blueprints = calibration_blueprints_v3()

    assert tuple(item.task_id for item in blueprints) == CALIBRATION_TASK_IDS_V3
    assert tuple(item.generation_seed for item in blueprints) == CALIBRATION_SEEDS_V3
    assert tuple(item.mutation_kind.value for item in blueprints) == V3_DEFECT_FAMILIES
    assert len(blueprints) == 6
    assert len(set(CALIBRATION_TASK_IDS_V3)) == 6
    assert not (set(CALIBRATION_TASK_IDS_V3) & set(CALIBRATION_TASK_IDS_V2))
    assert not (set(CALIBRATION_TASK_IDS_V3) & set(SELECTION_TASK_IDS_V2))
    assert V3_DEVELOPMENT_CANDIDATE_IDS == (
        "qwen3-8b-q8",
        "qwen2.5-coder-14b-q5km",
        "devstral-24b-q4km",
        "gpt-oss-20b-mxfp4",
    )


def test_every_v3_calibration_prompt_uses_frozen_v3_representation() -> None:
    prompt_hashes = []
    for blueprint in calibration_blueprints_v3():
        prompt = solver_prompt_transport_v3(blueprint)
        text = prompt.decode("utf-8")
        prompt_hashes.append(hashlib.sha256(prompt).hexdigest())

        assert "ALLOWED_FILE_PATHS" in text
        assert "relative/file.py" not in text
        assert "FILE relative/" not in text
        for path, _raw in blueprint.buggy_files:
            assert f"- {path}" in text

        gold = gold_full_file_output_v3(blueprint)
        patch, _representation = extract_full_file_patch_v3(gold, blueprint)
        assert patch.endswith(b"\n")

    assert len(set(prompt_hashes)) == 6


def test_v3_multi_file_calibration_requires_two_file_repair() -> None:
    blueprint = next(
        item
        for item in calibration_blueprints_v3()
        if item.task_id == "repository-surgery-calibration-v3-multi-file-0001"
    )
    buggy = dict(blueprint.buggy_files)
    clean = dict(blueprint.clean_files)

    changed = tuple(path for path in sorted(clean) if clean[path] != buggy[path])
    assert changed == ("app.py", "fees.py")

    gold = gold_full_file_output_v3(blueprint)
    assert b"FILE app.py\n" in gold
    assert b"FILE fees.py\n" in gold
    assert gold.count(b"<<<<<<< CONTENT") == 2
    assert gold.count(b">>>>>>> CONTENT") == 2
