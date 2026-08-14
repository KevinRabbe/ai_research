# Untouched Repository Surgery Selection Pack V1

## Status

Prepared after the final local operational configuration freeze and before any selection-model inference.

The bound operational freeze is:

```text
448f72a61f320017138b5222cfed4673d001478e17bb7bc21185e04e8874066f
```

This document does not contain candidate selection results and does not choose the final four minds.

## Purpose

The selection pack is the first material that may be used to compare the five frozen candidate minds. Its contents are constructed only after calibration and operational-resource tuning are closed.

The pack contains twelve deterministic Repository Surgery tasks: two tasks in each of the six defect classes already exercised during calibration:

```text
api-contract
boundary
error-handling
local-logic
multi-file-behavior
state-management
```

The tasks use new repositories, constants, prompts, public examples, protected cases, and mutation seeds. They do not reuse any calibration task ID.

## Frozen sequencing rule

The required order is:

1. final local operational configuration is frozen;
2. construct this selection pack without candidate outputs;
3. qualify every project-authored mutation and gold repair through the qualified Docker evaluator;
4. freeze the resulting selection-pack digest and qualification-report digest;
5. only then expose the solver-visible selection tasks to candidate models;
6. do not edit tasks, prompt semantics, output protocol, resource settings, candidate identities, or evaluator material in response to selection outcomes.

## Qualification gate

`repository_surgery_selection_pack_v1.py` evaluates only two project-authored conditions before the pack is exposed to models:

```text
buggy baseline
project-authored gold repair
```

Every buggy baseline must remain observably defective. Every gold repair must reach exact accuracy `1.0` and evaluator valid rate `1.0` through the existing qualified Docker path.

Candidate inference is absent from the qualification module.

## Content addressing

The selection-pack identity binds:

```text
final operational configuration freeze SHA-256
ordered task IDs
mutation kinds
solver-visible task SHA-256 values
generation-record SHA-256 values
protected evaluation-plan SHA-256 values
```

Each generation record additionally binds the clean and buggy repository identities, issue prompt, public examples, protected input set, protected expectation set, mutation configuration, project-authored gold patch, and generator software revision.

The qualification report separately binds the selection-pack SHA-256, qualified Docker identity, buggy-baseline evaluation identities, and gold-repair evaluation identities.

## Visibility boundary

Candidate runtime receives only the solver-visible repository, issue prompt, and public examples through the already-frozen V8 structured-edit prompt contract.

Protected case inputs and expectations remain outside model runtime state. Protected expectations are consumed only by the privileged grader.

## Scientific interpretation

Selection-pack qualification is task/evaluator verification, not candidate measurement. It must not be interpreted as plural uplift, model ranking, population selection, or confirmation evidence.

After the target qualification report is accepted, this pack becomes immutable selection material. The next empirical step is the five-candidate raw-mind bakeoff under the already-frozen operational configurations and deterministic four-mind selection rule.
