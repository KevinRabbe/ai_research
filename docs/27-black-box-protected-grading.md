# Black-Box Protected Grading

## Status

This document defines the first protected grading mechanism for Repository Surgery v0.

The grading mechanism is intentionally narrower than a general software judge. It establishes a hard separation between candidate execution and protected expectations before any capable model is evaluated.

## 1. Invariant

The mutable cognitive system may produce:

```text
patches
programs
observed outputs
execution traces
```

It may not receive:

```text
protected expected outputs
protected labels
protected reference answers
promotion decisions
```

The privileged grader alone maps observations to protected scores.

## 2. Protected case

One protected case contains:

```text
case_id
runtime_input_sha256
expected_output_sha256
```

The two artifacts have different roles.

`runtime_input_sha256` may enter a candidate-execution request.

`expected_output_sha256` remains in the privileged evaluation plan.

## 3. Set identities

The protected evaluator commits separately to:

```text
protected_inputs_sha256
protected_expectations_sha256
```

Each is a canonical hash over the ordered `(case_id, artifact_sha256)` bindings for the full case set.

Therefore changing one input or one expectation changes the evaluator identity even when the human-readable task ID remains unchanged.

## 4. Observation

Candidate execution emits an observation containing:

```text
case_id
runtime_input_sha256
sandbox_result_sha256
observed_output_sha256
execution_valid
```

No expectation hash appears in the observation.

The observation is therefore safe to preserve as part of the candidate-execution lineage without exposing the protected label.

## 5. Initial comparison mode

Repository Surgery v0 begins with:

```text
exact-bytes-v1
```

This does not mean arbitrary program stdout must naturally have byte-perfect formatting.

A separately frozen output adapter may canonicalize a candidate's observed semantic result before storing `observed_output_sha256`.

The protected grader then performs exact equality between:

```text
canonical observed bytes
and
canonical expected bytes
```

The output adapter itself is part of evaluator configuration and must be frozen before selection evaluation.

## 6. Invalid execution

A timeout, memory failure, abnormal sandbox termination, or otherwise invalid execution is a failed protected case.

It remains in the denominator.

The grader must never silently delete failed executions and report accuracy only over successful runs.

For `N` protected cases:

```text
exact_accuracy = correct_cases / N
valid_rate     = valid_executions / N
```

Both metrics are retained.

## 7. Protected evaluation record

The grader emits an immutable `EvaluationRecord` bound to:

```text
already-frozen stage artifact
exact TaskIdentity
evaluator ID
evaluator configuration SHA-256
evaluator software Git revision
protected visibility
metrics
qualification result
grader resource use
```

The exact evaluator software revision is mandatory.

There is no default or implicit "current code" identity.

## 8. Candidate cannot qualify itself

The candidate may emit a statement such as:

```text
all tests passed
```

That statement has no qualification authority.

Qualification is derived only from the privileged grader's comparison against protected expectations.

This same rule later applies to harness and architectural self-improvement:

```text
candidate proposes improvement
        ↓
protected evaluator measures improvement
        ↓
external promotion rule decides
```

## 9. Relation to reward hacking

The architecture does not assume a capable system will respect evaluator boundaries merely because instructions tell it to do so.

Instead, information required to directly recover protected labels is structurally withheld from candidate execution.

The objective is not to make exploitation theoretically impossible. The objective is to prevent the simplest evaluator-inspection path and make any claimed improvement depend on behavior that generalizes to protected input/output relations rather than reading the answer key.

## 10. Current implementation

```text
src/plural_cognition/collective/grading.py
tests/test_collective_grading.py
```

The implementation provides:

```text
ProtectedCase
BlackBoxEvaluationPlan
CaseObservation
ComparisonMode.EXACT_BYTES
protected_input_set_sha256
protected_expectation_set_sha256
observation_from_sandbox_result
grade_black_box
```

The grader itself performs no candidate execution.

## 11. Next step

After the grading and sandbox contracts qualify together, the next target-machine step is a **runner preflight**, not immediate untrusted-code execution.

The preflight should determine which isolated runtime can satisfy the frozen sandbox contract on the actual machine and record its exact capabilities before a concrete runner is accepted.
