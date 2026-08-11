# Bounded External Context Access

## Status

This document freezes the generic interface through which a capable mind may inspect large external state without placing the entire repository, memory store, or experiment history into its active transformer context.

The interface is deliberately narrower than a full RLM or agent runtime. It defines requests, visibility, budgets, and immutable observations. It does not yet implement retrieval, filesystem traversal, embeddings, search indexes, symbol analysis, or autonomous recursion.

## 1. Motivation

The target architecture treats effective context as the state the system can reliably address, not merely the tokens simultaneously present in attention.

Instead of:

```text
question + entire repository + entire history
                 ↓
              model
                 ↓
              answer
```

use:

```text
small active working context
        ↓
explicit context query
        ↓
external repository / memory / artifacts
        ↓
bounded observation
        ↓
model continues reasoning
```

This keeps storage/state management outside the neural model while preserving exact provenance and resource accounting.

## 2. Query operations

The first architecture-independent operations are:

```text
TREE
SEARCH
READ
SYMBOL
REFERENCES
DEPENDENCIES
```

These are semantic operation classes, not a commitment to one implementation.

Examples of later concrete backends might map them to repository-tree traversal, lexical/semantic search, file-range reads, language-server queries, static dependency analysis, or memory retrieval.

## 3. Operation arguments remain external payloads

A generic `ContextQuery` does not embed arbitrary path strings, search expressions, or model-generated query text directly in its manifest.

Instead it binds an operation-specific payload by SHA-256:

```text
query_payload_sha256
```

For example, a later repository-search payload might encode:

```json
{
  "pattern": "update_enemy",
  "path_prefix": "src/ai"
}
```

while a symbol query may have a completely different structure.

This lets the generic runtime remain stable while domain-specific query languages evolve independently.

## 4. Source references

Every query targets a `CognitiveReference`.

Examples:

```text
repository://sha256/<digest>
memory://sha256/<digest>
experiment://sha256/<digest>
```

The source therefore has an exact content identity and visibility scope before retrieval begins.

## 5. Visibility is checked before access

The query binds:

```text
requester_id
cognitive phase
source reference
```

The first visibility rules are:

```text
SYSTEM source
  visible in all phases

PRIVATE_MIND source
  visible only when source.owner_id == requester_id

SHARED_COLLECTIVE source
  forbidden during INDEPENDENT
  permitted after the independent phase
```

This applies the same information-flow boundary to retrieval that already applies to runtime checkpoints.

A powerful external memory system must not become a hidden cross-mind communication channel.

## 6. Bounded retrieval

Every query contains a `ContextBudget`:

```text
max_result_bytes
max_items
```

The returned `ContextObservation` is invalid if it exceeds either ceiling.

This serves three purposes:

1. prevents retrieval from silently reconstructing a huge context dump;
2. makes resource comparisons reproducible;
3. forces later retrieval policies to choose what information is worth spending context on.

The budget is part of the query identity.

## 7. Immutable observation

A result binds:

```text
query SHA-256
exact budget
result-content SHA-256
result byte count
returned item count
truncation flag
resource usage
```

The result payload itself remains in the content-addressed store.

This permits an exact cognitive lineage such as:

```text
working state
   ↓
ContextQuery Q1
   ↓
ContextObservation O1
   ↓
updated working state
   ↓
ContextQuery Q2
   ↓
ContextObservation O2
```

without copying every observation into one permanent prompt transcript.

## 8. Exact retrieval accounting

For the current contract:

```text
ContextObservation.resources.retrieval_bytes
== ContextObservation.result_bytes
```

This makes the external-context volume directly auditable.

Later implementations may add index-compute or storage-I/O accounting separately, but the bytes delivered into the cognitive runtime must not be estimated loosely.

## 9. Truncation is explicit

When the backend has more matching material than the budget permits, the observation must set:

```text
truncated = true
```

The model/runtime can then decide whether to refine the query, request another bounded observation, or proceed.

A backend must not silently discard information while presenting the observation as complete.

## 10. Relation to active context

The context backend does not decide what belongs in a model prompt.

It only produces immutable bounded observations.

A later context policy may choose to:

```text
inject the observation directly
summarize it
extract a structured fact
store it in working memory
create an experiment hypothesis
request a narrower follow-up query
```

Those transformations remain separately attributable.

## 11. Relation to RLM-style computation

The interface supports the core architectural idea behind external-context reasoning:

```text
large state remains outside model
model receives handles + bounded operations
model decides what to inspect
observations return incrementally
```

It does not assume that recursion itself is always useful.

Recursive/subagent calls, if later added, must consume the same explicit resource and context budgets rather than gaining unlimited access by virtue of being recursive.

## 12. Protected evaluator separation

Context queries and observations are solver/runtime state.

They must not expose:

```text
protected expectations
hidden-test source
privileged evaluator configuration
promotion threshold
promotion decision
```

Protected runtime inputs may still be supplied through the already-defined sandbox boundary when required for execution. Expected outputs remain in the privileged grader domain.

## 13. Backend abstraction

`ContextBackend` is a minimal protocol:

```text
ContextQuery
    ↓
ContextBackend.query(...)
    ↓
ContextObservation
```

A later backend may operate on:

```text
repository snapshots
symbol indexes
experiment history
memory stores
skills
other immutable artifacts
```

without changing the minds or plural-synthesis layer.

## 14. No concrete retrieval engine yet

This slice deliberately does not choose:

```text
ripgrep
GitHub code search
language server
vector database
embedding model
SQLite
graph database
RAG framework
agent framework
```

Those are implementation candidates, not scientific contracts.

The first concrete backend should be chosen by the needs of Repository Surgery calibration and measured for retrieval quality, latency, context volume, and reproducibility.

## 15. Current implementation

```text
src/plural_cognition/collective/context_access.py
tests/test_collective_context_access.py
```

It provides:

```text
ContextOperation
ContextBudget
ContextQuery
ContextObservation
ContextBackend
```

No external read/search is executed by these contracts.

## 16. Next step

Once protected execution is available, the first concrete context backend should be intentionally small:

```text
content-addressed RepositorySnapshot
        ↓
TREE / SEARCH / READ
        ↓
strict byte + item ceilings
        ↓
immutable ContextObservation
```

Symbol/reference/dependency operations can then be added only if the bakeoff or calibration trajectories show that simpler repository access is a real bottleneck.

This keeps the harness useful without turning the initial benchmark into an uncontrolled agent framework comparison.
