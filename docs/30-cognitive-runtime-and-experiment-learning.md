# Cognitive Runtime and Experiment-Learning Contract

## Status

This document turns the harness/context-learning direction into a narrow, testable architecture without yet implementing autonomous background work, self-play, model training, or unrestricted self-modification.

The immediate purpose is to define what the later `H0` harness stage should own and what evidence must survive every experiment.

The design follows two principles:

1. the neural mind is not the whole AI system;
2. failed and successful experiments are both useful if they preserve what was believed, predicted, changed, observed, and learned.

## 1. System boundary

The capable system is decomposed into replaceable layers:

```text
neural mind(s)
    ↓
small active working context
    ↓
external cognitive runtime
    ├─ repository state
    ├─ immutable artifacts
    ├─ working memory
    ├─ episodic / experiment memory
    ├─ skills
    ├─ retrieval
    ├─ tool observations
    ├─ task/checkpoint state
    └─ later: scheduler / subagents / refinement
    ↓
execution / experiment environment
    ↓
verification
    ↓
protected evaluator
```

The model remains responsible for learned inference, abstraction, hypothesis generation, planning, and decisions. Large durable state does not need to remain continuously inside transformer attention.

## 2. External context is addressable state

Persistent cognitive objects receive stable content-addressed references rather than being copied into every prompt.

The first reference kinds are:

```text
artifact
repository
task
experiment
memory
skill
tool-observation
```

A reference uses a SHA-256 identity and may be rendered as a URI-like handle such as:

```text
repository://sha256/<digest>
experiment://sha256/<digest>
memory://sha256/<digest>
```

These are identities, not network locations. Resolution remains under the runtime's explicit storage and visibility policy.

The current implementation does not add a retrieval engine. It only freezes the reference semantics required by one later.

## 3. State visibility

External state has one of three scopes:

```text
SYSTEM
shared task inputs and runtime-owned immutable material

PRIVATE_MIND
state visible only to one declared primary mind

SHARED_COLLECTIVE
state intentionally created after the independent phase for collective cognition
```

This is necessary because external memory must not accidentally destroy the independent-mind baseline.

## 4. Independence remains a hard boundary

During the initial `A0/B0/C0/D0` phase, a runtime checkpoint may consume:

```text
SYSTEM state
its own PRIVATE_MIND state
```

It may not consume:

```text
SHARED_COLLECTIVE state
another primary mind's PRIVATE_MIND state
```

Therefore moving memory outside the model does not silently turn four minds into four front ends over one shared cognitive state.

Only after the initial artifacts are frozen may synthesis/harness phases consume explicitly shared collective state.

## 5. Experiment-learning loop

Repository Surgery and later engineering tasks should preserve the reasoning-relevant structure of an experiment:

```text
OBSERVE
   ↓
HYPOTHESIZE
   ↓
PREDICT
   ↓
ACT / MODIFY
   ↓
MEASURE
   ↓
COMPARE prediction with reality
   ↓
EXPLAIN
   ↓
UPDATE hypothesis
```

A successful final patch alone is insufficient to describe this process.

A failed attempt can be scientifically useful when it reveals that a causal prediction was wrong and records the resulting belief update.

## 6. Immutable `ExperimentAttempt`

The first experiment record binds:

```text
TaskIdentity
attempt identity
actor identity
producer configuration
protocol identity
software revision
observation artifact
hypothesis artifact
prediction artifact
action / modification artifact
observed-result artifact
explanation artifact
optional successor hypothesis
parent attempt hashes
optional numerical prediction measurements
resource usage
```

The substantive payloads live in the content-addressed store. The record binds them by SHA-256 so large text, patches, profiler output, traces, and structured hypotheses do not have to be embedded in the manifest.

## 7. Prediction calibration

When an experiment has measurable outcomes, record predicted and actual values.

Example:

```text
metric: runtime_ms
predicted: 80
actual: 95
confidence: 0.70
absolute prediction error: 15
```

This supports a later research question distinct from task accuracy:

> Is the system becoming better at predicting the consequences of its own interventions?

Declining prediction error can indicate improved causal understanding even before headline solve rate changes.

Not every prediction is numerical, so numerical measurements remain optional. The complete prediction is still preserved as its own immutable artifact.

## 8. Protected evaluation remains separate

`ExperimentAttempt` is solver/runtime evidence, not privileged grading state.

It deliberately does not contain:

```text
protected expectations
hidden tests
promotion thresholds
privileged evaluator configuration
secret score
promotion decision
```

A protected evaluation may later score an already-frozen output or observed result, but that record remains in the evaluator domain.

This preserves the existing architecture:

```text
candidate cognition / experiment
        ↓
immutable observation
        ↓
privileged evaluator + protected expectation
        ↓
score / qualification
```

## 9. Runtime task state

The external runtime needs resumable task state independent of a live chat transcript.

The first declared task states are:

```text
QUEUED
RUNNING
WAITING_FOR_TOOL
CHECKPOINTED
PAUSED
VERIFYING
DONE
FAILED
```

This is a state contract only. No autonomous scheduler is added yet.

## 10. Cognitive phases

The runtime distinguishes:

```text
INDEPENDENT
SYNTHESIS
HARNESS
VERIFICATION
REFINEMENT
CONSOLIDATION
```

These phases are intentionally broader than execution states. `RUNNING` describes what the scheduler is doing; `INDEPENDENT` or `SYNTHESIS` describes which cognitive information-flow rules apply.

## 11. Priority model

The initial priority levels are:

```text
0  urgent user work
1  normal user work
2  system/evaluation work
3  refinement work
4  speculative work
```

Lower numeric values have higher priority.

This supports the later Active / Refine / Consolidate architecture without implementing background autonomy now.

## 12. Safe preemption

Background or long-running work must eventually be interruptible at explicit safe points.

A runtime checkpoint records whether it is safe to preempt.

Rules frozen now:

```text
PAUSED        => safe_to_preempt must be true
CHECKPOINTED  => safe_to_preempt must be true
DONE/FAILED   => safe_to_preempt must be true
RUNNING       => may temporarily be false during an atomic operation
```

Later training code may define optimizer-step/checkpoint boundaries as atomic regions without changing this generic runtime contract.

## 13. Immutable `RuntimeCheckpoint`

A checkpoint binds:

```text
TaskIdentity
runtime task id
owner id
cognitive phase
runtime state
priority
producer configuration
protocol identity
software revision
objective artifact
workspace artifact
working-state artifact
plan artifact
tool-state artifact
ordered external references
safe-preemption flag
resource ledger
```

The checkpoint stores identities rather than requiring the entire working set to remain in model context.

## 14. What is deliberately not implemented

This slice does not yet add:

```text
a background scheduler
a Dream/Refine loop
self-generated tasks
self-play
a retrieval policy
a memory ranking algorithm
automatic skill promotion
model fine-tuning
RL
candidate-model promotion
a simulator/world model
subagent orchestration
unrestricted harness self-editing
```

Those mechanisms should be introduced only when the earlier evaluation and execution layers can measure their effect.

## 15. Relation to `H0`

The harness stage can now be defined more precisely.

`H0` is not merely "the model got tools." It is the transformation produced by a declared cognitive runtime over a frozen `S0` input:

```text
S0
 ↓
content-addressed external state
+ bounded retrieval
+ repository/tool operations
+ experiment attempts
+ resumable task state
+ declared resource use
 ↓
H0
```

The original `S0` remains immutable, allowing:

```text
U_harness = score(H0) - score(S0)
```

without conflating harness capability with plural synthesis.

## 16. Relation to future continual improvement

A later refinement lifecycle may be:

```text
ACTIVE work
   ↓
immutable experiment history
   ↓
REFINEMENT candidates
   ↓
validated memories / skills / harness mutations
   ↓
CONSOLIDATION candidate
   ↓
protected evaluation
   ↓
reject or promote
```

Immediate experience should first become external memory. Repeated validated patterns may later become skills. Only sufficiently supported, regression-tested patterns should become candidates for neural weight adaptation.

This preserves the hierarchy:

```text
single experience          → memory
repeated validated pattern → skill / procedure
strong general pattern     → possible weight consolidation candidate
```

## 17. No self-approval

Neither refinement nor consolidation changes the promotion authority.

The mutable cognitive system may propose:

```text
new memory policy
new skill
new retrieval strategy
new harness code
new adapter/model descendant
```

but only the separate protected evaluator may promote a candidate into the qualified system.

## 18. Implementation

Current contracts:

```text
src/plural_cognition/collective/experiment.py
src/plural_cognition/collective/runtime.py

tests/test_collective_experiment.py
tests/test_collective_runtime.py
```

The implementation is intentionally architecture-independent and does not execute untrusted code.

## 19. Next implementation order

The protected-runner gate remains first for real Repository Surgery execution.

Work that can proceed safely in parallel is:

```text
1. qualify protected execution backend on target machine
2. construct deterministic Repository Surgery calibration tasks
3. freeze bounded repository/context access interfaces
4. use ExperimentAttempt during calibration trajectories
5. implement minimal resumable harness runtime
6. run capable-model bakeoff
7. freeze four independent mind baselines
8. add plural synthesis
9. measure H0 harness uplift
10. only then introduce autonomous refinement/consolidation experiments
```

This prevents the long-term cognitive-runtime vision from becoming an excuse to build maximum architecture before the core evaluation loop is empirical.
