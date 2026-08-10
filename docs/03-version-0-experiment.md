# Version 0: Falsifiable Population-Synthesis Experiment

## 1. Purpose

Version 0 exists to answer one narrow question cheaply and repeatedly:

> Can a small population of structurally identical models with independently learned weights, all receiving the same complete problem and evidence, construct a verified solution better than every individual member and better than simpler aggregation methods?

Version 0 is not an assistant, product, general agent, or self-improving system.

## 2. Null and alternative hypotheses

### Null hypothesis H0

After controlling for total compute, sampling count, model capacity, and verification access, structured population synthesis provides no reproducible improvement over the strongest simpler baseline.

### Alternative hypothesis H1

Structured population synthesis produces a positive and reproducible synthesis gain on held-out tasks, including cases where the final correct relation was absent from every complete initial answer.

## 3. Provisional scale

Initial target:

```text
population:             4–8 members
parameters per member:  approximately 5–20 million
architecture:           identical small decoder transformer
weights:                independently initialized and trained
context:                256–512 tokens initially
task domain:            synthetic logic, causal, algorithmic, or rule-discovery tasks
verification:           deterministic wherever possible
hardware target:        one consumer GPU; sequential or small-batch execution allowed
```

The exact parameter count must be determined by a preflight. Each member must be capable enough to produce meaningful partial reasoning, but weak enough that the collective problem is not saturated.

## 4. Experimental systems

All systems receive identical task instances, data splits, verifier access, and matched inference budgets.

### System A — monolithic capacity control

One larger model with approximately matched total active parameters or matched inference FLOPs.

Purpose: test whether population organization adds value beyond ordinary model scaling.

This comparison may be deferred until the smaller controls show a signal.

### System B — proposed population synthesis

```text
different weights
+ independent first-pass reasoning
+ structured claim extraction
+ contradiction analysis
+ synthesis
+ independent verification
```

### System C — same-weight population control

```text
N copies of one weight set
+ identical orchestration and compute
```

Purpose: isolate whether weight-level learning diversity contributes beyond stochastic sampling and orchestration.

### System D — ordinary aggregation controls

Run multiple different-weight members but use only:

- majority vote;
- best-of-N selection;
- confidence-weighted vote;
- ordinary natural-language debate.

Purpose: test whether structured synthesis exceeds selection or discussion.

### System E — no-synthesis ablation

Use the different-weight population, structured workspace, elimination, and verification, but prohibit construction of a new combined hypothesis.

Purpose: isolate the contribution of synthesis.

## 5. Same complete evidence requirement

Every member receives the same complete task and evidence.

Version 0 must not rely on artificially hiding one necessary clue from each member and then proving that communication can reunite the clues. Distributed-information tasks may be useful later, but they do not test the core claim.

The desired diversity should arise from different learned functions and reasoning paths, not from privileged input access.

## 6. Task design

Tasks should have exact ground truth and support multiple legitimate approaches. They should be difficult enough to generate partial insight and systematic error, but not so difficult that all models fail without signal.

Candidate task families:

- hidden-rule systems with interacting conditions;
- causal graphs with confounders, interventions, and misleading correlations;
- small programs requiring diagnosis from specifications and traces;
- symbolic transformation systems;
- compositional logic problems with exceptions;
- mathematical constructions requiring multiple lemmas;
- algorithmic planning tasks with misleading local strategies.

Good tasks should permit examples such as:

```text
Member 1 identifies the main mechanism but misses a boundary condition.
Member 2 rejects the mechanism but discovers the boundary condition.
Member 3 finds a counterexample to the naive version.
Member 4 derives a prediction that distinguishes two explanations.

Collective synthesis:
The mechanism is valid only under the boundary condition,
and the counterexample occurs outside that regime.
```

## 7. Preventing benchmark leakage

Task generators should produce:

- training instances;
- public development instances;
- held-out seeds;
- held-out structural templates;
- adversarial variants;
- out-of-distribution combinations.

The final test set should remain inaccessible to the training process and synthesis controller.

A result that depends on memorized templates does not establish plural cognition.

## 8. Fixed Version 0 cognitive protocol

Version 0 should minimize learned orchestration.

### Round 1 — independent divergence

Each member receives the same complete task and produces a structured private analysis without access to other members.

Required fields may include:

```text
candidate conclusion
claims
assumptions
supporting evidence
counterexamples
predictions
uncertainties
proposed checks
```

### Round 2 — extraction and normalization

Convert each path into claim records. Equivalent claims may be linked, but raw paths remain preserved.

### Round 3 — contradiction and compatibility analysis

Identify:

- direct contradictions;
- assumption conflicts;
- shared predictions;
- compatible partial mechanisms;
- missing variables;
- claims requiring verification.

### Round 4 — synthesis

Construct one or more new candidates from compatible components. Record full provenance and identify any newly introduced relation.

### Round 5 — adversarial verification

Allocate independent critics and deterministic tools to attack each synthesized candidate.

### Round 6 — final integration

Return one of three states:

1. verified solution;
2. unresolved alternatives with a discriminating test;
3. insufficient surviving explanation.

The system should never be rewarded for forced certainty.

## 9. Primary metrics

### 9.1 Individual maximum

\[
S_{individual} = \max_i S(M_i)
\]

### 9.2 Collective synthesis score

\[
S_{collective} = S(\text{verified collective result})
\]

### 9.3 Synthesis gain

\[
G_{synthesis} = S_{collective} - S_{individual}
\]

The core claim requires positive synthesis gain across held-out tasks and seeds.

### 9.4 Novel synthesis rate

Fraction of correct collective solutions containing at least one necessary relation that appeared in no complete individual initial answer.

### 9.5 Multi-source necessity

Fraction of correct collective solutions whose proof or causal explanation requires valid components originating from multiple members.

### 9.6 Minority rescue

Rate at which a correct minority claim defeats a wrong majority after evidence or deterministic verification.

### 9.7 Functional diversity

Measure diversity through:

- pairwise error correlation;
- hypothesis overlap;
- method classification;
- unique valid claims;
- unique counterexamples;
- prediction disagreement;
- contribution entropy.

### 9.8 Coordination cost

Record:

- total FLOPs or model calls;
- tokens or internal representation volume;
- wall-clock time;
- peak memory;
- workspace writes and reads;
- verification calls;
- duplicated work.

## 10. Required ablations

At minimum:

1. different weights versus same weights;
2. independent first round versus immediate communication;
3. structured workspace versus free-form discussion;
4. synthesis enabled versus disabled;
5. deterministic verification versus model-only judging;
6. provenance enabled versus hidden;
7. fixed population size versus matched additional sampling;
8. same curriculum versus partially different training histories.

## 11. Pre-registration

Before final evaluation, record:

- model architecture and parameter count;
- training data generator and splits;
- population size;
- inference budget;
- all baselines;
- success thresholds;
- statistical tests;
- allowed tuning decisions;
- failure criteria.

This prevents redesigning the definition of success after observing results.

## 12. Success criteria

A strong positive result requires System B to:

1. exceed the strongest individual member;
2. exceed System C;
3. exceed majority vote and best-of-N;
4. exceed the no-synthesis ablation;
5. demonstrate traceable novel synthesis;
6. preserve or rescue valid minority evidence;
7. generalize to held-out structures;
8. retain its advantage after compute matching;
9. reproduce across multiple independent training seeds.

A weak or partial result should be reported as such.

## 13. Failure interpretation

### B equals C

Different weights did not provide useful additional diversity under the tested training process. Test learning-history, curriculum, memory, or architecture diversity before rejecting plural cognition.

### B equals D or E

The population helps, but structured synthesis adds no value. Redesign the integration mechanism.

### B loses to the strongest member

Coordination destroys more information than it creates. Investigate provenance, expertise weighting, hierarchy, or verification.

### All systems fail

The member models or tasks may be poorly calibrated. Establish that individual models can solve meaningful subsets before interpreting the population result.

### No consistent synthesis gain after reasonable redesign

Reject this implementation as the central route. Preserve the broader question of how different cognitive perspectives can be combined and search for another mechanism.

## 14. Gate to further work

Dynamic allocation, learned communication, recursive improvement, population evolution, and larger models should not begin until Version 0 produces a credible signal.

The architecture must earn the right to become larger.
