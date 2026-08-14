# Plural Cognition and Open-Ended Intelligence Research

This repository investigates whether several genuinely different artificial cognitive paths can contribute complementary knowledge, synthesize new hypotheses, and converge on a verified solution stronger than any one constituent path.

The project now has two explicit research tracks:

```text
TRACK A — MECHANISM SCIENCE
small controlled models
exact synthetic worlds
causal isolation
formal synthesis mechanisms

TRACK B — CAPABLE COLLECTIVE
existing capable pretrained minds
real coding/reasoning tasks
plural synthesis
agentic harness
verified architectural self-improvement
```

Track A contains the existing Boolean Mechanism Worlds program and remains part of the permanent scientific record. Track B is now the primary development path. Small custom-model qualification is no longer a prerequisite for building the capable collective.

This is a research program, not a product roadmap.

## Core hypothesis

> Functionally different capable minds can contain complementary claims, methods, counterexamples, tests, and partial solutions. A structured collective process may combine those contributions into a verified result that exceeds every constituent mind and simpler matched-resource controls.

The intended process is:

```text
independent cognition
→ immutable raw outputs
→ structured evidence and provenance
→ contradiction and complementarity analysis
→ constructive synthesis
→ harness-assisted execution
→ adversarial verification
→ one final result
```

The long-term research direction asks whether the collective can then improve the machinery through which it thinks, communicates, remembers, synthesizes, verifies, allocates resources, and generates descendants while promotion remains externally evaluated and reversible.

## What counts as a mind

A mind is a functionally independent reasoning process, not a commitment to one neural architecture.

A mind may use:

- a dense language model;
- a Mixture-of-Experts model;
- a different pretrained model family;
- a specialized coding or reasoning model;
- a differentiated adapter or descendant;
- a hybrid neural/symbolic system;
- a future architecture not anticipated here.

The important quantity is **functional diversity**, not numerical weight difference.

The logical population is also independent of hardware topology. Four minds may execute sequentially on one accelerator or concurrently on several accelerators without changing the scientific definition of the collective.

## Preserve diversity before synthesis

Every primary mind first works independently:

```text
                         TASK
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
      Mind A             Mind B             Mind C             Mind D
        │                  │                  │                  │
        ▼                  ▼                  ▼                  ▼
       A0                 B0                 C0                 D0
```

`A0/B0/C0/D0` are frozen before cross-mind communication. This prevents early anchoring and lets the project measure real complementarity rather than four correlated restatements of the same hypothesis.

## Immutable stage attribution

No capability-producing transformation overwrites its input.

```text
A0 B0 C0 D0
      ↓
E0 — integrated evidence
      ↓
S0 — synthesized solution
      ↓
H0 — harness-assisted solution
      ↓
V0 — verified/repaired solution
      ↓
F0 — final output
```

Every stage remains independently scoreable.

This allows the project to distinguish:

```text
base-mind capability
plural uplift
harness uplift
verification uplift
total system uplift
```

rather than reporting one opaque final benchmark number.

## Primary capability metrics

Let `B` be the strongest individual constituent and `C` the collective synthesis score.

Primary plural uplift is:

\[
U_{plural}=C-B.
\]

The project also tracks:

- best-individual capability;
- oracle-union capability;
- complementarity headroom;
- pairwise error correlation;
- unique solved tasks;
- Novel Collective Solves, where all complete individual answers fail but the collective succeeds;
- rescue and damage rates at every transformation;
- exact four-mind coalition contribution and Shapley value;
- uplift per token, inference call, accelerator-time, and other controlled resources;
- harness uplift and verification uplift separately from plural synthesis.

With four primary minds there are only `2^4 = 16` coalitions, making exact coalition analysis practical.

## Required controls

The capable collective must be compared against simpler alternatives under controlled resources, including:

```text
strongest single mind
strongest single mind with matched extra inference
same model ×4 isolated contexts
four heterogeneous minds without synthesis
heterogeneous minds + selection
heterogeneous minds + constructive synthesis
```

Later comparisons add the harness, adversarial verification, and continual harness refinement as independently measured stages.

The project must distinguish genuine collective gain from merely buying additional independent attempts.

## Harness and external cognition

The harness now enters earlier in the primary roadmap because its contribution can be measured without contaminating earlier stages.

Candidate harness capabilities include:

- persistent external state;
- repository access;
- terminal and code execution;
- testing and Git;
- retrieval and structured memory;
- reusable skills;
- planning and long-horizon task state;
- programmatic context management;
- subagents;
- structured tool interfaces.

Primary minds and their subagents are different levels of plurality. A mind may use internal workers without those workers automatically becoming independent primary minds.

## Evaluator boundary

The solver must not control its own definition of success.

Mutable components may eventually include:

```text
minds
prompts
memory
skills
routing
representations
communication
synthesis
subagent topology
tool strategy
harness code
candidate architecture
```

The privileged evaluation domain remains separate:

```text
hidden tasks
ground truth
scoring rules
promotion thresholds
resource accounting
artifact integrity
rollback authority
security boundaries
```

The collective may propose that a candidate is better. Only the protected evaluator may promote it.

## Continual and architectural self-improvement

A qualified parent is never overwritten directly.

```text
qualified parent
      │
      ├──────────── preserved
      │
      ▼
candidate descendant
      │
development evaluation
      │
protected confirmation
      │
   ┌──┴───┐
 reject  promote
```

The early self-improvement target is external cognitive machinery: prompts, memory, skills, routing, context policy, representations, communication, synthesis, tool use, verification strategy, and harness architecture.

Weight adaptation is deliberately later. Existing capable pretrained models are used first so research compute can focus on collective cognition and system improvement rather than recreating base intelligence from scratch.

## Existing mechanism-science foundation

The repository already contains a controlled Boolean Mechanism Worlds program with:

- immutable Boolean AST and exact semantics;
- deterministic public evidence and hidden targets;
- symbolic model training and CUDA measurement;
- strict run/checkpoint/dataset manifests;
- proof-carrying member packets;
- semantic diversity and error-correlation metrics;
- provenance graphs and derivation hyperedges;
- bounded visible-only synthesis;
- exact hidden scoring after outputs are fixed;
- all sixteen four-member coalitions;
- leave-one-out necessity and exact Shapley attribution;
- same-weight and different-weight controls;
- frozen-weight architectural self-improvement machinery on a separate stacked branch.

Those experiments remain valuable mechanism science. Their negative results and recovery protocols remain preserved. They no longer gate the capable-system branch.

The proposed V1.2-t40m extension and execution of the original small-model frozen-weight SI experiment are **parked, not discarded**.

## Current primary implementation sequence

The governing roadmap is [`docs/22-capable-heterogeneous-collective-roadmap.md`](docs/22-capable-heterogeneous-collective-roadmap.md).

Its immediate sequence is:

```text
1. preserve the legacy experiment state
2. build the evaluation spine
3. define architecture-independent MindBackend interfaces
4. define immutable raw-mind artifacts
5. implement resource accounting
6. run a capable-model bakeoff
7. establish one-mind and four-isolated-mind baselines
8. measure complementarity and oracle union
9. select the first four-mind population
10. implement structured cross-mind evidence
11. implement minimal constructive synthesis
12. run matched-resource plural controls
13. add exact coalition attribution
14. introduce the agentic/RLM harness
15. measure harness uplift independently
16. add adversarial and protected verification
17. enable continual candidate harness modification
18. broaden to verified architectural self-improvement
```

No additional custom transformer training is required to begin this sequence.

## Repository map

### Primary direction

- [`docs/00-research-charter.md`](docs/00-research-charter.md) — mission, non-goals, claims, and invariants
- [`docs/01-theory-of-plural-cognition.md`](docs/01-theory-of-plural-cognition.md) — different internal worlds and shared external structure
- [`docs/04-open-ended-self-improvement.md`](docs/04-open-ended-self-improvement.md) — recursive collective improvement
- [`docs/05-evolutionary-constitution.md`](docs/05-evolutionary-constitution.md) — reversible architectural evolution rules
- [`docs/22-capable-heterogeneous-collective-roadmap.md`](docs/22-capable-heterogeneous-collective-roadmap.md) — current primary roadmap
- [`docs/11-reasoning-mathematics-and-search-design.md`](docs/11-reasoning-mathematics-and-search-design.md) — structured synthesis, search, and attribution foundations

### Historical mechanism-science roadmap and experiments

- [`docs/06-roadmap.md`](docs/06-roadmap.md) — historical gated roadmap, now superseded as the primary execution order
- [`docs/03-version-0-experiment.md`](docs/03-version-0-experiment.md) — original falsification protocol
- [`docs/07-version-1-build-plan.md`](docs/07-version-1-build-plan.md) — Version 1 questions, controls, and build order
- [`docs/08-v1.1-model-scale-selection.md`](docs/08-v1.1-model-scale-selection.md) — original hardware-aware model brackets and selection rule
- [`docs/09-v1.1-symbolic-codec.md`](docs/09-v1.1-symbolic-codec.md) — symbolic representation and decoder contract
- [`docs/10-v1.1-cuda-preflight.md`](docs/10-v1.1-cuda-preflight.md) — target-machine GPU measurement
- [`docs/12-v1.2-cpu-population-foundation.md`](docs/12-v1.2-cpu-population-foundation.md) — population infrastructure
- [`docs/13-v1-execution-and-analysis-procedure.md`](docs/13-v1-execution-and-analysis-procedure.md) — original operational sequence
- [`docs/14-v1-control-matrix.md`](docs/14-v1-control-matrix.md) — frozen controls and interpretation rules
- [`docs/references.md`](docs/references.md) — adjacent research

## Research principles

- Architecture-agnostic, process-strict.
- Diverge before converging.
- Functional diversity matters more than implementation diversity.
- Evidence outranks popularity.
- Preserve useful failures and minority evidence.
- Require synthesis, not only selection.
- Every capability-producing stage preserves its input.
- Hidden truth scores fixed results but never guides the same task's synthesis.
- Negative results remain published and useful.
- Never overwrite a qualified parent or completed experiment.
- Control resources and report amplification separately from raw scale.
- The solver may improve itself; it may not control the protected evaluator that decides whether it improved.

## One-sentence description

> Build a system in which several capable, functionally different minds can become one measurably stronger verified intelligence, then test whether that intelligence can repeatedly discover better ways to organize and improve itself.
