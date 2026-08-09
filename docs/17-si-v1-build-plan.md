# SI-V1: Runnable Frozen-Weight Self-Improvement Build Plan

## 1. Purpose

SI-V1 is the first executable experiment for the architectural self-improvement claim.

It is deliberately narrower than recursive self-improvement. The experiment asks whether bounded search can improve the external reasoning policy around one frozen checkpoint and one frozen set of model generations.

The complete run separates three layers:

```text
frozen proposal generation
→ mutable external reasoning policy
→ hidden evaluation after policy output is fixed
```

## 2. Questions

### Q1 — Descendant improvement

Can any isolated descendant outperform the immutable parent on hidden tasks under the same reasoning ceiling?

### Q2 — Generalization

Does development-selected improvement survive hidden seeds, held-out compositions, and deeper mechanisms?

### Q3 — Search organization

Does a quality-diverse archive find stronger hidden descendants than a single-best lineage or equal-budget random search?

### Q4 — Causal mechanism

Which one-field mutations created retained improvement, and do removing those changes reverse the gain?

### Q5 — Resource integrity

Does the result remain after matching candidate pools, model-generation cost, reasoning ceilings, and total genome-evaluation budgets?

## 3. Not tested

SI-V1 does not test:

- model-weight mutation;
- autonomous source-code rewriting;
- learned mutation proposal;
- learned evaluator design;
- unrestricted architecture generation;
- population topology evolution;
- recursive meta-improvement;
- open-world agent safety;
- AGI or ASI.

## 4. Frozen proposal corpus

The real run uses one selected Boolean-world checkpoint.

Generate eight ordered candidate paths per task with fixed sampling seeds:

```text
401, 402, 403, 404, 405, 406, 407, 408
```

Freeze:

- checkpoint binary and SHA-256;
- execution manifest;
- generation temperature and top-k;
- maximum generated tokens;
- ordered task-shard manifests;
- every generated token sequence;
- every parse failure;
- every canonical candidate expression.

All policies consume the same candidate rows. The evolution engine cannot call the model.

## 5. Task partitions

Build separate dataset shards with one shared data-generation contract and distinct split seeds:

```text
discovery:   256 tasks
development: 256 tasks
hidden:      512 tasks
shift:       512 tasks
```

The shift split should increase at least one structural factor:

- expression depth;
- held-out operator composition;
- intervention density;
- misleading visible correlations.

The hidden and shift targets remain inaccessible to search code.

## 6. Genome

Initial fields:

```text
mode
synthesis_rounds
max_unique_candidates
max_candidate_evaluations
max_generated_composites
max_expression_nodes
max_expression_depth
```

Mode values:

```text
complete-selection
verified-fragment-selection
verified-synthesis
unverified-synthesis
```

Canonicalization rules:

- selection modes force synthesis fields to fixed inactive defaults;
- synthesis caps must be internally consistent;
- expression depth cannot exceed node cap;
- duplicate normalized genomes share one SHA-256 identity.

## 7. Policy execution

For one task:

1. reconstruct the public task from the frozen task row;
2. parse every valid candidate against that task’s variable set;
3. create deterministic packets from candidate subexpressions;
4. run the genome-selected visible-only policy;
5. fix one canonical output or explicit failure;
6. record complete resource use;
7. return without target access.

The split scorer subsequently computes exact and semantic accuracy.

## 8. Mutation neighborhood

A mutation changes one active field to an adjacent value in its ordered domain.

Examples:

```text
complete-selection
→ verified-fragment-selection

verified-fragment-selection
→ verified-synthesis

rounds 1
→ rounds 2

candidate cap 32
→ candidate cap 64
```

Both upward and downward mutations are allowed.

Do not permit a mutation to increase several resources simultaneously.

## 9. Search strategies

### Single-best lineage

- start from the immutable parent;
- generate all unique one-step neighbors;
- evaluate candidates in deterministic hash order until the generation budget is exhausted;
- promote one development-best candidate;
- repeat for the frozen number of generations.

### Quality-diverse archive

Behavior descriptor:

```text
(mode family, verification class, synthesis-depth tier, compute tier)
```

- one elite per cell;
- deterministic round-robin parent scheduling;
- one-step neighbors;
- same total genome-evaluation budget as the single-best lineage;
- deterministic cell replacement.

### Random search

- sample unique normalized genomes from the complete bounded genome set;
- same number of evaluated genomes;
- same discovery/development scoring;
- same final hidden-opening procedure.

### Shuffled-label negative control

- use a deterministic permutation of discovery/development target labels;
- keep candidate pools and public tasks unchanged;
- hidden evaluation remains unshuffled;
- expect no reproducible hidden gain.

## 10. Fitness and promotion

For each split, report:

```text
exact accuracy
mean semantic accuracy
visible consistency
invalid rate
mean reasoning operations
maximum reasoning operations
```

Development ordering:

1. higher semantic accuracy;
2. higher exact accuracy;
3. lower invalid rate;
4. lower mean reasoning operations;
5. lower genome complexity;
6. lower genome SHA-256.

The hidden score is never part of this ordering.

## 11. Search budget

Initial CPU preflight:

```text
generations:             8
genome evaluations:     64 per strategy
archive cells:           at most 24
candidate paths/task:    8
per-task candidate cap:  128
per-task composite cap:  256
```

The final values may be reduced by CPU preflight before real results, but must then be frozen.

## 12. Finalists

Freeze before hidden opening:

- immutable parent;
- final single-best lineage champion;
- archive development champion;
- archive efficiency champion;
- archive most behaviorally novel valid elite;
- random-search champion;
- shuffled-label champion;
- predeclared fixed verified-synthesis policy.

Hidden evaluation scores exactly these frozen finalists.

Do not choose a new finalist after inspecting hidden scores.

## 13. Lineage evidence

Every result records:

- experiment manifest hash;
- candidate-pool hash;
- task-shard hashes;
- strategy;
- generation;
- genome hash;
- parent genome hash;
- mutation field and values;
- discovery and development metrics;
- resource use;
- archive cell;
- promotion or rejection reason;
- all descendant hashes.

Final reports include the complete ancestry of each hidden finalist.

## 14. Causal ablations

For every successful descendant:

1. revert the final mutation only;
2. replay the parent under the descendant’s resource ceiling;
3. disable each newly enabled module;
4. reduce each increased search limit one step;
5. test the descendant on a second independent candidate pool.

A claimed mechanism should lose at least part of its gain when its causal change is removed.

## 15. Statistics

Primary paired comparisons use task-level differences.

Report:

- mean semantic-accuracy gain;
- exact-accuracy gain;
- 95% paired bootstrap interval;
- win/tie/loss task counts;
- effect by task depth and mechanism family;
- compute difference;
- invalid-output difference.

Repeat the complete experiment on at least three independent candidate-pool/task seeds before a strong claim.

## 16. Build phases

### SI-V1.0 — exact genome and mutation layer

Implement:

- canonical genome;
- normalization;
- SHA-256;
- neighbor generation;
- mutation records;
- behavioral descriptors;
- unit and property tests.

Gate:

- no duplicate normalized genomes;
- every child differs by one field;
- mutations are deterministic and reversible;
- inactive fields cannot create false diversity.

### SI-V1.1 — frozen candidate pools

Implement:

- strict evaluation-artifact ingestion;
- same-checkpoint and same-task validation;
- public-task reconstruction;
- canonical candidate parsing;
- content-addressed pool format;
- explicit parse failures;
- pool replay tests.

Gate:

- pool generation is deterministic across input order;
- hidden targets are absent;
- any changed checkpoint, row, protocol, or expression changes the pool hash.

### SI-V1.2 — policy executor

Implement:

- packet extraction;
- complete selection;
- fragment selection;
- verified synthesis;
- unverified synthesis;
- resource accounting;
- over-budget failure;
- fixed-output trace.

Gate:

- hidden target cannot steer output;
- identical genome and pool produce identical output;
- resource limits fail closed;
- synthetic tasks demonstrate policies with different behavior.

### SI-V1.3 — immutable lineage and archive

Implement:

- candidate records;
- single-best lineage;
- quality-diverse archive;
- random-search control;
- shuffled-label control;
- deterministic scheduling;
- exact evaluation-budget accounting.

Gate:

- parents remain immutable;
- archive and lineage use equal genome-evaluation budgets;
- hidden scorer is absent from search interfaces;
- synthetic landscapes reproduce known stepping-stone and local-optimum cases.

### SI-V1.4 — final qualification

Implement:

- finalist freeze;
- hidden opening;
- paired statistics;
- causal reversion ablations;
- canonical reports;
- full execution CLI;
- restartable progress manifests.

Gate:

- one command can replay the complete frozen search and later open hidden results;
- hidden opening is impossible before finalist manifest creation;
- every score links to immutable pool, task, genome, and lineage hashes.

## 17. Proposed code layout

```text
src/plural_cognition/self_improvement/
├── genome.py
├── mutation.py
├── candidate_pool.py
├── policy.py
├── evaluation.py
├── archive.py
├── search.py
├── lineage.py
├── experiment.py
├── statistics.py
└── manifests.py

src/plural_cognition/
├── self_improvement_prepare_cli.py
├── self_improvement_search_cli.py
└── self_improvement_open_hidden_cli.py

tests/
├── test_si_genome.py
├── test_si_candidate_pool.py
├── test_si_policy.py
├── test_si_archive.py
├── test_si_search.py
├── test_si_statistics.py
└── test_si_cli.py
```

## 18. Execution boundary

Everything except checkpoint candidate generation and the final empirical run should be CPU-qualified before the GPU is needed.

Later GPU use is limited to:

```text
load one frozen checkpoint
→ generate the eight candidate paths for each split
→ write immutable evaluation artifacts
```

Evolution, archive search, hidden opening, ablations, statistics, and reporting run on CPU from the frozen pools.
