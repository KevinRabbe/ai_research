import pytest

from plural_cognition.collective.candidate_pool_v2_selection_counterfactual_forensics import (
    LEVELS,
    counterfactual_patch,
    parse_counterfactual_replacements,
)
from plural_cognition.collective.repository_surgery_selection_pack_v2 import (
    selection_blueprints_v2,
)


def _clean(blueprint, path: str) -> str:
    text = dict(blueprint.clean_files)[path].decode("utf-8")
    return text[:-1] if text.endswith("\n") else text


def test_counterfactual_levels_are_cumulative_and_named() -> None:
    assert LEVELS == (
        "frozen-strict",
        "surface-tolerant",
        "prompt-path-tolerant",
        "bare-file-tolerant",
    )


def test_surface_level_accepts_colon_header_without_code_repair() -> None:
    blueprint = selection_blueprints_v2()[0]
    raw = (
        "FILE: app.py\n<<<<<<< CONTENT\n"
        + _clean(blueprint, "app.py")
        + "\n>>>>>>> CONTENT"
    ).encode("utf-8")
    with pytest.raises(ValueError, match="expected FILE header"):
        parse_counterfactual_replacements(raw, blueprint, level=0)
    blocks = parse_counterfactual_replacements(raw, blueprint, level=1)
    assert [item.path for item in blocks] == ["app.py"]
    assert counterfactual_patch(raw, blueprint, level=1).startswith(b"--- a/app.py\n+++ b/app.py\n")


def test_surface_level_accepts_blank_separator_between_marked_blocks() -> None:
    blueprint = next(
        item for item in selection_blueprints_v2()
        if item.task_id == "repository-surgery-selection-v2-multi-file-0001"
    )
    raw = (
        "FILE app.py\n<<<<<<< CONTENT\n"
        + _clean(blueprint, "app.py")
        + "\n>>>>>>> CONTENT\n\n"
        + "FILE pricing.py\n<<<<<<< CONTENT\n"
        + _clean(blueprint, "pricing.py")
        + "\n>>>>>>> CONTENT"
    ).encode("utf-8")
    with pytest.raises(ValueError, match="expected FILE header"):
        parse_counterfactual_replacements(raw, blueprint, level=0)
    blocks = parse_counterfactual_replacements(raw, blueprint, level=1)
    assert [item.path for item in blocks] == ["app.py", "pricing.py"]


def test_prompt_path_level_only_repairs_literal_relative_prefix() -> None:
    blueprint = selection_blueprints_v2()[0]
    raw = (
        "FILE relative/app.py\n<<<<<<< CONTENT\n"
        + _clean(blueprint, "app.py")
        + "\n>>>>>>> CONTENT"
    ).encode("utf-8")
    with pytest.raises(ValueError, match="not solver-visible"):
        parse_counterfactual_replacements(raw, blueprint, level=1)
    blocks = parse_counterfactual_replacements(raw, blueprint, level=2)
    assert [item.path for item in blocks] == ["app.py"]

    arbitrary = raw.replace(b"relative/app.py", b"other/app.py")
    with pytest.raises(ValueError, match="not solver-visible"):
        parse_counterfactual_replacements(arbitrary, blueprint, level=3)


def test_bare_file_level_accepts_complete_content_without_markers() -> None:
    blueprint = selection_blueprints_v2()[0]
    raw = ("FILE app.py\n" + _clean(blueprint, "app.py")).encode("utf-8")
    with pytest.raises(ValueError, match="expected CONTENT opener"):
        parse_counterfactual_replacements(raw, blueprint, level=2)
    blocks = parse_counterfactual_replacements(raw, blueprint, level=3)
    assert [item.path for item in blocks] == ["app.py"]
    assert counterfactual_patch(raw, blueprint, level=3).startswith(b"--- a/app.py\n+++ b/app.py\n")


def test_bare_file_level_can_split_multiple_complete_files() -> None:
    blueprint = next(
        item for item in selection_blueprints_v2()
        if item.task_id == "repository-surgery-selection-v2-multi-file-0002"
    )
    raw = (
        "FILE app.py\n"
        + _clean(blueprint, "app.py")
        + "\n\nFILE normalize.py\n"
        + _clean(blueprint, "normalize.py")
    ).encode("utf-8")
    blocks = parse_counterfactual_replacements(raw, blueprint, level=3)
    assert [item.path for item in blocks] == ["app.py", "normalize.py"]
