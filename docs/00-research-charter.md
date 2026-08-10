# Research Charter

## 1. Mission

Investigate whether an artificial cognitive system can:

1. maintain multiple genuinely different perspectives on the same complete problem;
2. extract useful knowledge from paths that may be incomplete or globally wrong;
3. translate and combine knowledge across different internal representations;
4. construct and verify solutions that exceed every individual member;
5. eventually improve the machinery through which the collective thinks, learns, verifies, and evolves.

The long-term direction is artificial superintelligence. The immediate work is narrower: formulate falsifiable claims, construct controlled experiments, and reject mechanisms that do not earn further scale.

## 2. What this project is not

This is not primarily:

- a chatbot or assistant project;
- a product roadmap;
- a conventional multi-agent wrapper around existing language models;
- an attempt to maximize a single benchmark score;
- a claim that more agents automatically create more intelligence;
- a commitment to transformers, identical architectures, natural-language communication, or any fixed population size.

A useful capability may appear in a particular snapshot. Such a snapshot may be copied, frozen, independently validated, and used by humans. That possibility must not redirect the main lineage toward user satisfaction, market demand, latency, or short-term stability.

## 3. Two primary research claims

### Claim P — plural cognition

A population of genuinely different cognitive processes can produce a verified collective solution whose necessary knowledge was not present in any one complete individual answer.

The proposed mechanism is:

```text
independent paths
→ structured knowledge extraction
→ cross-representation translation
→ contradiction and evidence analysis
→ synthesis of new hypotheses
→ adversarial verification
→ one final result
```

This must outperform simpler alternatives such as majority vote, best-of-N selection, repeated sampling from one weight set, and ordinary debate.

### Claim E — open-ended self-improvement

A qualified collective system can generate isolated descendants, evaluate them honestly across multiple time horizons, preserve useful alternative lineages, and improve not only task performance but the process that discovers future improvements.

Claim E is not part of Version 0. It should be tested only after Claim P has produced a reproducible signal.

## 4. Stable principles

These principles express the research objective. They are not mandates for one implementation.

### 4.1 Preserve functional plurality

The system should permit different hypotheses, predictions, methods, representations, and error patterns. Different weights are one provisional mechanism. Functional diversity matters more than numerical weight difference.

### 4.2 Delay convergence

Do not optimize every member to immediately agree. Divergence is useful until evidence, constraints, or successful synthesis justify convergence.

### 4.3 Evaluate claims rather than popularity

A hypothesis supported by one member can defeat a majority if it explains more evidence, survives stronger tests, or makes a decisive verified prediction.

### 4.4 Preserve useful parts of failed paths

A globally wrong path may still contain a correct counterexample, variable, causal relation, boundary condition, measurement warning, or experimental design.

### 4.5 Require synthesis, not only selection

The strongest collective result is not necessarily one submitted candidate. The system should be able to construct a new hypothesis from compatible parts of multiple paths and then test that new hypothesis as an independent candidate.

### 4.6 Confront external reality

Internal agreement is not proof. Where possible, conclusions should face deterministic checks, execution, simulation, measurement, held-out prediction, or independently reproducible evidence.

### 4.7 Preserve negative evidence

Rejected mechanisms, failed candidates, null results, and contradictory experiments remain part of the scientific record. The value of an experiment is uncertainty removed, not whether it supports the preferred theory.

### 4.8 Be architecture-agnostic and process-strict

The system may eventually replace identical models with heterogeneous models, symbolic components, simulators, causal systems, novel neural structures, or mechanisms not anticipated here. The promotion and evaluation process remains strict regardless of architecture.

## 5. Provisional seed assumptions

The first experiment will provisionally use:

- a small population;
- identical model topology;
- different independently learned weights;
- the same full problem and evidence for every member;
- private reasoning state;
- a structured shared workspace;
- fixed rounds of divergence, extraction, synthesis, and verification;
- deterministic ground truth or evaluators where possible.

These are experimental controls, not permanent constitutional requirements.

## 6. Scientific standard

Every major claim should have:

- a precise null hypothesis;
- matched-compute controls;
- repeated runs across seeds;
- held-out task families;
- explicit stopping and success criteria defined before evaluation;
- complete reporting of positive, negative, null, and contradictory results;
- traceability from final conclusions to contributing evidence and operations;
- enough detail for independent reproduction.

The architecture must earn the right to become larger.

## 7. Key distinctions

### One AI versus one perspective

The intended system is one persistent artificial intelligence at the system level, while internally maintaining multiple cognitive perspectives. One identity does not require one monolithic representation.

### Different answers versus different paths

The purpose of the population is not to return many final answers. It is to create diverse paths whose useful knowledge can be extracted, recombined, and eliminated until one justified result remains.

### Information exchange versus emergent synthesis

Passing complementary facts between members is useful but insufficient as proof of collective emergence. The stronger target is a valid relation or solution created during integration that was absent from every complete initial answer.

### Immediate performance versus developmental potential

A candidate may regress during adaptation and later exceed its parent. Evaluation must distinguish transition cost, mature performance, learning slope, and descendant-generating potential.

## 8. Long-term success condition

The long-term threshold is not merely that the system edits its own source code or improves on one benchmark. It is that the collective repeatedly discovers better ways to generate, distribute, combine, test, and improve intelligence across unfamiliar domains, while its claims remain empirically auditable.
