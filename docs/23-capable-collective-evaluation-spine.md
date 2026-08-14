# Capable Collective Evaluation Spine

## Status

This document specifies the first implementation slice of the capable heterogeneous collective roadmap.

It introduces architecture-independent contracts for immutable cognitive artifacts, lineage, resource accounting, and evaluation. It deliberately does **not** select models, implement a harness, or change any legacy Boolean-world experiment.

## 1. Purpose

The capable-system branch needs to answer questions such as:

```text
What did each mind produce before seeing the others?
What changed after evidence integration?
What changed after synthesis?
What changed after the harness?
What changed after verification?
How much compute did each transformation consume?
Which exact artifact did an evaluator score?
```

Those questions must remain answerable even after later stages become self-modifying.

The first implementation therefore treats each stage output as an immutable content-addressed artifact.

## 2. Stage lineage

The initial stage vocabulary is:

```text
raw-mind-output
evidence-integration
synthesis
harness
adversarial-review
verification
final
```

The intended lineage is:

```text
A0 B0 C0 D0
      ↓
E0
      ↓
S0
      ↓
H0
      ↓
R0
      ↓
V0
      ↓
F0
```

The exact future graph may branch or contain multiple candidates. The invariant is that every non-raw artifact identifies its parent artifact hashes.

Raw mind outputs have no cognitive parent artifact because the task identity is bound separately.

## 3. Task identity

A visible task identity contains:

```text
task_id
task_family
payload_sha256
```

The payload hash binds the exact solver-visible task without exposing protected evaluator state.

Protected answers, hidden tests, and promotion policy do not belong in the solver-visible task artifact.

## 4. Artifact identity

A stage artifact binds:

```text
schema
stage
task identity
run_id
producer_id
producer_configuration_sha256
protocol_sha256
software_revision
content_sha256
parent_sha256s
resource usage
```

The artifact's SHA-256 is calculated over canonical JSON containing these fields.

The output bytes themselves may live elsewhere. `content_sha256` binds those bytes without requiring the lineage record to duplicate arbitrarily large model outputs or repository patches.

## 5. Producer configuration

`producer_id` is human-readable and not sufficient for reproducibility.

`producer_configuration_sha256` is the exact configuration identity for the component that produced the artifact.

For a raw mind this should eventually bind information such as:

```text
backend implementation
model identifier
model revision
quantization
system protocol
sampling/decoding configuration
tool permissions
context policy
adapter identity if any
```

For a synthesizer or harness it binds that component's exact configuration instead.

The detailed producer manifest belongs to the next interface layer; this phase only requires its cryptographic identity.

## 6. Resource ledger

Every stage records non-negative integer counters for:

```text
input_tokens
output_tokens
inference_calls
tool_calls
verifier_calls
wall_time_ms
accelerator_time_ms
peak_accelerator_bytes
cpu_time_ms
peak_ram_bytes
retrieval_bytes
```

These fields are intentionally implementation-neutral.

Later backends may add richer diagnostic artifacts, but the common ledger must remain available for matched-resource analysis.

The ledger distinguishes:

```text
capability gain
from
resource gain
```

## 7. Evaluation identity

Evaluation is a separate immutable record rather than a field that mutates the artifact being scored.

An evaluation record binds:

```text
artifact_sha256
task identity
evaluator_id
evaluator_configuration_sha256
evaluator_software_revision
visibility
metrics
qualification decision if applicable
evaluation resource usage
```

Visibility is one of:

```text
development
protected
diagnostic
```

The same solver artifact can therefore receive development and protected evaluations without changing its identity.

## 8. Metric contract

Metrics are represented as sorted unique `(name, finite value)` records.

The common contract does not assume that every metric lies in `[0,1]`. This is necessary because the same evaluation system may record:

```text
accuracy
number of passed tests
latency
resource cost
error count
reward
```

Metric-specific range validation belongs to the evaluator that defines that metric.

## 9. Immutability rules

The following are fail-closed invariants:

1. raw mind outputs must not name cognitive parent artifacts;
2. every later stage must name at least one parent artifact;
3. parent hashes are unique and canonically sorted;
4. task, content, configuration, and protocol hashes use exact lowercase SHA-256 identities;
5. software revisions use full lowercase Git commit identities;
6. resource counters cannot be negative or Boolean masquerading as integers;
7. evaluation metrics must be sorted, unique, and finite;
8. changing content, stage, visibility, producer configuration, resources, or lineage changes the corresponding record identity.

## 10. Why resources are part of artifact identity

Resource usage is not merely telemetry in this research program.

Two outputs that contain identical text but were produced under materially different resource conditions are different experimental events.

For example:

```text
same answer
one inference call
```

is not experimentally identical to:

```text
same answer
16 attempts
20 tool calls
large retrieval budget
```

Binding the ledger into the artifact identity prevents those events from being silently conflated.

## 11. Why evaluation remains separate

The cognitive artifact must be frozen before scoring.

Therefore:

```text
artifact
   ↓
evaluation record
```

rather than:

```text
artifact ← evaluator repeatedly mutates score fields
```

This is especially important once a protected evaluator exists. The protected score must not alter or enrich the solver artifact that produced it.

## 12. Initial implementation

The first code slice is:

```text
src/plural_cognition/collective/artifacts.py
src/plural_cognition/collective/__init__.py
tests/test_collective_artifacts.py
```

It introduces:

```text
CollectiveStage
EvaluationVisibility
TaskIdentity
ResourceUsage
StageArtifact
MetricValue
EvaluationRecord
sha256_content
```

It has no dependency on a specific model family or inference provider.

## 13. Next implementation slice

After these contracts qualify, implement the architecture-independent producer layer:

```text
MindIdentity
MindConfiguration
MindRequest
MindResult
MindBackend protocol
```

Then add concrete backends only after the interface is stable.

The first concrete backends should be chosen for experimental usefulness rather than vendor preference.

## 14. Non-goals of this phase

This phase does not yet:

- download or select any model;
- define the first coding benchmark;
- implement four-mind scheduling;
- implement synthesis;
- implement the RLM harness;
- implement protected hidden tests;
- modify neural weights;
- claim collective uplift.

Its purpose is narrower:

> make every later capability-producing transformation measurable, immutable, and attributable before the capable system begins to grow.
