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
- [`docs/08-v1.1-model-scale-selection.md`](docs/08-v1.1-model-scale-selection.md) — RTX 4060 Ti model candidates, preflight protocol, and selection rule
- [`docs/references.md`](docs/references.md) — adjacent research and primary sources

## Current status

V1.0—the deterministic Boolean world and hidden exact evaluator—is implemented and qualified.

V1.1 now has a provisional model-scale decision:

```text
lower calibration model:  approximately 4.75M parameters
primary model:            approximately 9.87M parameters
upper calibration model: approximately 17.74M parameters
```

The primary implementation target is an eight-layer, width-320 decoder with five 64-dimensional attention heads. The final population scale will be the smallest candidate that reaches nontrivial but unsaturated hidden exact accuracy and useful functional disagreement across independently trained seeds.

The immediate next code slice remains narrower than model training:

```text
compact symbolic vocabulary
→ deterministic public-task codec
→ canonical mechanism output codec
→ exact parser and malformed-output rejection
→ round-trip tests
```

Only after the codec is trustworthy should the three model scales be instantiated and benchmarked.

## One-sentence description

> Build a system in which many different cognitive paths can become one intelligence, then test whether that intelligence can discover increasingly better ways to organize and improve itself.