# Repository Surgery v0

## Status

This document defines the first deterministic coding-task family for the capable-model bakeoff.

It does not yet claim that the benchmark has been calibrated to the desired difficulty band. Calibration happens before the selection split is frozen.

## 1. Purpose

Public coding benchmarks are useful external references, but the first plural-cognition experiment should also have a contamination-resistant task family whose exact generation and hidden evaluation remain under repository control.

Repository Surgery v0 uses small Python repositories with deterministic seeded defects:

```text
known-correct repository
        ↓
deterministic mutation
        ↓
buggy repository + issue description
        ↓
model patch
        ↓
protected tests
```

The raw-mind bakeoff initially uses repositories small enough to expose through one frozen solver-visible package. Larger repositories, retrieval, terminal use, subagents, and long-running execution belong to the later harness condition.

## 2. Scientific role

Repository Surgery v0 should answer:

> Which currently capable model configurations solve different deterministic software-repair problems before cross-mind communication or a powerful agent harness is introduced?

The task family supports measurement of:

```text
individual accuracy
operational validity
unique solves
pairwise error correlation
oracle union
complementarity headroom
resource cost
```

Those measurements select the first four primary minds.

The same tasks can later compare:

```text
raw minds
plural selection
constructive synthesis
harness-assisted repair
adversarial review
verification
```

because each stage preserves its predecessor artifact.

## 3. Content-addressed repository snapshots

A repository is represented by a canonical sorted manifest:

```text
schema
files[]
  path
  content_sha256
  size_bytes
```

Every file is independently stored by SHA-256.

The repository manifest itself is also stored by SHA-256.

Two directory trees with identical relative paths and identical file bytes therefore receive the same repository identity regardless of their host path.

Initial snapshot rules:

- regular files only;
- symlinks rejected;
- normalized relative POSIX paths only;
- no parent traversal;
- no platform-unsafe colon components;
- materialization only into a new or empty directory;
- file bytes verified on every content-store read.

The current implementation is:

```text
src/plural_cognition/collective/content_store.py
src/plural_cognition/collective/repository.py
```

## 4. Solver-visible task

A model may receive only the visible half of a task:

```text
task identity
split
buggy_repository_sha256
issue_prompt_sha256
language
max_visible_bytes
optional public_tests_sha256
```

The task payload hash commits to exactly those visible fields.

It does not contain:

```text
clean repository
hidden tests
gold patch
mutation implementation
protected evaluator configuration
```

## 5. Protected generation record

For each task, a separate protected record binds:

```text
task_id
task_payload_sha256
split
generation_seed
mutation_kind
mutation_configuration_sha256
clean_repository_sha256
buggy_repository_sha256
issue_prompt_sha256
public_tests_sha256
hidden_tests_sha256
gold_patch_sha256
```

This allows complete reproducibility without exposing the target repair to the solver.

The generation record must bind exactly to the corresponding solver-visible task.

## 6. Initial mutation classes

Version 0 reserves these defect classes:

```text
local-logic
boundary
api-contract
multi-file-behavior
state-management
error-handling
aliasing
performance
```

These names describe benchmark-generation categories. They are not automatically shown to the model.

Each concrete mutation added later must be deterministic from:

```text
source repository identity
mutation configuration identity
generation seed
```

and must pass task-construction checks before entering calibration.

## 7. Task-construction validity

A generated task is valid only if all of the following hold:

1. the clean repository passes every public and protected test;
2. the mutated repository differs from the clean repository;
3. the mutated repository fails at least one protected target test;
4. the gold patch returns the mutated repository to the intended behavior;
5. the gold patch passes all protected regression tests;
6. protected tests do not require external network access;
7. the task does not depend on uncontrolled wall-clock time or nondeterministic external services;
8. the solver-visible prompt does not expose hidden answers or gold-patch content;
9. repository and test identities are frozen before candidate-model evaluation.

A mutation that does not produce a real observable failure is rejected rather than retained as an easy task.

## 8. Patch submission

The initial submission format is:

```text
unified-diff-v1
```

A submission binds:

```text
task identity
producer stage-artifact identity
patch SHA-256
patch size
patch format
```

Patch bytes live in the content-addressed store.

The patch is not applied in the solver process.

## 9. Protected execution boundary

Model-generated patches are untrusted code changes.

The eventual evaluator must therefore materialize and execute them inside a separate restricted execution environment rather than directly inside the orchestration process or on an unrestricted host checkout.

The evaluator sequence should be:

```text
protected evaluator
      ↓
create fresh isolated task workspace
      ↓
materialize frozen buggy snapshot
      ↓
apply submitted patch under path restrictions
      ↓
run protected deterministic tests
      ↓
collect exit status / test results / resource use
      ↓
destroy workspace
      ↓
emit immutable evaluation record
```

The mutable solver must not receive the protected test bytes, evaluator filesystem, evaluator credentials, or promotion authority.

## 10. Calibration before freezing selection tasks

Repository Surgery v0 should not use an arbitrary difficulty threshold inherited from the Boolean experiment.

Calibration tasks may be changed until they satisfy the benchmark's practical requirements:

- evaluators are deterministic;
- model output can be parsed/applied reliably;
- tasks exhibit real variation in difficulty;
- no obvious accidental leakage exists;
- resource ceilings are realistic;
- the strongest candidate is neither at floor nor ceiling.

The target region for the strongest raw constituent is approximately:

```text
40%–75% task success
```

This is a task-design target, not a post-hoc qualification gate.

Once the selection task set is frozen, it is not changed in response to candidate identities or outcomes.

## 11. Initial split discipline

### Calibration

May be inspected repeatedly while building mutations, prompts, output handling, and resource ceilings.

### Selection

Used exactly for candidate-model bakeoff and first four-mind population selection.

### Confirmation

Protected from model/population selection and synthesis tuning.

If the frozen population performs poorly on confirmation, preserve the result instead of replacing a mind after seeing confirmation outcomes.

## 12. Raw-model interface

The model backend receives a hash-only `MindRequest`.

Repository and prompt bytes are resolved through a content store bound to that backend/runtime.

This keeps the invocation identity small and immutable while allowing arbitrarily larger task material to live outside the model interface.

The content store is not memory or retrieval intelligence by itself. It is deterministic artifact transport.

Later harness retrieval policies may decide which stored material to expose, but those policies constitute a separately measured capability layer.

## 13. Next implementation steps

The next benchmark-specific code should add:

```text
deterministic seed repository templates
concrete mutation implementations
task generator validation
canonical prompt construction
patch parser / path validator
isolated evaluator interface
calibration-set builder
```

Only after those components qualify should candidate models be downloaded or evaluated on Repository Surgery selection tasks.

## 14. Non-goals

Repository Surgery v0 is not intended to be a complete software-engineering benchmark.

It initially does not test:

- repository-scale autonomous exploration;
- long-running issue resolution;
- web research;
- package installation from arbitrary sources;
- GUI interaction;
- cloud operations;
- unrestricted shell access;
- continual memory;
- self-modifying harness behavior.

Those are later harness capabilities.

The first task family exists to create a deterministic, protected, controllable substrate for measuring whether capable minds possess useful complementary software-repair knowledge before the collective architecture starts amplifying them.
