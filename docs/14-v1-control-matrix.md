# V1 Control Matrix

## Purpose

Version 1 must separate four possible explanations for a collective gain:

1. the system generated more candidates;
2. several members repeated the same answer;
3. one member already contained the winning answer;
4. genuinely different learned weights supplied complementary knowledge that structured synthesis combined.

Every control below receives fixed model outputs before hidden evaluation begins.

## Per-population controls

| Condition | Inputs | Decision rule before hidden scoring | What it tests |
|---|---|---|---|
| Complete selection | Complete candidate from each member | Highest visible agreement, then lower complexity and canonical tie break | Best-of-N without fragment use or synthesis |
| Complete majority | Complete candidate from each member | Most frequent exact semantic function, then visible-only deterministic tie break | Whether vote count explains the result |
| Verified-fragment selection | Complete candidates plus fragments whose proof metadata passes visible checks | Select one existing semantic candidate; no composition | Whether fragment extraction alone explains the gain |
| Verified synthesis | Complete candidates plus visibly verified fragments | Bounded composition using only operators present in accepted proposals | Primary structured-synthesis mechanism |
| Unverified synthesis | Complete candidates plus all proposed fragments | Same bounded search without proof-metadata filtering | Whether verification improves or prevents damage |

Hidden truth never selects among candidates in these conditions. It scores only the already-fixed output.

## Cross-population controls

### Different-checkpoint greedy population

```text
four independently initialized checkpoints
same architecture
same data
same optimizer and token budget
same greedy decoding
same validation rows
same synthesis machinery
```

Artifact classification:

```text
different-checkpoint-greedy
```

This is the primary V1 condition.

### Same-checkpoint sampled population

```text
one predeclared checkpoint: selected scale, initialization seed 101
four fixed sampling seeds: 301, 302, 303, 304
temperature: 1.0
top-k: 8
same validation rows
same extraction and synthesis machinery
```

Artifact classification:

```text
same-checkpoint-sampled
```

This controls for obtaining four trajectories without learning four different weight states.

The control is invalid for the primary comparison if fewer than 95% of tasks remain analyzable.

## Internal population gate

The different-checkpoint population must satisfy all of the following:

1. analysis coverage at least 95%;
2. mean synthesis gain at least five percentage points;
3. paired bootstrap lower bound for synthesis gain above zero;
4. at least one exact, novel, multi-source synthesis event;
5. verified synthesis exceeds complete selection;
6. verified synthesis exceeds complete majority;
7. verified synthesis exceeds verified-fragment selection.

A multi-source event requires:

```text
final semantics absent from every initial complete answer
+ final output exactly correct
+ final provenance contains several members
+ removal/coalition analysis shows at least two score-necessary members
```

Provenance alone does not establish necessity.

## Cross-condition gate

The final paired comparison requires:

1. primary artifact type is `different-checkpoint-greedy`;
2. control artifact type is `same-checkpoint-sampled`;
3. both artifacts bind the same ordered validation-shard manifests;
4. primary passes its internal gate;
5. same-weight analysis coverage is at least 95%;
6. per-task primary-minus-control synthesis accuracy has a 95% bootstrap lower bound above zero;
7. per-task primary-minus-control synthesis gain has a 95% bootstrap lower bound above zero.

The executable command is:

```text
plural-cognition-compare-conditions
```

## Interpretation of outcomes

### Primary fails its internal gate

No plural-cognition signal was demonstrated. Inspect:

- individual capability;
- parse validity;
- functional diversity;
- fragment quality;
- search coverage;
- verifier exclusions;
- premature convergence.

### Primary passes internally but not against same-weight sampling

Structured synthesis may work, but different learned weights did not demonstrate added value beyond stochastic sampling.

### Same-weight control has low coverage

The comparison is inconclusive. Do not count malformed sampled paths as evidence for the primary mechanism. Revisit the predeclared sampling protocol in a new experiment version rather than tuning it inside the completed experiment.

### Both paired advantages pass

The experiment supports the narrow V1 claim:

> Under the frozen Boolean-world protocol, independently learned weights supplied useful diversity that the same structured synthesis process exploited more effectively than four sampled paths from one checkpoint.

This remains a domain-specific mechanism result, not a claim of general intelligence or artificial superintelligence.

## Still separate from the first signal

The following remain later replications or extensions rather than hidden requirements added after V1 results:

- larger monolithic parameter-matched control;
- ordinary natural-language debate;
- linear-chain versus graph-native synthesis;
- additional independently trained four-member populations;
- a second exact task family;
- 50-million-token capability trajectories;
- heterogeneous model architectures;
- active intervention selection;
- recursive architectural self-improvement.
