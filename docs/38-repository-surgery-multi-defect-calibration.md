# Repository Surgery Multi-Defect Calibration

## Status

The single-task Repository Surgery calibration smoke has passed on the exact qualified target machine. This document defines the next calibration-only expansion before any selection task set is frozen or any capable-model-generated patch is executed.

The matrix uses deterministic project-authored repositories, mutations, prompts, protected cases, and gold repairs. It is not a model benchmark result.

## 1. Purpose

One boundary defect proves the protected execution and grading path works end to end, but it does not establish that Repository Surgery v0 can represent materially different repair modes.

The next gate therefore exercises six distinct mutation classes through the same qualified Docker and privileged black-box grader:

```text
api-contract
boundary
error-handling
local-logic
multi-file-behavior
state-management
```

Each task is in the `calibration` split. These tasks may still be inspected or changed if construction defects are found.

## 2. Frozen per-task acceptance rule

For every calibration task:

```text
buggy repository + empty patch
        ↓
qualified Docker
        ↓
protected exact-byte evaluation
        ↓
accuracy < 1.0 and qualified == false

buggy repository + project-authored gold patch
        ↓
qualified Docker
        ↓
protected exact-byte evaluation
        ↓
accuracy == 1.0
valid_rate == 1.0
qualified == true
```

A task that does not expose a real protected failure is rejected. A task whose gold patch does not fully restore protected behavior is also rejected.

## 3. Matrix tasks

### API contract

The input field `scale` is optional and defaults to one. The defect turns optional access into required indexing. Protected cases include an omitted field.

### Boundary

Premium shipping discount applies at subtotal `>= 50`. The defect changes the threshold to `> 50`.

### Error handling

A zero divisor must be converted to the documented structured invalid-input response. The defect removes the zero guard, so the buggy candidate crashes on that protected case.

### Local logic

Each item contributes three points. The defect replaces multiplication by three with addition of three.

### Multi-file behavior

`app.py` delegates delivery-fee policy to `rates.py`. The defect changes only the EU rate in the helper module, requiring repair outside the entrypoint file.

### State management

A cart object must accumulate amounts across a sequence of operations. The defect overwrites state instead of accumulating it.

## 4. Protected-evaluation boundary

The matrix preserves the same split used by the calibration smoke:

```text
candidate execution domain:
  buggy repository
  submitted patch
  one protected runtime input

privileged grading domain:
  observed candidate output
  protected expected output
```

Protected expectations, evaluator labels, grader state, qualification state, and promotion authority never enter the candidate container.

## 5. Qualification binding

The matrix executes only through the already-promoted Docker binding:

```text
qualified report:
2d2e3af2685a826b92cc03c36865cd74f1c4c954520b9448c82edbc294a70b04

stable Engine qualification:
8155c7193395faaa6096032249b179926381f069343589f5c40e2ac3f4c14000

immutable image:
sha256:b6b32c4c224d190ff281853aafe6e6d57d0361a32dc7ba11076af6e18892b139

qualified runner source:
1a361fee3ba74ba1b85d7d249ced89b624d9d58a907f95bde34d7f24730782e3
```

If the bound runner source/configuration or stable Engine fingerprint drifts, execution fails closed.

## 6. Machine-readable report

The matrix emits:

```text
plural-cognition-repository-surgery-calibration-matrix-v1
```

with one immutable record per task containing:

```text
task id
mutation kind
visible task hash
generation-record hash
evaluation-plan hash
baseline evaluation hash
gold evaluation hash
baseline exact accuracy
gold exact accuracy
baseline valid rate
gold valid rate
```

The top-level report also binds the qualified Docker identity and software revision.

## 7. What a passing matrix establishes

A passing matrix establishes that several deterministic repair modes can be generated, executed, and graded reproducibly through the protected path, including a case where the buggy process exits abnormally and a case requiring a second source file.

It does not establish model difficulty, contamination resistance by itself, plural uplift, or final benchmark quality.

## 8. Next gate after a pass

After the target machine passes this matrix:

```text
inspect per-task baseline/gold evidence
        ↓
add remaining useful calibration classes if needed
        ↓
freeze generator/task-construction protocol
        ↓
construct a larger calibration pool
        ↓
measure capable-model raw difficulty on calibration only
        ↓
tune calibration task distribution
        ↓
freeze untouched selection set
        ↓
run candidate-model bakeoff
```

Selection tasks must not be edited in response to model identities or selection outcomes once frozen.
