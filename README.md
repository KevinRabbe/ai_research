# Plural Cognition and Open-Ended Intelligence Research

This repository investigates a research direction toward artificial superintelligence based on two independent claims:

1. **Plural cognition:** one artificial intelligence may contain multiple genuinely different cognitive perspectives that diverge, exchange structured knowledge, synthesize new hypotheses, and converge only after verification.
2. **Open-ended self-improvement:** the complete cognitive system may eventually improve not only task performance, but also the machinery through which it reasons, communicates, allocates compute, verifies claims, learns, and generates descendants.

The project is **not a product roadmap**. Its primary output is experimental evidence about whether these mechanisms work. Useful capabilities may appear in frozen snapshots, but product pressure must not determine the main research lineage.

## Core hypothesis

> Different cognitive paths can produce complementary claims, assumptions, counterexamples, predictions, and representations. A structured collective process may combine these fragments into a verified solution that no individual path contained.

The intended cognitive sequence is:

```text
diverge
→ extract knowledge
→ translate between representations
→ eliminate unsupported claims
→ synthesize improved hypotheses
→ verify
→ converge on one result
```

This is not ordinary majority voting, best-of-N selection, or conversational debate. The decisive event is **novel synthesis**: the collective constructs valid knowledge absent from every complete individual answer.

## First falsifiable milestone

The Version 0 specification defines the scientific protocol. Version 1 is the first runnable implementation.

Version 1 must test whether a small population of structurally identical models with independently learned weights can outperform:

- its strongest individual member;
- same-weight copies using the same coordination machinery;
- different-weight majority voting;
- best-of-N selection;
- ordinary debate;
- a no-synthesis ablation;
- an equal-budget extra-sampling control.

The architecture earns additional scale only if it demonstrates reproducible synthesis gain under matched compute and controlled evaluation.

## Research principles

- **Architecture-agnostic, process-strict.** The initial identical-model population is a starting hypothesis, not a permanent rule.
- **Diverge before converging.** Do not force one representation or opinion too early.
- **Evidence outranks popularity.** A correct minority must be able to overturn a wrong majority.
- **Preserve useful failures.** A wrong path may contain a correct relation, counterexample, or boundary condition.
- **External verification matters.** Claims should be tested through deterministic checks, simulations, experiments, prediction, or reproducible evidence where possible.
- **Negative results are progress.** Failed hypotheses and architectures remain documented.
- **Long-horizon evaluation.** A descendant may regress during adaptation before reaching a better capability frontier.
- **Never overwrite the qualified parent.** Self-improvement creates isolated descendants and reversible lineages.

## Repository map

- [`docs/00-research-charter.md`](docs/00-research-charter.md) — mission, non-goals, claims, and invariants
- [`docs/01-theory-of-plural-cognition.md`](docs/01-theory-of-plural-cognition.md) — different internal worlds, shared structure, and collective synthesis
- [`docs/02-population-cognitive-engine.md`](docs/02-population-cognitive-engine.md) — proposed seed architecture
- [`docs/03-version-0-experiment.md`](docs/03-version-0-experiment.md) — scientific protocol and falsification boundary
- [`docs/04-open-ended-self-improvement.md`](docs/04-open-ended-self-improvement.md) — recursive collective improvement across time
- [`docs/05-evolutionary-constitution.md`](docs/05-evolutionary-constitution.md) — rules that permit architectural freedom without trusting unverified changes
- [`docs/06-roadmap.md`](docs/06-roadmap.md) — gated research sequence
- [`docs/07-version-1-build-plan.md`](docs/07-version-1-build-plan.md) — first runnable experiment, task design, controls, metrics, and build order
- [`docs/08-v1.1-model-scale-selection.md`](docs/08-v1.1-model-scale-selection.md) — exact decoder brackets and hardware-aware selection protocol
- [`docs/09-v1.1-symbolic-codec.md`](docs/09-v1.1-symbolic-codec.md) — qualified symbolic grammar, context boundary, and decoder CPU contract
- [`docs/10-v1.1-cuda-preflight.md`](docs/10-v1.1-cuda-preflight.md) — exact RTX 4060 Ti throughput and memory procedure
- [`docs/11-reasoning-mathematics-and-search-design.md`](docs/11-reasoning-mathematics-and-search-design.md) — proof-carrying fragments, hypothesis graphs, semantic diversity, exact contribution attribution, and research-derived synthesis design
- [`docs/12-v1.2-cpu-population-foundation.md`](docs/12-v1.2-cpu-population-foundation.md) — qualified packet, graph, verification, contribution, and bounded synthesis contracts
- [`docs/references.md`](docs/references.md) — adjacent research and primary sources

## Current status

V1.0 is qualified: the repository contains the exact Boolean world, public evidence boundary, ambiguity rejection, and hidden exhaustive evaluator.

V1.1 contains:

```text
fixed symbolic vocabulary: 75 tokens
initial variables:          6
full causal context:        256 tokens
public task codec:          deterministic and lossless for model-visible semantics
mechanism parser:           strict and fail-closed
causal label mask:          answer tokens only
shared decoder family:      PC-4M, PC-10M, PC-18M
exact parameters:           4,741,120 / 9,859,840 / 17,731,584
CPU smoke:                  forward/backward implemented for all three
CUDA preflight runner:      deterministic 30-case default sweep and atomic JSON
```

The first V1.2 CPU population foundation is also qualified:

```text
canonical member packets:   strict decode, complete task binding, SHA-256
semantic diversity:         exact truth-table distance and error correlation
cooperative credit:         all 16 four-member coalitions and exact Shapley values
provenance graph:            typed nodes, typed/hyperedges, semantic merging
proof auditing:              visible support, contradiction, prediction, counterexample checks
bounded synthesis:           member-proposed operators, exact deduplication, hard limits
qualification:               87 tests green on CI run 136
```

A constructed infrastructure case confirms that the synthesizer can combine multi-source fragments into a visibly exact semantic result absent from every initial complete candidate. This is not evidence that trained models will produce such fragments reliably.

No empirical model-learning capability, target-machine GPU throughput, or plural-cognition gain has yet been established. The next external qualification is the exact RTX 4060 Ti sweep when the GPU is free. The next scientific qualification requires one-member learning curves, independently trained populations, learned packets, hidden exact evaluation, and matched controls.

## Commands

Install the research and training dependencies:

```text
python -m pip install -e ".[dev,train]"
```

Validate the CUDA sweep without requiring a GPU:

```text
plural-cognition-cuda-preflight --list-only
```

The complete target-machine command is documented in `docs/10-v1.1-cuda-preflight.md`.

## One-sentence description

> Build a system in which many different cognitive paths can become one intelligence, then test whether that intelligence can discover increasingly better ways to organize and improve itself.
