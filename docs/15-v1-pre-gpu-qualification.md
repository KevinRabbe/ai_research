# V1 Pre-GPU Qualification

## Qualified state

The complete GPU-independent Version 1 experiment harness is qualified on:

```text
exact executable head: aef3044a0fd1e4f0da3caeb415ac8808dc380990
GitHub Actions:        CI run 346 passed
repository tests:      146 passed
```

This is a software, mathematical, and experimental-protocol qualification. It is not a learned-model or plural-cognition result.

## What is ready before the GPU becomes available

### Exact task and evaluator

- deterministic Boolean Mechanism Worlds;
- public evidence separated from hidden target state;
- exact semantic equivalence and distance;
- deterministic interventions and counterexamples;
- hidden evaluation applied only after outputs are fixed;
- ambiguous task rejection.

### Learner family

- fixed 75-token symbolic vocabulary;
- strict task and mechanism codecs;
- answer-only causal labels;
- PC-4M, PC-10M, and PC-18M exact parameter configurations;
- CPU forward/backward qualification;
- strict greedy generation;
- reproducible sampled generation.

### Data and execution integrity

- index-addressed deterministic training examples;
- content-addressed dataset shards;
- strict canonical manifest parsing;
- run, screening-plan, and execution manifests;
- data configuration bound to the run data seed;
- zero-based contiguous shard ranges;
- exact matched 32,768-token optimizer geometry;
- measured CUDA-preflight resolution;
- complete shard verification before CUDA allocation.

### Training and checkpoints

- fail-closed CUDA environment checks;
- exact microbatch and gradient accumulation;
- token-indexed learning-rate schedule;
- finite loss and gradient checks;
- gradient clipping;
- atomic progress and checkpoint writes;
- complete RNG state preservation;
- resume bound to the exact execution and dataset hashes;
- binary checkpoint hash sidecars.

### Individual evaluation and model selection

- fixed validation rows;
- exact parse, visible, semantic, and exact-accuracy metrics;
- evaluation artifacts bound to checkpoint, execution, generation protocol, and validation shards;
- six-run scale matrix;
- smallest-model selection under the frozen 95% parse and 20%–70% exact-accuracy boundaries;
- refusal to make a post-hoc model choice if no scale qualifies.

### Population experiment

- two selected-scale screening checkpoints reused;
- two additional initialization seeds added automatically;
- deterministic complete-answer selection;
- deterministic complete-answer majority voting;
- verified-fragment selection;
- verified and unverified bounded synthesis;
- visible-only proof auditing;
- typed provenance and derivation graph;
- exact semantic diversity metrics;
- all 16 coalitions for four members;
- leave-one-out necessity and exact Shapley attribution;
- strong synthesis event classification.

### Same-weight control and final gate

- one predeclared checkpoint sampled under seeds 301–304;
- explicit `same-checkpoint-sampled` condition classification;
- explicit `different-checkpoint-greedy` primary classification;
- validation-row and shard equality checks;
- 95% minimum control coverage;
- paired bootstrap interval for primary-minus-control synthesis accuracy;
- paired bootstrap interval for primary-minus-control synthesis gain;
- canonical final condition-comparison artifact.

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

The exact PowerShell sequence is in `docs/13-v1-execution-and-analysis-procedure.md`.

## What still requires the RTX 4060 Ti

```text
measured CUDA preflight
→ six 10M-token screening runs
→ six greedy checkpoint evaluations
→ automatic scale selection
→ two additional selected-scale runs
→ four-member greedy population evaluation
→ four same-checkpoint sampled evaluations
→ paired condition comparison
```

## Claims not yet supported

No current artifact establishes:

- actual RTX 4060 Ti throughput or peak VRAM;
- learning success at any scale;
- useful different-weight functional diversity;
- novel synthesis from learned members;
- advantage over same-weight sampling;
- general intelligence;
- artificial superintelligence;
- recursive self-improvement.

## Qualification boundary

The strongest justified statement is:

> Everything needed to execute, resume, evaluate, control, attribute, and statistically compare the first Version 1 experiment is implemented and CPU-qualified. The remaining unknowns are empirical measurements and learned behavior.
