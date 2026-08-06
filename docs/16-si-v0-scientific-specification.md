# SI-V0: Frozen-Weight Architectural Self-Improvement Specification

## 1. Independent research claim

This experiment tests a claim separate from plural cognition:

> A cognitive system can discover a better external reasoning architecture while all neural weights, candidate generations, task evidence, and resource ceilings remain frozen.

A positive plural-population result is not required. The experiment may reuse qualified Boolean-world, checkpoint, manifest, and exact-evaluation infrastructure, but it must not use plural-population performance as a selection signal.

## 2. Narrow experimental question

Can a bounded evolutionary process produce an isolated descendant reasoning policy that outperforms its immutable parent on held-out tasks under the same frozen candidate pool and per-task compute ceiling?

The first experiment mutates only external machinery:

- complete-answer selection;
- visible verification;
- fragment extraction;
- fragment verification;
- bounded synthesis;
- search depth and candidate limits;
- fallback and stopping behavior.

Model weights, tokenizer, checkpoint, generated candidate pool, visible evidence, task splits, and hidden evaluator remain immutable.

## 3. Null and alternative hypotheses

### Null hypothesis

After matching candidate pools, task rows, mutation-evaluation budgets, and per-task reasoning ceilings, evolutionary architecture search produces no reproducible held-out advantage over:

- the immutable parent;
- no-mutation replay;
- random genome search;
- a single-best lineage;
- a fixed hand-selected policy using the same resources.

### Alternative hypothesis

At least one descendant discovered through the frozen mutation and promotion process:

1. improves held-out exact or semantic accuracy over the immutable parent;
2. remains within the same per-task resource ceiling;
3. beats matched search controls;
4. reproduces across independent task and candidate-pool seeds;
5. preserves exact mutation and lineage provenance.

## 4. Frozen candidate pool

One qualified checkpoint generates candidate answers once before evolution.

For every task, the pool stores:

- immutable task-row identity;
- model-visible public evidence;
- ordered generation-source identities;
- valid canonical expressions or explicit generation failures;
- generated token IDs;
- checkpoint, execution, generation-protocol, and dataset hashes.

The pool does not contain the hidden target.

The same pool is supplied to every parent, descendant, and control. Evolution cannot request extra model generations.

## 5. Task partitions

Use disjoint content-addressed partitions:

```text
discovery
→ used to generate and rank mutations

development
→ used for promotion and archive admission

hidden test
→ opened only after final descendants are frozen

shift test
→ deeper or held-out compositions opened after hidden-test evaluation
```

No hidden or shift score may influence:

- mutation generation;
- parent selection;
- archive placement;
- promotion;
- stopping;
- lineage choice.

## 6. Reasoning-policy genome

The initial discrete genome controls only already-qualified operations.

### Output mode

```text
complete-selection
verified-fragment-selection
verified-synthesis
unverified-synthesis
```

### Bounded synthesis fields

```text
max rounds:              1, 2, 3
unique candidate cap:    32, 64, 128
candidate-evaluation cap:64, 128, 256
composite-generation cap:64, 128, 256
expression node cap:     8, 12, 16
expression depth cap:    4, 6, 8
```

Inactive fields are canonicalized to fixed defaults so semantically identical genomes have one identity.

Every genome has canonical JSON and SHA-256.

## 7. Mutation contract

A child differs from its parent in exactly one active genome field before normalization.

Every mutation records:

- parent genome hash;
- child genome hash;
- field changed;
- old and new value;
- generation;
- mutation seed and ordinal;
- parent lineage identity.

The parent is never overwritten.

Duplicate normalized children are merged by genome hash while preserving every proposal source.

## 8. Evaluation firewall

A policy receives only:

```text
public task
+ frozen candidate pool
+ fixed reasoning budget
```

It fixes one output using visible evidence only.

Only after the output is fixed may the split evaluator compare it with the hidden target for that split.

The hidden evaluator must not be reachable from policy execution, synthesis, ranking, fallback, pruning, or stopping code.

## 9. Resource accounting

Record per task:

- candidate inputs consumed;
- packet extractions;
- fragment audits;
- unique candidates evaluated;
- composites generated;
- synthesis rounds;
- expression nodes considered;
- wall-clock time;
- peak RAM where measured.

Every genome is rejected or marked over-budget if it exceeds the frozen per-task ceiling.

Primary comparisons require the descendant to stay within the same ceiling as the parent. Report actual compute separately.

## 10. Evolution strategies

### Immutable parent

The starting policy is fixed before results:

```text
complete-selection
```

with canonical inactive synthesis defaults.

### Single-best lineage

Each generation mutates only the current development-best parent. One descendant is promoted through deterministic score, compute, complexity, and genome-hash tie-breaking.

### Quality-diverse archive

Maintain one elite per behavioral bin. Initial bins use:

- output-mode family;
- verification strictness;
- synthesis-depth tier;
- compute tier.

Parents are sampled deterministically across occupied bins. Archive capacity and candidate-evaluation budget are fixed.

### Random-search control

Sample unique genomes from the same bounded genome space using the same total number of genome evaluations.

### No-mutation control

Replay the immutable parent through every generation and split.

## 11. Promotion rule

A descendant may replace a lineage parent or archive elite only when:

1. it is valid on every required discovery/development task;
2. it stays within resource ceilings;
3. its development score is better, or equal with lower actual compute;
4. equal score and compute are resolved by lower policy complexity, then genome hash;
5. the full parent remains preserved.

Hidden scores never participate.

## 12. Primary metrics

### Capability

- exact semantic accuracy;
- mean semantic accuracy;
- visible-consistency rate;
- invalid-output rate.

### Improvement

```text
held-out descendant gain
= descendant hidden score - immutable-parent hidden score
```

Also report:

- gain over random search;
- gain over single-best lineage;
- gain of archive champion;
- archive frontier versus lineage frontier;
- generations to first retained improvement;
- improvement survival on shift tests.

### Efficiency

- mean and maximum reasoning operations;
- actual versus allowed compute;
- score per operation;
- mutation evaluations consumed;
- archive occupancy;
- duplicate mutation rate.

### Evolutionary value

- number of promoted descendants;
- lineage depth;
- behavioral diversity;
- unique components preserved;
- descendants generated from non-best archive cells;
- hidden winners whose ancestors were not current-best performers.

## 13. Controls

Required first-run controls:

1. immutable parent;
2. no-mutation replay;
3. random genome search;
4. single-best lineage;
5. quality-diverse archive;
6. fixed best hand-coded policy selected before hidden results;
7. parent with the same maximum reasoning ceiling;
8. shuffled discovery labels as a negative control.

The shuffled-label search must not produce reproducible hidden improvement.

## 14. Provisional success criterion

Freeze after CPU preflight and before real candidate-pool results.

A strong positive first result requires:

1. archive or lineage descendant hidden semantic-accuracy gain of at least 5 percentage points over the immutable parent;
2. paired 95% bootstrap lower bound above zero;
3. no increase in the frozen per-task resource ceiling;
4. superiority over matched random search;
5. reproduction across at least three independent candidate-pool/task seeds;
6. nonzero gain on the held-out composition or depth-shift split;
7. exact lineage and mutation provenance;
8. no hidden-evaluator access during search.

A smaller consistent effect is reported as a weak signal, not proof.

## 15. Failure interpretations

### Discovery gain only

The search overfit the discovery tasks.

### Development gain but no hidden gain

Promotion overfit the development boundary.

### Hidden gain disappears under compute matching

The apparent improvement was resource scaling.

### Random search matches evolution

The evolutionary organization added no value beyond finite genome search.

### Single-best beats archive

Quality diversity did not help at this horizon or descriptor design.

### Archive wins only through more evaluated genomes

The result is search-budget scaling, not archive value.

### Descendants exploit evaluator artifacts

Invalidate the run, preserve evidence, and redesign the evaluator firewall.

### No genome improves

Either the mutable architecture space is insufficient, the parent is already optimal for the frozen pool, or the self-improvement hypothesis has no support under this implementation.

## 16. Claim boundary

A passing experiment supports only:

> Under a frozen checkpoint, frozen candidate pools, fixed task partitions, and controlled reasoning budgets, the bounded evolutionary process discovered an external reasoning-policy descendant that generalized better than its immutable parent and matched controls.

It does not establish:

- recursive unrestricted self-modification;
- weight self-improvement;
- open-ended intelligence;
- AGI or ASI;
- safe autonomous deployment;
- that the initial genome is the final architecture.
