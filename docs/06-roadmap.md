# Gated Research Roadmap

## Principle

Each phase exists to answer a narrower question before the project earns permission to add complexity.

```text
prove the mechanism
→ isolate its cause
→ improve its allocation
→ improve its organization
→ evolve the organization
→ broaden what may evolve
```

A phase may end in rejection. Negative results should redirect the architecture rather than trigger blind scaling.

## Phase 0 — formalization and benchmark preflight

### Question

Can the core hypothesis be stated and measured without relying on subjective answer quality?

### Deliverables

- formal claim and null hypothesis;
- synthetic task-generator candidates;
- deterministic verifiers;
- provisional member architecture;
- compute and memory preflight;
- diversity metrics;
- preregistration template;
- reproducibility protocol.

### Gate

Proceed only when individual models show nontrivial but imperfect capability and the benchmark can distinguish partial insight, full solutions, and invalid synthesis.

## Phase 1 — static plural synthesis

### Question

Can different-weight members with the same complete evidence produce a collective result better than every member and simpler aggregation?

### Systems

- proposed structured synthesis population;
- same-weight copies;
- majority vote;
- best-of-N;
- ordinary debate;
- no-synthesis ablation;
- later, matched larger monolithic model.

### Gate

Proceed only if positive synthesis gain is reproducible across seeds and held-out task structures, with traceable multi-member contribution.

### Failure response

- redesign extraction or synthesis;
- test learning-history diversity;
- test better verification;
- test hierarchy or provenance;
- reject the implementation if repeated redesign does not produce a signal.

## Phase 2 — dynamic compute allocation

### Question

Can the system allocate active population capacity according to uncertainty, novelty, verification need, and expected information gain?

### Initial design

Start with an explicit controller rather than an end-to-end learned allocator.

Possible actions:

- activate additional independent paths;
- deepen one hypothesis;
- search for counterexamples;
- request external evidence;
- run simulation;
- allocate independent verification;
- stop and answer.

### Controls

- fixed allocation;
- full population on every task;
- random allocation;
- difficulty-only heuristics;
- oracle allocation where possible.

### Gate

Proceed only if adaptive allocation improves capability or information gain under matched compute, not merely latency on easy tasks.

## Phase 3 — learned communication and synthesis

### Question

Can the collective learn better ways to translate, compress, preserve, and combine different internal representations?

### Scope

- claim extraction;
- relation matching;
- contradiction detection;
- latent or structured communication;
- synthesis proposal;
- provenance tracking;
- communication bandwidth control.

### Main risk

Communication may cause diversity collapse.

### Gate

Proceed only if learned communication improves synthesis while maintaining measurable functional plurality and minority rescue.

## Phase 4 — frozen-weight architectural self-improvement

### Question

Can the system improve its collective machinery while all member weights remain frozen?

### Mutable components

- workspace schema;
- allocation policy;
- communication policy;
- pruning;
- synthesis;
- verification;
- tool-use procedures;
- experiment design.

### Evaluation

Every mutation creates an isolated descendant. Compare against the immutable parent and hidden tasks.

### Gate

Proceed only if descendants repeatedly generalize improvements beyond the tasks used to propose them.

## Phase 5 — quality-diverse evolutionary archive

### Question

Does preserving diverse lineages produce better long-term descendants than following only the current best system?

### Compare

```text
single-best lineage
versus
quality-diverse archive
```

### Metrics

- current performance;
- novelty;
- adaptation rate;
- mature capability;
- descendant quality;
- component reuse;
- diversity retained;
- long-horizon frontier.

### Gate

Proceed only if archived stepping stones produce reproducible long-horizon benefit.

## Phase 6 — meta-improvement

### Question

Can the system improve the process that proposes, schedules, and evaluates improvements?

### Mutable components

- mutation proposal policy;
- parent selection;
- candidate resource allocation;
- failure analysis;
- benchmark generation;
- archive policy;
- maturation-time estimation.

### Main risk

Evaluator capture or hidden resource scaling.

### Gate

Proceed only if the improvement process itself becomes more effective on held-out architectural problems under controlled resources.

## Phase 7 — controlled weight evolution

### Question

Can member learning histories and weights evolve without collapsing population diversity or causing untraceable regressions?

### Scope

- bounded fine-tuning;
- alternative curricula;
- member specialization;
- diversity-preserving objectives;
- lineage-specific memories;
- weight recombination experiments.

### Gate

Proceed only if weight evolution improves collective synthesis and generalization beyond what external machinery alone achieved.

## Phase 8 — population topology and heterogeneous cognition

### Question

What organization of cognitive components best supports collective intelligence?

### Candidate structures

- flat identical populations;
- different model sizes;
- heterogeneous architectures;
- hierarchical populations;
- temporary coalitions;
- specialist subpopulations;
- population-of-populations;
- neural plus symbolic systems;
- causal models and simulators;
- newly evolved structures.

### Gate

No preferred final architecture is assumed. Candidates compete under the evolutionary constitution.

## Phase 9 — hardware-aware evolution

### Question

Can the cognitive architecture and hardware execution strategy co-evolve without confusing hardware scale with cognitive improvement?

### Possible targets

- grouped matrix execution;
- local weight storage;
- communication topology;
- memory placement;
- conditional activation;
- model compression;
- custom kernels;
- accelerator specialization;
- alternative computing substrates.

### Requirement

Report cognitive mechanism gains separately from raw hardware gains.

## Phase 10 — open-ended research organism

### Target property

A qualified system that:

- maintains multiple cognitive perspectives;
- constructs verified collective knowledge;
- discovers and tests improvements to its own organization;
- preserves useful alternative lineages;
- improves its improvement process;
- remains empirically auditable;
- can generate frozen useful snapshots without allowing product pressure to govern the main lineage.

This phase is a direction, not a promised endpoint.

## Cross-phase stop conditions

Pause or redirect when:

- the central metric cannot be measured reliably;
- improvements disappear under held-out evaluation;
- gains reduce to extra compute or data;
- diversity collapses without compensation;
- coordination consistently underperforms the strongest member;
- verification cannot distinguish synthesis from plausible fabrication;
- candidate containment or rollback assumptions fail;
- repeated redesign fails to produce information supporting the route.

## Immediate next actions

1. Select one or two deterministic task families.
2. Build task generators and exact verifiers.
3. Run a parameter-scale preflight on the available GPU.
4. Establish one-member capability curves.
5. Freeze Version 0 systems, metrics, and success thresholds.
6. Run same-weight and different-weight training across multiple seeds.
7. Execute the controlled comparison.
8. Publish all outcomes before expanding scope.
