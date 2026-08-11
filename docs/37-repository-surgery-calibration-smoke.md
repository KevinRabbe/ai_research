# Repository Surgery Calibration Smoke

## Status

The Docker containment gate is qualified. The next empirical step is a controlled end-to-end Repository Surgery v0 calibration smoke using only deterministic **project-authored** material.

No model-generated patch is executed in this phase.

Implementation:

```text
src/plural_cognition/collective/repository_surgery_calibration.py
src/plural_cognition/collective/qualified_docker.py
tests/test_collective_repository_surgery_calibration.py
```

## Purpose

This smoke experiment tests the complete protected-evaluation spine before capable-model bakeoff:

```text
deterministic clean repository
        ↓
deterministic boundary mutation
        ↓
solver-visible task + protected generation record
        ↓
qualified Docker execution
        ↓
protected case observations
        ↓
privileged exact-byte grader
        ↓
buggy baseline must fail
project-authored gold repair must pass
```

A pass proves that the benchmark contracts, qualified sandbox, patch application, output capture, protected-input separation, protected-expectation separation, and privileged grading compose correctly on the target machine.

It does **not** establish the final task difficulty distribution and does not select any model.

## Calibration task 0001

The first task is:

```text
repository-surgery-calibration-boundary-0001
```

It contains a tiny Python JSON stdin/stdout program implementing a shipping-total policy.

Correct policy:

```text
premium customer AND subtotal >= 50
    -> 5-unit discount
```

The deterministic mutation changes the boundary operator from `>=` to `>`.

The solver-visible issue describes the intended policy but does not expose protected runtime cases, protected expected outputs, evaluator configuration, clean repository identity, or gold-patch bytes.

Two public non-boundary examples are stored as visible task material. Four protected cases include the exact threshold, below/above-threshold controls, and a non-premium threshold control.

## Gold repair

The project-authored gold repair is a strict `unified-diff-v1` patch that restores the boundary operator.

Before target execution, unit tests require that applying this patch to the content-addressed buggy snapshot reproduces the clean repository manifest exactly.

## Protected execution

The calibration smoke obtains the Docker configuration through the v10 qualified binding. It refuses to proceed if:

```text
qualification-source hash drifted
runner-configuration hash drifted
live stable Engine fingerprint drifted
```

The calibration sandbox uses:

```text
network disabled
2 s wall ceiling
1 s CPU budget
64 MiB memory
1 MiB writable workspace
8-process ceiling
4 KiB stdout
4 KiB stderr
```

Each protected case receives only its runtime input. Expected output bytes remain solely in the privileged `BlackBoxEvaluationPlan` / content store used by the host-side grader.

## Smoke acceptance rule

The smoke is successful only when both conditions hold:

```text
buggy baseline exact_accuracy < 1.0 and qualified == false
gold repair exact_accuracy     = 1.0 and qualified == true
```

Invalid executions remain failures in the denominator; no protected case is silently dropped.

## Immutable report

A successful run writes canonical JSON with:

```text
schema
current calibration software revision
qualified Docker report/source/Engine/image identities
visible task SHA-256
generation-record SHA-256
evaluation-plan SHA-256
buggy-baseline evaluation SHA-256
gold evaluation SHA-256
baseline exact accuracy
gold exact accuracy
```

The report receives its own SHA-256 identity.

## After the smoke

If the target smoke passes, expand Repository Surgery calibration from one boundary mutation into a small deterministic matrix spanning several defect classes. The calibration set may still be revised for task validity, parser reliability, resource ceilings, and difficulty spread.

Only after that calibration matrix is satisfactory should the selection set be frozen and capable models evaluated.
