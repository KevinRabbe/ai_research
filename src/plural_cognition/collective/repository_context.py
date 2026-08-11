"""Deterministic bounded context access over content-addressed repository snapshots.

This is the first concrete ContextBackend. It reads only RepositorySnapshot and
ContentStore state already supplied to it; it never traverses the host checkout,
opens the network, invokes a model, or executes repository code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Any, Iterable

from .artifacts import ResourceUsage
from .content_store import ContentStore
from .context_access import (
    ContextObservation,
    ContextOperation,
    ContextQuery,
)
from .repository import RepositorySnapshot, load_repository_snapshot
from .runtime import ReferenceKind

REPOSITORY_TREE_QUERY_SCHEMA = "plural-cognition-repository-tree-query-v1"
REPOSITORY_SEARCH_QUERY_SCHEMA = "plural-cognition-repository-search-query-v1"
REPOSITORY_READ_QUERY_SCHEMA = "plural-cognition-repository-read-query-v1"
REPOSITORY_CONTEXT_RESULT_SCHEMA = "plural-cognition-repository-context-result-v1"


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _validate_relative_path(value: str, field: str) -> None:
    if type(value) is not str or not value:
        raise ValueError(f"{field} must be a non-empty normalized relative path")
    if "\\" in value:
        raise ValueError(f"{field} must use POSIX separators")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value:
        raise ValueError(f"{field} must be normalized and relative")
    if any(part in ("", ".", "..") for part in path.parts):
        raise ValueError(f"{field} contains unsafe path components")


def _optional_prefix(value: str | None) -> None:
    if value is not None:
        _validate_relative_path(value, "path_prefix")


def _positive_int(value: int, field: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{field} must be a positive integer")


def _path_matches_prefix(path: str, prefix: str | None) -> bool:
    return prefix is None or path == prefix or path.startswith(prefix + "/")


class RepositoryContextError(RuntimeError):
    """Raised when a repository-context request cannot be fulfilled safely."""


@dataclass(frozen=True, slots=True)
class RepositoryTreeQuery:
    path_prefix: str | None = None

    def __post_init__(self) -> None:
        _optional_prefix(self.path_prefix)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": REPOSITORY_TREE_QUERY_SCHEMA,
            "path_prefix": self.path_prefix,
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class RepositorySearchQuery:
    needle: str
    path_prefix: str | None = None

    def __post_init__(self) -> None:
        if type(self.needle) is not str or not self.needle:
            raise ValueError("needle must be a non-empty string")
        if "\n" in self.needle or "\r" in self.needle:
            raise ValueError("needle must be a single-line literal")
        _optional_prefix(self.path_prefix)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": REPOSITORY_SEARCH_QUERY_SCHEMA,
            "needle": self.needle,
            "path_prefix": self.path_prefix,
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class RepositoryReadQuery:
    path: str
    start_line: int
    line_count: int

    def __post_init__(self) -> None:
        _validate_relative_path(self.path, "path")
        _positive_int(self.start_line, "start_line")
        _positive_int(self.line_count, "line_count")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": REPOSITORY_READ_QUERY_SCHEMA,
            "path": self.path,
            "start_line": self.start_line,
            "line_count": self.line_count,
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.canonical_payload())

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


def _load_query_payload(raw: bytes, operation: ContextOperation):
    try:
        payload = json.loads(raw.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RepositoryContextError("repository context query payload is invalid JSON") from exc
    if type(payload) is not dict:
        raise RepositoryContextError("repository context query payload must be an object")

    if operation is ContextOperation.TREE:
        if set(payload) != {"schema", "path_prefix"} or payload.get("schema") != REPOSITORY_TREE_QUERY_SCHEMA:
            raise RepositoryContextError("invalid repository TREE query payload")
        result = RepositoryTreeQuery(payload["path_prefix"])
    elif operation is ContextOperation.SEARCH:
        if set(payload) != {"schema", "needle", "path_prefix"} or payload.get("schema") != REPOSITORY_SEARCH_QUERY_SCHEMA:
            raise RepositoryContextError("invalid repository SEARCH query payload")
        result = RepositorySearchQuery(payload["needle"], payload["path_prefix"])
    elif operation is ContextOperation.READ:
        if set(payload) != {"schema", "path", "start_line", "line_count"} or payload.get("schema") != REPOSITORY_READ_QUERY_SCHEMA:
            raise RepositoryContextError("invalid repository READ query payload")
        result = RepositoryReadQuery(
            payload["path"],
            payload["start_line"],
            payload["line_count"],
        )
    else:
        raise RepositoryContextError(
            f"repository backend does not implement {operation.value}"
        )

    if result.canonical_bytes() != raw:
        raise RepositoryContextError("repository context query payload is not canonical")
    return result


def _tree_items(
    snapshot: RepositorySnapshot,
    query: RepositoryTreeQuery,
) -> Iterable[dict[str, Any]]:
    for item in snapshot.files:
        if _path_matches_prefix(item.path, query.path_prefix):
            yield {"path": item.path, "size_bytes": item.size_bytes}


def _search_items(
    snapshot: RepositorySnapshot,
    query: RepositorySearchQuery,
    store: ContentStore,
) -> Iterable[dict[str, Any]]:
    for item in snapshot.files:
        if not _path_matches_prefix(item.path, query.path_prefix):
            continue
        raw = store.get_bytes(item.content_sha256)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            offset = 0
            while True:
                column = line.find(query.needle, offset)
                if column < 0:
                    break
                yield {
                    "path": item.path,
                    "line": line_number,
                    "column": column + 1,
                }
                offset = column + max(1, len(query.needle))


def _read_items(
    snapshot: RepositorySnapshot,
    query: RepositoryReadQuery,
    store: ContentStore,
) -> Iterable[dict[str, Any]]:
    entry = next((item for item in snapshot.files if item.path == query.path), None)
    if entry is None:
        raise RepositoryContextError(f"repository path not found: {query.path}")
    raw = store.get_bytes(entry.content_sha256)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RepositoryContextError(
            f"repository READ requires UTF-8 text: {query.path}"
        ) from exc
    lines = text.splitlines()
    start = query.start_line - 1
    end = min(len(lines), start + query.line_count)
    for index in range(start, end):
        yield {"line": index + 1, "text": lines[index]}


def _bounded_result(
    operation: ContextOperation,
    items: Iterable[dict[str, Any]],
    *,
    max_result_bytes: int,
    max_items: int,
) -> tuple[bytes, int, bool]:
    selected: list[dict[str, Any]] = []
    iterator = iter(items)
    truncated = False

    while len(selected) < max_items:
        try:
            candidate = next(iterator)
        except StopIteration:
            break
        trial = {
            "schema": REPOSITORY_CONTEXT_RESULT_SCHEMA,
            "operation": operation.value,
            "items": selected + [candidate],
            "truncated": True,
        }
        if len(_canonical_json_bytes(trial)) > max_result_bytes:
            truncated = True
            break
        selected.append(candidate)

    if not truncated and len(selected) == max_items:
        try:
            next(iterator)
        except StopIteration:
            pass
        else:
            truncated = True

    payload = {
        "schema": REPOSITORY_CONTEXT_RESULT_SCHEMA,
        "operation": operation.value,
        "items": selected,
        "truncated": truncated,
    }
    raw = _canonical_json_bytes(payload)
    if len(raw) > max_result_bytes:
        raise RepositoryContextError(
            "context budget is too small for repository result envelope"
        )
    return raw, len(selected), truncated


@dataclass(slots=True)
class RepositorySnapshotContextBackend:
    """TREE/SEARCH/READ backend over immutable RepositorySnapshot content."""

    store: ContentStore

    def query(self, request: ContextQuery) -> ContextObservation:
        if not isinstance(request, ContextQuery):
            raise TypeError("request must be ContextQuery")
        if request.source.kind is not ReferenceKind.REPOSITORY:
            raise RepositoryContextError("repository backend requires repository source")
        if request.operation not in (
            ContextOperation.TREE,
            ContextOperation.SEARCH,
            ContextOperation.READ,
        ):
            raise RepositoryContextError(
                f"repository backend does not implement {request.operation.value}"
            )

        snapshot = load_repository_snapshot(request.source.content_sha256, self.store)
        raw_query = self.store.get_bytes(request.query_payload_sha256)
        query_payload = _load_query_payload(raw_query, request.operation)
        if query_payload.sha256 != request.query_payload_sha256:
            raise RepositoryContextError("query payload digest is inconsistent")

        if isinstance(query_payload, RepositoryTreeQuery):
            items = _tree_items(snapshot, query_payload)
        elif isinstance(query_payload, RepositorySearchQuery):
            items = _search_items(snapshot, query_payload, self.store)
        elif isinstance(query_payload, RepositoryReadQuery):
            items = _read_items(snapshot, query_payload, self.store)
        else:
            raise AssertionError("unhandled repository query payload")

        result, returned_items, truncated = _bounded_result(
            request.operation,
            items,
            max_result_bytes=request.budget.max_result_bytes,
            max_items=request.budget.max_items,
        )
        result_sha256 = self.store.put_bytes(result)
        resources = ResourceUsage(
            tool_calls=1,
            retrieval_bytes=len(result),
        )
        return ContextObservation(
            query_sha256=request.sha256,
            budget=request.budget,
            result_content_sha256=result_sha256,
            result_bytes=len(result),
            returned_items=returned_items,
            truncated=truncated,
            resources=resources,
        )
