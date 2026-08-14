# Capable Heterogeneous Collective Intelligence Roadmap

## Status

This document defines the revised primary research path.

The completed Boolean Mechanism Worlds work remains part of the permanent scientific record. Its positive, negative, null, and methodological results are not invalidated by this roadmap. Small custom-model qualification is no longer a prerequisite for constructing the main capable system.

The project now separates two research tracks:

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

Track A may be revisited when a narrow mechanism requires controlled study. Track B becomes the primary development path.

The proposed V1.2-t40m extension and execution of the original small-model frozen-weight self-improvement experiment are therefore **parked, not discarded**.

## 1. Revised central hypothesis

The project investigates whether several capable but functionally different artificial minds can form one collective cognitive system whose verified solutions exceed those produced by every constituent mind.

The proposed mechanism is:

```text
independent capable minds
→ preserve functional diversity
→ extract structured evidence and proposals
→ expose contradictions and complementary information
→ construct new composite solutions
→ use tools and external computation
→ verify
→ converge on one result
```

The stronger long-term hypothesis is:

> A heterogeneous collective whose reasoning, communication, memory, synthesis, verification, and execution architecture can be modified under external evaluation may repeatedly discover better ways to organize intelligence.

## 2. Definition of a mind

A **mind** is a functionally independent reasoning process within the collective. It is defined by behavior and state, not by one neural implementation.

A mind may use a dense model, Mixture-of-Experts model, different pretrained family, specialized coding or reasoning model, differentiated adapter, hybrid neural/symbolic system, or future architecture.

A mind should possess at minimum:

```text
mind identity
model/backend identity
private context
private working state
private or namespaced memory
independent initial reasoning phase
immutable initial output artifact
```

Different weights are neither necessary nor sufficient for useful plurality. The relevant quantity is **functional diversity**.

## 3. One collective intelligence, multiple minds

The unit ultimately being optimized is the entire system:

```text
                     COLLECTIVE
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
      Mind A           Mind B           Mind C           Mind D
        │                │                │                │
        └────────────────┼────────────────┼────────────────┘
                         ▼
                 collective cognition
                         ▼
                  one final action
```

The main capability target is verified collective performance relative to the strongest constituent and to matched-resource controls.

## 4. Execution topology is not cognitive topology

The logical architecture must not depend on the number of accelerators.

One accelerator may execute the minds sequentially. Multiple accelerators may execute them concurrently. These are implementations of the same cognitive graph.

Parallel execution changes latency and throughput; it does not define whether plural cognition exists.

The scheduler must separate logical mind topology from physical hardware placement.

## 5. Preserve independence before communication

Every task begins with an isolation phase:

```text
                         TASK
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
      Mind A             Mind B             Mind C             Mind D
        │                  │                  │                  │
   private work        private work       private work       private work
        │                  │                  │                  │
        ▼                  ▼                  ▼                  ▼
       A0                 B0                 C0                 D0
```

No mind sees another mind's answer during this phase. This protects against anchoring, imitation, premature consensus, shared false assumptions, majority pressure, and loss of rare hypotheses.

Only after `A0/B0/C0/D0` are frozen may cross-mind cognition begin.

## 6. Immutable cognitive lineage

No transformation may overwrite its input. Every major stage receives immutable artifacts and creates new immutable descendants.

Canonical task lineage:

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
F0 — final action/output
```

All earlier artifacts remain addressable.

Every artifact should bind task identity, parent hashes, model identities, protocol identity, context identity, tool observations, generated content, resource use, software revision, and evaluation result.

The same rule applies to self-modification: qualified parents are never overwritten by their candidates.

## 7. Core measurement model

For task set \(T\), let individual mind performance be \(P_A,P_B,P_C,P_D\).

Define the strongest constituent baseline:

\[
B=\max(P_A,P_B,P_C,P_D).
\]

Define collective synthesis score \(C=P(S_0)\).

Primary plural uplift is:

\[
U_{plural}=C-B.
\]

A move from constituent scores such as `70/72/68/71` to a verified collective score of `80` is therefore an `+8` percentage-point plural uplift, subject to matched-resource controls and replication.

## 8. Oracle union and complementarity headroom

For every task \(t\), let \(x_{i,t}=1\) when mind \(i\) solves the task and `0` otherwise.

The oracle-union score is:

\[
O=\frac{1}{|T|}\sum_t \mathbf{1}[\max_i x_{i,t}=1].
\]

The population's simple selection headroom is:

\[
H_{selection}=O-B.
\]

If `B=72%`, `O=88%`, and synthesis reaches `80%`, then synthesis captures half of the available oracle-selection headroom:

\[
\eta=\frac{C-B}{O-B}=0.5.
\]

The oracle union is not an upper bound on constructive synthesis because the collective may solve tasks that every complete individual answer failed.

## 9. Novel Collective Solves

A **Novel Collective Solve** occurs when all complete initial individual answers fail but the combined system succeeds through permitted synthesis, tools, evidence, or verification.

Define:

\[
NCS=P(\text{all individuals fail} \land \text{collective succeeds}).
\]

This is one of the strongest indicators of constructive collective cognition rather than simple answer selection.

## 10. Rescue and damage accounting

Every transformation stage is evaluated independently.

For transformation \(X\rightarrow Y\):

\[
R=P(X=fail,Y=pass)
\]

and

\[
D=P(X=pass,Y=fail).
\]

Net effect is:

\[
\Delta=R-D.
\]

A stage cannot hide regressions behind aggregate score. Rescue and damage counts are retained alongside final accuracy.

## 11. Stage-specific uplift

Let:

```text
B = strongest raw constituent
C = collective synthesis
H = harness-assisted result
V = verifier/repair result
F = final system result
```

Then report separately:

\[
U_{plural}=C-B
\]

\[
U_{harness}=H-C
\]

\[
U_{verification}=V-H
\]

\[
U_{total}=F-B.
\]

No later stage may overwrite the earlier score or artifact.

## 12. Resource accounting

More inference is itself a resource. Every comparison must report, where applicable:

```text
input tokens
output tokens
number of inference calls
number of independent attempts
tool calls
wall-clock time
accelerator time
peak accelerator memory
CPU time
RAM use
retrieval volume
verification cost
```

Results must distinguish capability from efficiency. A four-mind system beating one mind with more total inference is useful engineering evidence, but not by itself evidence that heterogeneity caused the gain.

## 13. Exact four-mind coalition attribution

With four minds there are only \(2^4=16\) coalitions. Preserve exact coalition evaluation whenever practical.

This permits exact Shapley contribution:

\[
\phi_i=\sum_{S\subseteq N\setminus\{i\}}
\frac{|S|!(|N|-|S|-1)!}{|N|!}
[v(S\cup\{i\})-v(S)].
\]

This distinguishes a strong individual from a valuable collective contributor. A weaker individual model may have high collective value if it supplies rare correct information, counterexamples, or useful criticism.

## 14. Selecting the four minds

Do not automatically choose the four highest-scoring individual models.

Candidate evaluation should consider:

```text
individual capability
unique solved tasks
pairwise error correlation
proposal and method diversity
counterexample contribution
oracle-union increase
marginal coalition value
inference cost
memory requirements
coding/tool competence
stability
```

The desired population is strong enough individually but sufficiently complementary that combining it exposes useful information unavailable to one constituent alone.

## 15. Required baseline conditions

Before claiming plural uplift, compare at minimum:

```text
A. strongest single mind, one attempt
B. strongest single mind with matched extra inference budget
C. same model ×4 isolated contexts
D. four heterogeneous minds without synthesis
E. four heterogeneous minds + selection
F. four heterogeneous minds + plural synthesis
```

Later conditions add:

```text
G. plural synthesis + harness
H. plural synthesis + harness + verification
I. continually refined harness
```

This separates extra attempts from functional diversity, selection, constructive synthesis, harness amplification, and verification.

## 16. Structured cross-mind representation

The system should not depend exclusively on free-form conversations.

A domain-appropriate proposal packet may contain:

```text
task_id
mind_id
complete_candidate
hypotheses[]
claims[]
evidence[]
counterexamples[]
uncertainties[]
assumptions[]
risks[]
code_changes[]
tests[]
tool_results[]
provenance[]
confidence/calibration fields
```

Natural-language reasoning may generate proposals. Verification determines what becomes trusted collective state.

## 17. Evidence graph

Cross-mind information enters a shared typed graph or equivalent structured workspace.

Possible node types include claim, observation, code fragment, test, hypothesis, counterexample, assumption, risk, candidate solution, and uncertainty.

Possible relations include supports, contradicts, depends-on, derived-from, repairs, generalizes, specializes, tests, invalidates, and equivalent-to.

Support count alone must never determine truth. Minority evidence must survive when it is more diagnostic than consensus.

## 18. Collective synthesis

Synthesis is a first-class cognitive subsystem, not majority voting or best-of-N selection.

It should be capable of extracting useful components, reconciling compatible claims, retaining unresolved alternatives, using one mind's counterexample against another, combining partial implementations, generating new candidate solutions, requesting additional evidence, constructing tests, and repairing contradictions.

The desired result may be a new solution assembled from contributions that no complete initial answer contained.

## 19. Harness moves earlier

A powerful agentic harness is no longer postponed until all plural-cognition questions are complete.

It may provide persistent external state, repository access, terminal execution, testing, Git, retrieval, memory, skills, planning, subagents, programmatic context management, long-running task state, and structured tool APIs.

However, `S0` must be frozen before the harness transforms it:

```text
S0 → harness → H0
```

This makes harness uplift independently measurable.

## 20. Context and memory architecture

Large persistent state should live primarily outside model context.

Separate:

```text
RAW STATE       immutable observations and artifacts
QUALIFIED STATE currently trusted structured knowledge
WORKING STATE   temporary active reasoning context
CANDIDATE STATE experimental representation or memory system
```

Models retrieve only the subset needed for the current operation.

## 21. Subagents are below the mind layer

Distinguish:

```text
MACRO PLURALITY
independent primary minds

MICRO PLURALITY
subagents used internally by one mind
```

Subagents do not automatically count as independent primary minds. Their contribution is attributed to their parent unless an experiment explicitly defines otherwise.

## 22. Verification architecture

The solver must not control its final definition of success.

Separate the mutable cognitive domain — minds, prompts, memory, skills, routing, representation, synthesis, harness, subagents, tool strategy, and candidate architecture — from the privileged evaluation domain containing hidden tasks, ground truth, scoring rules, promotion thresholds, resource accounting, artifact integrity, rollback authority, and security boundaries.

A system may propose that a candidate is better. Only the external evaluator may promote it.

## 23. Adversarial verification

Later stages should include a dedicated adversarial process:

```text
collective solver
      ↓
candidate solution
      ↓
red / critic process
      ↓
counterexamples / attacks
      ↓
repair candidate
      ↓
external verifier
```

The adversarial system should be rewarded for discovering genuine failures, not for agreeing with the solver.

## 24. Continual harness improvement

Once a stable capable baseline exists, permit the collective to propose changes to prompts, memory organization, skills, context policy, mind roles, routing, communication, evidence schema, synthesis, subagent topology, planning, and tool use.

Every modification creates a candidate descendant:

```text
qualified H_n
      │
      ├──────────── remains immutable
      │
      ▼
candidate H_n+1
      │
development evaluation
      │
hidden evaluation
      │
   ┌──┴───┐
 reject  promote
```

Every candidate records parent hash, candidate hash, trajectory evidence, failure hypothesis, mutation description, resource delta, before/after scores, rescues, regressions, and promotion decision.

## 25. Representation evolution

The system may eventually improve not only behavior but also how information is represented.

Keep harness/behavior architecture `H` and representation architecture `R` independently testable:

```text
H_ref       + R_ref
H_candidate + R_ref
H_ref       + R_candidate
H_candidate + R_candidate
```

This separates behavior improvement, representation improvement, and interaction effects.

## 26. Verified architectural self-improvement

After continual harness refinement demonstrates reliable gains, broaden mutation to system architecture.

The collective may inspect its repository, analyze failure trajectories, identify bottlenecks, write candidate code, modify communication, routing, synthesis, memory, representation, scheduling, and tool procedures, and run public tests.

It may not read hidden answers, alter hidden tests, change promotion thresholds or resource accounting, rewrite historical artifacts, or approve its own promotion.

## 27. Weight adaptation comes later

Do not begin by training the capable minds ourselves.

First determine how far external collective architecture can go. Only after justified by evidence test:

```text
prompt/role differentiation
↓
memory differentiation
↓
different adapters
↓
bounded fine-tuning
↓
continued-training descendants
↓
model/harness co-learning
↓
broader neural self-modification
```

Every additional learning mechanism must demonstrate value beyond the mature external architecture.

## 28. Revised research phases

### Phase 0 — Archive existing mechanism science

Freeze and document the current Boolean-world results. No result is deleted or retrospectively reinterpreted. `t40m` and the original small-model Experiment 2 are parked.

### Phase 1 — Evaluation spine

Build task, runtime, artifact, resource-accounting, public-development, protected-confirmation, provenance, and replay interfaces.

**Gate:** the same frozen output reproduces the same score, lineage, and resource interpretation.

### Phase 2 — Mind backend abstraction

Create an architecture-independent interface for local and remote capable models.

**Gate:** materially different model implementations execute the same task protocol without plural-layer changes.

### Phase 3 — Model bakeoff

Evaluate candidate models independently for capability plus complementarity.

**Gate:** select a population with sufficient competence and measurable non-redundant task coverage.

### Phase 4 — Independent four-mind baseline

Run four frozen minds without communication. Establish individual scores, best-individual baseline, oracle union, pairwise error correlation, unique solves, and resource use.

**Gate:** meaningful complementarity must exist before expensive synthesis research is justified.

### Phase 5 — Plural synthesis

Add structured evidence exchange and constructive synthesis. Compare the required controls.

**Gate:** reproducible positive plural uplift over the strongest constituent and relevant matched-resource controls, with auditable provenance and nontrivial rescue events.

### Phase 6 — Harness amplification

Introduce persistent memory, tools, repository access, programmatic context, subagents, planning, and long-horizon execution.

**Gate:** positive harness uplift without hiding plural regressions.

### Phase 7 — Adversarial verification

Add independent attack, counterexample generation, testing, and repair.

**Gate:** verification improves reliability or capability without excessive damage to correct solutions.

### Phase 8 — Continual harness self-improvement

Allow evidence-driven candidate changes to external cognitive machinery.

**Gate:** multiple independently evaluated descendant cycles produce generalizing improvement over immutable parents.

### Phase 9 — Architectural self-improvement

Allow modifications to broader system code and cognitive organization.

**Gate:** descendants improve held-out capability under controlled resources and remain reproducibly promotable and rollbackable.

### Phase 10 — Quality-diverse architecture evolution

Maintain multiple qualified lineages rather than only one current winner.

**Gate:** archive-based search outperforms a matched single-lineage strategy over longer horizons.

### Phase 11 — Meta-improvement

Permit the system to improve mutation proposal, failure analysis, experiment generation, candidate scheduling, resource allocation, archive policy, and improvement strategy. The evaluator remains protected.

**Gate:** the improvement process itself improves on held-out architectural problems rather than merely consuming more resources.

### Phase 12 — Model/harness co-learning

Only now investigate controlled neural adaptation.

**Gate:** weight-level change adds capability or developmental potential beyond the mature frozen-weight architecture.

## 29. Primary metric family

Maintain at least:

```text
best-individual capability
oracle-union capability
complementarity headroom
pairwise error correlation
unique solve rate
collective synthesis capability
plural uplift
Novel Collective Solve rate
rescue rate
damage/regression rate
harness uplift
verification uplift
total system uplift
uplift per token
uplift per inference call
uplift per accelerator-time
exact coalition contribution
exact Shapley contribution
resource-normalized descendant improvement
```

No single number is sufficient.

## 30. Central falsification conditions

Reconsider the route if repeated controlled experiments show that heterogeneous minds provide no useful complementarity; collective synthesis cannot beat matched-compute repeated sampling; gains disappear on held-out tasks; additional minds consistently damage the strongest constituent; harness gains reduce to uncontrolled resource scaling; self-improvement overfits development evaluation; candidates exploit evaluators instead of improving competence; diversity collapses before synthesis; or descendant improvements cannot survive immutable-parent comparison.

Negative outcomes remain scientific results.

## 31. What is no longer assumed

The project no longer assumes that all minds must use the same architecture, live inside one neural network, be trained by this project, fit in VRAM simultaneously, or execute in parallel. It no longer assumes that different weights alone imply useful plurality, that the harness must wait until every mechanism experiment is complete, that small Boolean-model qualification is required before capable-system work, or that weight modification is necessary for early self-improvement.

## 32. What remains invariant

The following principles survive the pivot:

```text
diverge before converging
functional diversity matters
evidence outranks popularity
preserve minority information
preserve failed but useful paths
require constructive synthesis rather than only selection
freeze results before hidden evaluation
preserve provenance
never overwrite qualified parents
report negative results
control resources
separate solver from evaluator
promote descendants only through evidence
remain architecture-agnostic
```

## 33. Immediate implementation order

```text
1. Freeze the legacy experiment state and document this roadmap pivot.
2. Define new task/evaluator/runtime/artifact interfaces.
3. Define the architecture-independent MindBackend interface.
4. Define immutable raw-mind output artifacts.
5. Implement resource accounting.
6. Assemble a candidate-model bakeoff.
7. Establish a one-mind coding baseline.
8. Establish four isolated-mind baselines.
9. Measure error correlation, unique solves, and oracle union.
10. Select the first four-mind population.
11. Implement the first model-independent structured evidence format.
12. Implement a minimal synthesis baseline.
13. Compare single, matched repeated sampling, same-model four-mind,
    heterogeneous four-mind, and heterogeneous + synthesis.
14. Add exact four-mind coalition attribution.
15. Add the first agentic/RLM harness while preserving pre-harness artifacts.
16. Measure harness uplift separately.
17. Add protected verification and adversarial review.
18. Only after those baselines are stable, enable continual candidate harness modification.
```

No additional custom transformer training is required to begin this sequence.

## 34. Long-term target

The target is not merely four agents talking.

The target is a system in which multiple capable minds, useful cognitive diversity, structured external knowledge, constructive synthesis, tools and persistent computation, independent verification, measured continual improvement, and protected evolutionary promotion produce a single collective intelligence that:

1. exceeds its strongest constituent on unfamiliar problems;
2. can show where that uplift came from through immutable causal lineage;
3. can discover improvements to the machinery creating that uplift;
4. can verify those improvements against protected external criteria;
5. can preserve alternative useful cognitive lineages;
6. can eventually improve its ability to improve.

The long-term direction is:

```text
capable minds
→ collective intelligence
→ measured amplification
→ verified self-improvement
→ improved collective intelligence
→ repeated verified improvement
```

This is a research program toward compounding collective intelligence. It is not a claim that artificial superintelligence has been achieved or that recursive improvement is guaranteed.
