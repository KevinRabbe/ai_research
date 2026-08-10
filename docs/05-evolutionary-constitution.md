# Evolutionary Constitution

## 1. Purpose

The project should not prescribe the final organism. It should define the conditions under which alternative cognitive systems can be created, tested, preserved, and promoted without trusting their own claims.

The governing principle is:

> **Be architecture-agnostic and process-strict.**

A future system may decide that the original design is wrong. It may replace identical models with heterogeneous architectures, symbolic mechanisms, simulators, causal world models, new communication systems, or structures not anticipated here. That freedom is desirable only when the improvement process remains auditable and reversible.

## 2. Rule 1 — qualified parents are immutable

A qualified system must not overwrite itself in place.

Every change creates a descendant:

```text
qualified parent G
├── candidate G-A
├── candidate G-B
└── candidate G-C
```

The parent remains available for:

- baseline comparison;
- rollback;
- regression diagnosis;
- component recovery;
- future recombination.

## 3. Rule 2 — candidate privileges are bounded

Each candidate receives explicit limits on:

- compute;
- memory;
- storage;
- runtime;
- external tools;
- network access;
- code execution;
- hardware access;
- descendant count;
- modification scope.

Open-ended search does not mean unbounded execution.

## 4. Rule 3 — claimed improvements require external evidence

A candidate cannot promote itself through self-description or internal confidence.

Promotion evidence may include:

- deterministic tests;
- hidden evaluation tasks;
- held-out prediction;
- reproducible simulations;
- independent evaluators;
- resource accounting;
- adversarial tests;
- regression suites;
- cross-domain transfer;
- long-horizon descendant performance.

## 5. Rule 4 — evaluation uses multiple horizons

Candidates must not be judged only by immediate post-mutation performance.

Evaluation should record:

- initial regression;
- adaptation curve;
- time to regain baseline;
- mature performance;
- learning slope at evaluation end;
- robustness after distribution shift;
- quality of descendants;
- reuse value of individual components.

A radical architecture receives a longer protected maturation budget than a shallow parameter adjustment.

## 6. Rule 5 — preserve a quality-diverse archive

The archive must not collapse into one current winner.

Preservation criteria include:

- performance;
- novelty;
- specialization;
- efficiency;
- robustness;
- calibration;
- minority rescue;
- adaptability;
- descendant quality;
- component value;
- behavioural diversity.

A lower-scoring branch may remain because it occupies a unique region of the cognitive design space.

## 7. Rule 6 — preserve functional plurality

No specific implementation of plurality is permanent. The system should nonetheless measure whether its population continues to generate meaningfully different:

- hypotheses;
- predictions;
- methods;
- representations;
- errors;
- counterexamples;
- experimental proposals.

If every member becomes behaviourally equivalent, the system has effectively returned to one cognitive perspective even if its weights differ.

This rule protects the research property, not the original architecture.

## 8. Rule 7 — evidence can overturn the majority

Promotion, synthesis, and conclusion policies must not use popularity as the default truth criterion.

A minority branch or claim remains eligible when it has:

- stronger evidence;
- better calibration;
- successful held-out predictions;
- a decisive counterexample;
- independently reproduced results;
- unique explanatory coverage.

## 9. Rule 8 — evaluation systems are independently challenged

The system may propose better benchmarks, verifiers, or evaluation policies. It must not silently replace the standards by which it is judged.

Evaluator changes require:

- independent comparison against the prior evaluator;
- hidden adversarial checks;
- consistency with externally grounded objectives;
- tests for reward hacking;
- retention of old evaluation results;
- explicit migration rationale.

## 10. Rule 9 — all resources are accounted for

A candidate's evaluation record should include:

- training FLOPs;
- inference FLOPs;
- accelerator time;
- memory and storage;
- external model calls;
- data volume;
- human interventions;
- tool calls;
- maturation time.

A system that gains accuracy only by consuming more resources may still be useful, but it is not evidence of a better cognitive mechanism under matched resources.

## 11. Rule 10 — negative and null results remain first-class

Record:

- failed mutations;
- rejected branches;
- regressions;
- misleading metrics;
- verifier failures;
- repeated dead ends;
- hypotheses unsupported by evidence;
- experiments that could not distinguish systems.

The archive should make it possible to avoid rediscovering the same failures.

## 12. Rule 11 — promotion is reversible

Every promoted system must retain:

- exact parent identity;
- exact candidate identity;
- immutable evaluation evidence;
- migration procedure;
- rollback procedure;
- known regressions;
- compatibility boundaries.

No promotion deletes the prior qualified system.

## 13. Rule 12 — scope expands only after qualification

Early self-improvement should modify only narrow external components. Broader permissions are earned through evidence.

Suggested sequence:

```text
workspace and orchestration
→ allocation and synthesis
→ improvement-policy search
→ bounded weight adaptation
→ population topology
→ model architecture
→ learning algorithm
→ hardware strategy
```

## 14. Rule 13 — product snapshots cannot govern the main lineage

A useful research snapshot may be frozen and used separately.

```text
main evolutionary lineage
→ continues research

qualified snapshot
→ copied, frozen, independently validated
→ optional human use
```

User demand, market pressure, interface requirements, and short-term latency objectives must not become selection criteria for the main lineage unless they are independently justified research variables.

## 15. Rule 14 — stop conditions are legitimate outcomes

A candidate experiment should stop when:

- resource limits are reached;
- safety or containment assumptions fail;
- evaluation becomes invalid;
- the candidate manipulates its test environment;
- no meaningful learning signal remains;
- continued adaptation cannot distinguish the hypothesis;
- the expected information gain is lower than the experiment cost.

Stopping a failed branch is not failure of the research program. It is evidence.

## 16. What remains mutable

Subject to the rules above, the system may eventually alter:

- member architecture;
- member count;
- model scale;
- population hierarchy;
- training data;
- curricula;
- learning rules;
- communication language;
- internal representation;
- memory structure;
- world-model design;
- synthesis mechanism;
- verifier suite;
- allocation strategy;
- evolutionary operators;
- hardware implementation.

## 17. Constitutional test

A proposed change is admissible when:

1. it creates an isolated descendant;
2. it has bounded resources and permissions;
3. its effects can be measured;
4. the parent remains recoverable;
5. the evaluation cannot be unilaterally redefined by the candidate;
6. negative outcomes remain recorded;
7. promotion requires reproducible evidence;
8. alternative lineages are not automatically destroyed.

These conditions do not guarantee beneficial evolution. They make claims of improvement testable.
