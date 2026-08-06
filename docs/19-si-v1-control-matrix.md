# SI-V1 Frozen Control Matrix

## Purpose

This document freezes each comparison before empirical results are available.

All systems receive:

```text
the same frozen checkpoint
the same eight candidate paths per task
the same public task evidence
the same discovery/development/hidden/shift rows
the same per-task reasoning ceiling
the same exact post-selection scorer
```

No system may request additional model generations.

## Primary systems

### Immutable parent

```text
policy: complete-selection
genome: frozen SI parent
mutation: none
selection data: none
```

Purpose: establish the starting reasoning architecture.

### Single-best lineage

```text
parent source: current development-best genome
mutation: all unique adjacent one-field neighbors
promotion: one deterministic better descendant
budget: frozen total genome evaluations
```

Purpose: test greedy architectural hill climbing.

### Quality-diverse archive

```text
archive cell:
(mode family, verification class, synthesis-depth tier, compute tier)

one elite per cell
deterministic parent schedule
same genome-evaluation ceiling as controls
```

Purpose: test whether preserving non-best stepping stones crosses adaptation valleys.

The predeclared primary hidden finalist is the archive development champion.

## Matched controls

### No-mutation replay

Replay the immutable parent on every split.

Purpose: detect nondeterminism or data drift.

### Random genome search

```text
unique normalized genomes
unparented proposals
same total number of genome evaluations
same discovery/development scoring
same finalist freeze
```

Purpose: determine whether evolutionary organization adds value beyond finite random search.

Random proposals are not recorded as fabricated one-field descendants.

### Fixed verified-synthesis policy

A predeclared verified-synthesis genome is frozen in the experiment manifest.

Purpose: determine whether search adds value beyond manually enabling the strongest expected module.

### Shuffled-label archive

```text
public tasks unchanged
candidate paths unchanged
discovery/development targets deterministically permuted
hidden and shift targets unshuffled
```

Purpose: negative control for search and evaluator leakage.

A shuffled-label winner matching the primary invalidates a positive interpretation.

### Immediate-parent reversion

When the archive champion is a descendant, evaluate its immediate parent under the same hidden and shift ceilings.

Purpose: test whether the final retained mutation contributes causally to the result.

## Frozen genome space

### Modes

```text
complete-selection
verified-fragment-selection
verified-synthesis
unverified-synthesis
```

### Active synthesis fields

```text
rounds:                    1, 2, 3
unique candidates:         32, 64, 128
candidate evaluations:     64, 128, 256
generated composites:      64, 128, 256
expression nodes:          8, 12, 16
expression depth:          4, 6, 8
```

Selection-only genomes normalize all inactive synthesis fields to one canonical value. Inactive parameters cannot create archive diversity.

## Mutation rule

A lineage child changes exactly one active field to an adjacent domain value before normalization.

Every lineage mutation records:

```text
parent hash
child hash
field
old value
new value
generation
ordinal
```

Parents remain immutable.

## Promotion order

Discovery/development promotion uses, in order:

1. higher mean semantic accuracy;
2. higher exact accuracy;
3. lower invalid rate;
4. lower mean reasoning operations;
5. lower maximum operations;
6. lower genome complexity;
7. lower genome SHA-256.

Hidden and shift scores are absent from this ordering.

## Finalist roles

The finalist manifest always contains these roles in canonical order:

```text
immutable parent
single-best champion
archive champion
archive efficiency elite
archive behaviorally novel elite
random-search champion
shuffled-label champion
fixed verified-synthesis policy
```

Roles may point to the same genome. They may not be replaced after hidden opening.

## Resource matching

Primary ceiling:

```text
candidate paths per task:      8
packet extractions per task:   8
reasoning operations per task: 1024
genome evaluations:            64 per search strategy
archive capacity:              24
generations:                   8
```

Actual operations are recorded for every task and finalist.

A higher score outside the frozen ceiling receives no capability credit.

Cached packet preparation and deterministic fitness reuse reduce wall-clock cost only. Logical candidate pools, policy outputs, operation counts, and genome-evaluation budgets remain unchanged.

## Evaluator firewall

Policy execution accepts only:

```text
public task
frozen candidate pool
reasoning genome
reasoning budget
```

It returns one fixed expression or explicit failure.

The split scorer receives the fixed output afterward.

Target expressions are not present in:

- generation artifacts;
- candidate pools;
- genomes;
- mutation records;
- policy execution;
- synthesis ranking;
- archive placement;
- stopping rules.

## Single-run gate

The archive champion must:

- gain at least 5 percentage points over the parent on hidden semantic accuracy;
- have a paired 95% lower bound above zero;
- improve the shift split;
- beat random search;
- remain within the reasoning ceiling;
- beat the shuffled-label champion.

## Strong three-run gate

A strong claim additionally requires:

- three independent experiment hashes;
- three independent split-pool vectors;
- all single-run gates passing;
- mean hidden gain at least 5 percentage points;
- positive individual hidden lower bounds;
- positive run-level bootstrap lower bound;
- positive pooled-task bootstrap lower bound;
- positive shift gain in every run.

## Failure interpretation

### Archive equals parent

No supported architectural improvement under this genome and horizon.

### Fixed policy equals archive

Search did not add value beyond the predeclared architecture.

### Random equals archive

Evolutionary organization did not outperform random finite search.

### Single-best beats archive

The current archive descriptors or scheduling did not help.

### Discovery/development gain disappears on hidden

Search overfit the selection boundary.

### Hidden gain disappears on shift

Improvement did not generalize structurally.

### Shuffled-label control succeeds

Potential leakage, evaluator artifact, or search instability; invalidate the positive claim.

### Improvement requires a larger ceiling

Resource scaling, not architectural self-improvement.

## Claim boundary

Even a passing strong gate establishes only frozen-weight improvement of bounded external reasoning policy. It does not establish unrestricted recursive self-improvement, weight evolution, AGI, or ASI.
