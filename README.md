# Plural Cognition and Open-Ended Intelligence Research

This repository investigates whether one artificial intelligence can benefit from containing several genuinely different learned perspectives that diverge, contribute structured knowledge, synthesize new hypotheses, and converge only after verification.

A second, later research direction studies whether the complete cognitive system can improve its own reasoning, communication, verification, learning, resource allocation, and descendant-generation machinery.

This is a research program, not a product roadmap.

## Core hypothesis

> Different learned cognitive paths can contain complementary claims, conditions, counterexamples, and partial mechanisms. A structured collective process may combine those fragments into a verified solution absent from every complete individual answer.

The intended process is:

```text
diverge
→ extract structured knowledge
→ preserve provenance and contradiction
→ compose new hypotheses
→ verify
→ converge
```

This is not ordinary majority voting, best-of-N selection, or conversational debate.

The decisive event is **novel synthesis**:

```text
final exact solution
not present in any initial complete answer
requires useful contributions from several members
beats simpler controls under matched conditions
```

## First falsifiable milestone

Version 0 defines the scientific protocol. Version 1 is the first executable experiment.

The initial task family is **Boolean Mechanism Worlds**. It provides:

- exact hidden mechanisms;
- deterministic public evidence;
- one-bit interventions;
- exhaustive semantic equivalence;
- exact counterexamples;
- objective hidden evaluation;
- no learned judge model.

The first population uses four structurally identical decoders with independently learned weights.

Candidate model scales:

```text
PC-4M:   4,741,120 parameters
PC-10M:  9,859,840 parameters
PC-18M: 17,731,584 parameters
```

The selected scale is not chosen manually. Two seeds at each scale are trained under the same 10-million-token screening budget. The smallest model with at least 95% valid parses and mean exact accuracy between 20% and 70% is selected.

## Experimental conditions

The primary population is:

```text
four independently initialized checkpoints
same architecture
same data
same optimizer and token budget
same greedy decoding
same structured synthesis machinery
```

It must outperform:

- strongest individual member;
- best complete-answer selection;
- complete-answer majority voting;
- verified-fragment selection without composition;
- unverified synthesis;
- four sampled paths from one predeclared checkpoint;
- equal hidden-evaluation and validation rows.

The final paired condition comparison requires different learned weights to improve both collective semantic accuracy and synthesis gain over the same-checkpoint sampled population, with 95% bootstrap lower bounds above zero.

## Implemented foundation

### V1.0 — exact Boolean world

- immutable Boolean AST;
- deterministic normalization;
- exhaustive truth tables and semantic equivalence;
- exact semantic distance and counterexamples;
- semantically deduplicated catalogs;
- deterministic observations and interventions;
- public task separated from hidden target and evaluator state;
- ambiguous-task rejection.

### V1.1 — symbolic learner and GPU measurement

- fixed 75-token vocabulary;
- strict symbolic task and mechanism codecs;
- answer-only causal supervision;
- six-variable, 256-token initial training boundary;
- exact PC-4M, PC-10M, and PC-18M decoder configurations;
- CPU forward/backward qualification;
- fail-closed RTX 4060 Ti CUDA preflight runner.

### V1.2 — population reasoning infrastructure

- immutable proof-carrying member packets;
- strict canonical packet decoder and SHA-256 binding;
- visible support, contradiction, prediction, and counterexample auditing;
- exact semantic diversity and error-correlation metrics;
- typed provenance graph and derivation hyperedges;
- bounded visible-only symbolic synthesis;
- exact semantic deduplication;
- all 16 coalitions for four members;
- leave-one-out necessity and exact Shapley attribution;
- different-checkpoint and same-checkpoint condition classification.

### V1.3 — complete execution and analysis harness

- deterministic index-addressed training stream;
- content-addressed dataset shards;
- immutable run and execution manifests;
- measured microbatch resolution from CUDA preflight results;
- exact matched-token optimizer geometry;
- atomic checkpoints and resumable execution-bound sidecars;
- strict greedy and reproducible sampled generation;
- exact validation evaluation artifacts;
- automatic model-scale selection;
- automatic four-member population plan reusing two screening runs;
- executable best-of-N, majority, fragment, verified-synthesis, and unverified-synthesis controls;
- full per-task population analysis;
- deterministic bootstrap qualification;
- paired different-weight versus same-weight condition gate.

## Scientific boundary

The repository currently establishes software, mathematical, and experimental contracts.

It proves that the machinery can:

```text
validate contributions
→ preserve provenance
→ verify visible claims
→ compose bounded hypotheses
→ fix outputs without hidden guidance
→ score them exactly afterward
→ attribute contribution
→ compare primary and control conditions reproducibly
```

It does **not** yet establish:

- GPU throughput on the user's RTX 4060 Ti;
- learned Boolean-world capability;
- useful functional diversity between trained checkpoints;
- a plural-cognition capability gain;
- general intelligence;
- artificial superintelligence;
- recursive self-improvement.

Those claims require the measured runs and result artifacts defined in the execution procedure.

## Installed commands

```text
plural-cognition-cuda-preflight
plural-cognition-build-dataset
plural-cognition-resolve-screening
plural-cognition-prepare-screening-executions
plural-cognition-prepare-execution
plural-cognition-train
plural-cognition-evaluate
plural-cognition-select-scale
plural-cognition-prepare-population-plan
plural-cognition-evaluate-population
plural-cognition-compare-conditions
```

Install and run the CPU qualification suite:

```text
python -m pip install -e ".[dev,train]"
pytest
```

The full PowerShell procedure is in [`docs/13-v1-execution-and-analysis-procedure.md`](docs/13-v1-execution-and-analysis-procedure.md).

## Repository map

- [`docs/00-research-charter.md`](docs/00-research-charter.md) — mission, non-goals, claims, and invariants
- [`docs/01-theory-of-plural-cognition.md`](docs/01-theory-of-plural-cognition.md) — different internal worlds and shared external structure
- [`docs/02-population-cognitive-engine.md`](docs/02-population-cognitive-engine.md) — seed population architecture
- [`docs/03-version-0-experiment.md`](docs/03-version-0-experiment.md) — falsification protocol
- [`docs/04-open-ended-self-improvement.md`](docs/04-open-ended-self-improvement.md) — recursive collective improvement
- [`docs/05-evolutionary-constitution.md`](docs/05-evolutionary-constitution.md) — reversible architectural evolution rules
- [`docs/06-roadmap.md`](docs/06-roadmap.md) — gated research sequence
- [`docs/07-version-1-build-plan.md`](docs/07-version-1-build-plan.md) — Version 1 questions, controls, and build order
- [`docs/08-v1.1-model-scale-selection.md`](docs/08-v1.1-model-scale-selection.md) — hardware-aware model brackets and selection rule
- [`docs/09-v1.1-symbolic-codec.md`](docs/09-v1.1-symbolic-codec.md) — symbolic representation and decoder contract
- [`docs/10-v1.1-cuda-preflight.md`](docs/10-v1.1-cuda-preflight.md) — target-machine GPU measurement
- [`docs/11-reasoning-mathematics-and-search-design.md`](docs/11-reasoning-mathematics-and-search-design.md) — proof-carrying fragments, graphs, search, and attribution
- [`docs/12-v1.2-cpu-population-foundation.md`](docs/12-v1.2-cpu-population-foundation.md) — qualified population infrastructure
- [`docs/13-v1-execution-and-analysis-procedure.md`](docs/13-v1-execution-and-analysis-procedure.md) — complete operational sequence
- [`docs/14-v1-control-matrix.md`](docs/14-v1-control-matrix.md) — frozen baselines and interpretation rules
- [`docs/references.md`](docs/references.md) — adjacent primary research

## Research principles

- Architecture-agnostic, process-strict.
- Diverge before converging.
- Evidence outranks popularity.
- Preserve useful failures.
- Hidden truth scores fixed results but never guides synthesis.
- Negative results remain published and useful.
- Never overwrite a qualified parent or completed experiment.
- Do not increase scale until the current mechanism earns it.

## One-sentence description

> Build a system in which many different cognitive paths can become one verified intelligence, then test whether that intelligence can discover increasingly better ways to organize and improve itself.
