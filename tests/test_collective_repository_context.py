from __future__ import annotations

import json

import pytest

from plural_cognition.collective.artifacts import TaskIdentity
from plural_cognition.collective.content_store import FileContentStore
from plural_cognition.collective.context_access import (
    ContextBudget,
    ContextOperation,
    ContextQuery,
)
from plural_cognition.collective.repository import snapshot_directory
from plural_cognition.collective.repository_context import (
    REPOSITORY_CONTEXT_RESULT_SCHEMA,
    RepositoryContextError,
    RepositoryReadQuery,
    RepositorySearchQuery,
    RepositorySnapshotContextBackend,
    RepositoryTreeQuery,
)
from plural_cognition.collective.runtime import (
    CognitivePhase,
    CognitiveReference,
    ReferenceKind,
    ReferenceScope,
)


def _query(
    *,
    store: FileContentStore,
    repository_sha256: str,
    operation: ContextOperation,
    payload: bytes,
    max_result_bytes: int = 4096,
    max_items: int = 100,
) -> ContextQuery:
    payload_sha256 = store.put_bytes(payload)
    return ContextQuery(
        task=TaskIdentity("task-1", "repository-surgery-v0", "0" * 64),
        query_id=f"query-{operation.value}",
        requester_id="mind-a",
        phase=CognitivePhase.INDEPENDENT,
        source=CognitiveReference(
            kind=ReferenceKind.REPOSITORY,
            content_sha256=repository_sha256,
            scope=ReferenceScope.SYSTEM,
        ),
        operation=operation,
        query_payload_sha256=payload_sha256,
        protocol_sha256="1" * 64,
        budget=ContextBudget(
            max_result_bytes=max_result_bytes,
            max_items=max_items,
        ),
    )


def _repository(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    # Exact bytes keep RepositorySnapshot identities and size assertions
    # independent of host newline translation (notably CRLF on Windows).
    (root / "README.md").write_bytes(b"alpha\nbeta alpha\n")
    src = root / "src"
    src.mkdir()
    (src / "main.py").write_bytes(
        b"def main():\n    value = 'alpha'\n    return value\n"
    )
    store = FileContentStore(tmp_path / "store")
    stored = snapshot_directory(root, store)
    return store, stored.manifest_sha256


def _payload(store: FileContentStore, observation) -> dict:
    assert observation.resources.tool_calls == 1
    assert observation.resources.retrieval_bytes == observation.result_bytes
    raw = store.get_bytes(observation.result_content_sha256)
    assert len(raw) == observation.result_bytes
    payload = json.loads(raw.decode("ascii"))
    assert payload["schema"] == REPOSITORY_CONTEXT_RESULT_SCHEMA
    return payload


def test_tree_is_deterministic_and_bounded(tmp_path) -> None:
    store, repository_sha256 = _repository(tmp_path)
    backend = RepositorySnapshotContextBackend(store)
    query_payload = RepositoryTreeQuery()
    request = _query(
        store=store,
        repository_sha256=repository_sha256,
        operation=ContextOperation.TREE,
        payload=query_payload.canonical_bytes(),
        max_items=1,
    )

    observation = backend.query(request)
    payload = _payload(store, observation)

    assert observation.binds(request)
    assert observation.returned_items == 1
    assert observation.truncated is True
    assert payload["operation"] == "tree"
    assert payload["items"] == [{"path": "README.md", "size_bytes": 17}]
    assert payload["truncated"] is True


def test_search_returns_literal_occurrences_in_path_order(tmp_path) -> None:
    store, repository_sha256 = _repository(tmp_path)
    backend = RepositorySnapshotContextBackend(store)
    query_payload = RepositorySearchQuery("alpha")
    request = _query(
        store=store,
        repository_sha256=repository_sha256,
        operation=ContextOperation.SEARCH,
        payload=query_payload.canonical_bytes(),
    )

    observation = backend.query(request)
    payload = _payload(store, observation)

    assert payload["items"] == [
        {"column": 1, "line": 1, "path": "README.md"},
        {"column": 6, "line": 2, "path": "README.md"},
        {"column": 14, "line": 2, "path": "src/main.py"},
    ]
    assert observation.truncated is False


def test_read_returns_requested_line_window(tmp_path) -> None:
    store, repository_sha256 = _repository(tmp_path)
    backend = RepositorySnapshotContextBackend(store)
    query_payload = RepositoryReadQuery("src/main.py", start_line=2, line_count=2)
    request = _query(
        store=store,
        repository_sha256=repository_sha256,
        operation=ContextOperation.READ,
        payload=query_payload.canonical_bytes(),
    )

    observation = backend.query(request)
    payload = _payload(store, observation)

    assert payload["items"] == [
        {"line": 2, "text": "    value = 'alpha'"},
        {"line": 3, "text": "    return value"},
    ]
    assert observation.returned_items == 2


def test_repository_backend_rejects_non_repository_source(tmp_path) -> None:
    store, repository_sha256 = _repository(tmp_path)
    query_payload = RepositoryTreeQuery()
    payload_sha256 = store.put_bytes(query_payload.canonical_bytes())
    request = ContextQuery(
        task=TaskIdentity("task-1", "repository-surgery-v0", "0" * 64),
        query_id="query-tree",
        requester_id="mind-a",
        phase=CognitivePhase.INDEPENDENT,
        source=CognitiveReference(
            kind=ReferenceKind.ARTIFACT,
            content_sha256=repository_sha256,
            scope=ReferenceScope.SYSTEM,
        ),
        operation=ContextOperation.TREE,
        query_payload_sha256=payload_sha256,
        protocol_sha256="1" * 64,
        budget=ContextBudget(max_result_bytes=4096, max_items=10),
    )

    with pytest.raises(RepositoryContextError, match="requires repository source"):
        RepositorySnapshotContextBackend(store).query(request)


def test_repository_backend_rejects_unsupported_operation(tmp_path) -> None:
    store, repository_sha256 = _repository(tmp_path)
    payload_sha256 = store.put_bytes(b"{}")
    request = ContextQuery(
        task=TaskIdentity("task-1", "repository-surgery-v0", "0" * 64),
        query_id="query-symbol",
        requester_id="mind-a",
        phase=CognitivePhase.INDEPENDENT,
        source=CognitiveReference(
            kind=ReferenceKind.REPOSITORY,
            content_sha256=repository_sha256,
            scope=ReferenceScope.SYSTEM,
        ),
        operation=ContextOperation.SYMBOL,
        query_payload_sha256=payload_sha256,
        protocol_sha256="1" * 64,
        budget=ContextBudget(max_result_bytes=4096, max_items=10),
    )

    with pytest.raises(RepositoryContextError, match="does not implement symbol"):
        RepositorySnapshotContextBackend(store).query(request)
