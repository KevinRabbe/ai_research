from __future__ import annotations

from pathlib import Path

import pytest

from plural_cognition.collective.docker_bootstrap import apply_unified_diff


def test_bootstrap_applies_strict_modify_create_delete_patch(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "module.py").write_text("VALUE = 1\nREMOVE = True\n", encoding="utf-8")
    (repository / "obsolete.py").write_text("OLD = True\n", encoding="utf-8")

    patch = (
        b"diff --git a/module.py b/module.py\n"
        b"--- a/module.py\n"
        b"+++ b/module.py\n"
        b"@@ -1,2 +1,2 @@\n"
        b"-VALUE = 1\n"
        b"+VALUE = 2\n"
        b" REMOVE = True\n"
        b"diff --git a/new.py b/new.py\n"
        b"new file mode 100644\n"
        b"--- /dev/null\n"
        b"+++ b/new.py\n"
        b"@@ -0,0 +1 @@\n"
        b"+CREATED = True\n"
        b"diff --git a/obsolete.py b/obsolete.py\n"
        b"deleted file mode 100644\n"
        b"--- a/obsolete.py\n"
        b"+++ /dev/null\n"
        b"@@ -1 +0,0 @@\n"
        b"-OLD = True\n"
    )

    apply_unified_diff(repository, patch)

    assert (repository / "module.py").read_text(encoding="utf-8") == (
        "VALUE = 2\nREMOVE = True\n"
    )
    assert (repository / "new.py").read_text(encoding="utf-8") == "CREATED = True\n"
    assert not (repository / "obsolete.py").exists()


def test_bootstrap_rejects_patch_context_that_does_not_match(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    patch = (
        b"--- a/module.py\n"
        b"+++ b/module.py\n"
        b"@@ -1 +1 @@\n"
        b"-VALUE = 999\n"
        b"+VALUE = 2\n"
    )

    with pytest.raises(ValueError, match="context does not match"):
        apply_unified_diff(repository, patch)


def test_bootstrap_rejects_path_traversal(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    patch = (
        b"--- /dev/null\n"
        b"+++ b/../escape.py\n"
        b"@@ -0,0 +1 @@\n"
        b"+ESCAPE = True\n"
    )

    with pytest.raises(ValueError, match="unsafe"):
        apply_unified_diff(repository, patch)
    assert not (tmp_path / "escape.py").exists()


def test_bootstrap_rejects_crlf_patch_and_nonterminated_patch(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()

    with pytest.raises(ValueError, match="UTF-8 LF"):
        apply_unified_diff(repository, b"--- a/x\r\n+++ b/x\r\n")
    with pytest.raises(ValueError, match="end with LF"):
        apply_unified_diff(repository, b"--- a/x\n+++ b/x\n@@ -0,0 +0,0 @@")


def test_bootstrap_rejects_rename_patch(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "old.py").write_text("VALUE = 1\n", encoding="utf-8")
    patch = (
        b"--- a/old.py\n"
        b"+++ b/new.py\n"
        b"@@ -1 +1 @@\n"
        b"-VALUE = 1\n"
        b"+VALUE = 2\n"
    )

    with pytest.raises(ValueError, match="rename"):
        apply_unified_diff(repository, patch)
