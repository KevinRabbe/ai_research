import pytest

from plural_cognition.collective.candidate_pool_v3_full_file import (
    OUTPUT_CONTRACT_V3,
    build_solver_prompt_v3,
    extract_full_file_patch_v3,
    gold_full_file_output_v3,
    parse_full_file_replacements_v3,
    solver_prompt_transport_v3,
)
from plural_cognition.collective.repository_surgery_selection_pack_v2 import (
    selection_blueprints_v2,
)


def _blueprint(task_id: str):
    return next(item for item in selection_blueprints_v2() if item.task_id == task_id)


def test_v3_accepts_strict_and_optional_colon_file_headers() -> None:
    strict = b"FILE app.py\n<<<<<<< CONTENT\nprint('ok')\n>>>>>>> CONTENT"
    colon = b"FILE: app.py\n<<<<<<< CONTENT\nprint('ok')\n>>>>>>> CONTENT"

    strict_blocks = parse_full_file_replacements_v3(strict)
    colon_blocks = parse_full_file_replacements_v3(colon)

    assert strict_blocks == colon_blocks
    assert strict_blocks[0].path == "app.py"
    assert strict_blocks[0].content_lines == ("print('ok')",)


def test_v3_accepts_blank_lines_between_structured_blocks() -> None:
    raw = (
        b"FILE app.py\n<<<<<<< CONTENT\na = 1\n>>>>>>> CONTENT\n\n\n"
        b"FILE: helper.py\n<<<<<<< CONTENT\nb = 2\n>>>>>>> CONTENT\n"
    )
    blocks = parse_full_file_replacements_v3(raw)
    assert tuple(item.path for item in blocks) == ("app.py", "helper.py")


def test_v3_rejects_bare_file_output() -> None:
    with pytest.raises(ValueError, match="expected CONTENT opener"):
        parse_full_file_replacements_v3(b"FILE app.py\nprint('ok')")


def test_v3_rejects_prompt_induced_relative_prefix_in_production() -> None:
    blueprint = _blueprint("repository-surgery-selection-v2-api-contract-0001")
    raw = gold_full_file_output_v3(blueprint).replace(b"FILE app.py", b"FILE relative/app.py")

    with pytest.raises(ValueError, match="path is not solver-visible"):
        extract_full_file_patch_v3(raw, blueprint)


def test_v3_prompt_uses_exact_visible_paths_without_relative_placeholder() -> None:
    blueprint = _blueprint("repository-surgery-selection-v2-multi-file-0001")
    prompt = build_solver_prompt_v3(blueprint).decode("utf-8")

    assert "ALLOWED_FILE_PATHS" in prompt
    assert "- app.py" in prompt
    assert "- pricing.py" in prompt
    assert "FILE app.py" in prompt
    assert "relative/file.py" not in prompt
    assert "FILE relative/" not in prompt
    assert "Do not invent path prefixes" in prompt
    assert "CONTENT opener and closer lines are mandatory" in prompt

    transported = solver_prompt_transport_v3(blueprint)
    assert not transported.endswith(b"\n")
    assert build_solver_prompt_v3(blueprint) == transported + b"\n"


def test_v3_gold_output_materializes_deterministic_full_file_patch() -> None:
    blueprint = _blueprint("repository-surgery-selection-v2-multi-file-0002")
    raw = gold_full_file_output_v3(blueprint)
    patch, representation = extract_full_file_patch_v3(raw, blueprint)

    assert representation == OUTPUT_CONTRACT_V3
    assert patch.endswith(b"\n")
    assert b"--- a/app.py\n+++ b/app.py" in patch
    assert b"--- a/normalize.py\n+++ b/normalize.py" in patch
    assert b'{"sku": value}' in patch
    assert b"value.strip().upper()" in patch


def test_v3_rejects_duplicate_paths_and_markdown() -> None:
    repeated = (
        b"FILE app.py\n<<<<<<< CONTENT\na = 1\n>>>>>>> CONTENT\n\n"
        b"FILE: app.py\n<<<<<<< CONTENT\na = 2\n>>>>>>> CONTENT"
    )
    with pytest.raises(ValueError, match="each FILE path at most once"):
        parse_full_file_replacements_v3(repeated)

    with pytest.raises(ValueError, match="markdown fencing"):
        parse_full_file_replacements_v3(
            b"```\nFILE app.py\n<<<<<<< CONTENT\na = 1\n>>>>>>> CONTENT\n```"
        )
