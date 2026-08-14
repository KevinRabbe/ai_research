# Capable Model Bakeoff Protocol

## Status

Research snapshot: **2026-08-11**.

This document freezes the selection logic for the first capable heterogeneous population before any local bakeoff result exists.

It does not declare four permanent minds. It defines how candidates are measured and how the first population is selected from a larger pool.

## 1. Objective

The first population should not simply contain the four highest standalone benchmark scores.

The population should contain:

```text
one strongest individual anchor
+
three additional capable minds that increase solved-task coverage
```

The decisive selection quantity is therefore complementarity on a frozen selection split.

For candidate set `S`, define:

```text
B(S) = strongest individual score in S
O(S) = oracle-union score of S
H(S) = O(S) - B(S)
```

`O(S)` is the fraction of tasks solved by at least one constituent.

It represents selection headroom, not an upper bound on constructive synthesis.

## 2. Why the strongest candidate must remain in the population

Without this rule, population selection could choose four weaker but complementary models, lowering the strongest-member baseline and making later plural uplift artificially easier to demonstrate.

The initial selection therefore requires the strongest eligible individual to be one of the four minds.

This keeps the later question honest:

> Can the collective beat the strongest capable model we actually had available?

## 3. Deterministic population-selection rule

The initial rule is:

1. evaluate every candidate on exactly the same ordered **selection** tasks;
2. exclude candidates below the frozen operational-validity threshold;
3. identify the strongest eligible individual by solved-task count;
4. break strongest-individual ties by lower accelerator time, then lower token use, then candidate ID;
5. enumerate every four-candidate coalition containing that strongest candidate;
6. maximize oracle-union solved-task count;
7. break ties by higher summed individual solved-task counts;
8. then lower total accelerator time;
9. then lexicographic candidate IDs.

Pairwise error correlation is reported but deliberately not used as a hard tie-breaker because correlation is undefined when one model has a constant error vector.

The initial operational-validity threshold is:

```text
95%
```

A failed model load, malformed unusable result, backend failure, or evaluation failure is not silently removed from the denominator.

## 4. Evaluation splits

Use three distinct roles:

### Calibration

Used to build and calibrate task difficulty, evaluator correctness, output parsing, and resource ceilings.

Calibration outcomes may change the protocol.

They cannot qualify plural cognition.

### Selection

Used to compare candidate minds and choose the first four-member population.

Population selection may inspect selection results.

### Confirmation

Protected held-out tasks.

These are not used to select candidate models, tune prompts, choose synthesis rules, or repair the population.

The confirmation split is opened only after the relevant candidate system has been frozen.

## 5. Initial raw-mind condition

The candidate bakeoff intentionally begins before the powerful harness.

Each raw mind receives the same content-addressed solver-visible task package and its own frozen backend-specific protocol.

Initial raw-mind budgets should default to:

```text
one primary inference call
no cross-mind communication
no hidden evaluator access
no automatic retries unless predeclared
no mutable memory carried between tasks
no plural synthesis
```

A later harness condition may use repository tools, retrieval, subagents, memory, retries, and long-running execution, but its pre-harness input artifact remains preserved.

This prevents harness capability from being mislabeled as raw model capability.

## 6. Task design for the first coding bakeoff

The first task family should be small deterministic repository-repair problems rather than public leaderboard tasks alone.

Each task should bind:

```text
task ID
task family
repository snapshot hash
solver-visible prompt hash
optional public-test hash
language
visible byte ceiling
protected evaluator identity
protected-test hash
resource budget
```

The raw condition should keep repositories small enough that a standardized solver-visible bundle can be provided without requiring a full agentic retrieval harness.

Later phases deliberately increase repository size and require programmatic context management.

Useful task categories include:

```text
localized bug repair
multi-file behavioral bug
API contract mismatch
state-management bug
algorithmic correctness bug
edge-case regression
test repair where tests are themselves incorrect
small refactor preserving behavior
performance bug with deterministic threshold
```

Protected tests must distinguish plausible patches from actual repairs.

## 7. Initial candidate research snapshot

The following candidates are not preselected winners. They are an intentionally heterogeneous starting pool.

### Qwen3.5-9B

Role:

```text
current compact Qwen general/reasoning/agent candidate
```

The official Qwen/Hugging Face material describes Qwen3.5 as a natively multimodal family using a hybrid stack of Gated DeltaNet linear-attention layers and full attention. The 9B checkpoint is Apache-2.0 and is supported by current Transformers/vLLM-style inference stacks.

Primary sources:

- https://huggingface.co/Qwen/Qwen3.5-9B
- https://huggingface.co/docs/transformers/en/model_doc/qwen3_5

### Gemma 4 12B Unified

Role:

```text
independent Google DeepMind dense lineage
```

Google's June 2026 Gemma 4 model card lists the 12B Unified model at 11.95B parameters with a 256K context window and native function-calling/coding/agentic support. Google's published evaluation reports 72.0% on LiveCodeBench v6 for Gemma 4 12B Unified.

Primary sources:

- https://ai.google.dev/gemma/docs/core/model_card_4
- https://ai.google.dev/gemma/docs/releases

### Moonlight-16B-A3B-Instruct

Role:

```text
Moonshot MoE lineage that is small enough to investigate locally
```

Moonshot describes Moonlight as a 16B-total / 3B-active Mixture-of-Experts model trained with 5.7T tokens using the Muon optimizer. The instruction model has an 8K context window.

Primary source:

- https://huggingface.co/moonshotai/Moonlight-16B-A3B-Instruct

This is not Kimi K2.7 itself. It is a smaller Moonshot model that gives the local experiment an independent MoE lineage.

### DeepSeek-Coder-V2-Lite-Instruct

Role:

```text
coding-specialized DeepSeek MoE lineage
```

DeepSeek publishes this model as 16B total / 2.4B active with a 128K context window. It was further pretrained for code and mathematics and is materially different from a dense general-purpose candidate.

Primary source:

- https://huggingface.co/deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct

### Qwen2.5-Coder-14B-Instruct

Role:

```text
coding-specialized dense control inside the Qwen lineage
```

The official model card lists 14.7B parameters and a 131,072-token context window. Qwen describes the Coder series as trained on 5.5T code-related tokens and intended for code generation, reasoning, fixing, and code-agent applications.

Primary sources:

- https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct
- https://qwenlm.github.io/blog/qwen2.5-coder-family/

This candidate is useful even if a newer Qwen model is stronger because it tests specialization versus newer general capability.

### Devstral Small 2 24B

Role:

```text
agentic software-engineering specialist / hardware-borderline candidate
```

Mistral publishes Devstral Small 2 as a 24B coding-agent model with 256K context and Apache-2.0 weights. Mistral states that it is intended for local consumer hardware and reports 68.0% on SWE-bench Verified.

Primary sources:

- https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512
- https://mistral.ai/news/devstral-2-vibe-cli/

Mistral specifically cites a single RTX 4090 / 32GB-class Mac as local targets. On the project's 16GB RTX 4060 Ti, this is therefore a **borderline/offload candidate**, not assumed to be fully GPU-resident.

## 8. Large remote reference models

Very large models should not be forced into the local population merely because they are interesting.

They can later serve as optional reference minds or capability ceilings through APIs.

Examples from the current research snapshot include:

### Kimi K2.7 Code

Moonshot's current K2.7 Code is a very large coding/agent model in the Kimi K2 family. The official model card describes native INT4 deployment and recommends Kimi Code for its agent framework, but the underlying model remains in the ~1.1T-total-parameter class and is not a sensible local 16GB-resident target.

Primary source:

- https://huggingface.co/moonshotai/Kimi-K2.7-Code

### DeepSeek V4 API family

DeepSeek's current API documentation exposes `deepseek-v4-flash` and `deepseek-v4-pro`, both with thinking/non-thinking modes and tool calling. These are useful remote references while the local population remains hardware-bounded.

Primary source:

- https://api-docs.deepseek.com/quick_start/pricing/

### Proprietary frontier coding controls

OpenAI Codex and Anthropic Claude Code/Claude models can later be used as external ceiling controls if access and cost justify it. They must never be mixed into a supposedly local matched-resource result without being labeled as remote proprietary conditions.

Primary sources:

- https://openai.com/codex/
- https://openai.com/index/introducing-gpt-5-3-codex/
- https://www.anthropic.com/product/claude-code
- https://www.anthropic.com/claude/opus

## 9. Hardware interpretation

For local models, total parameter count determines weight storage even when an MoE activates only a small subset per token.

At an idealized four bits per parameter, raw weight lower bounds are approximately:

```text
9B   -> 4.5 GB
12B  -> 6.0 GB
14.7B -> 7.35 GB
16B  -> 8.0 GB
24B  -> 12.0 GB
```

These are not actual runtime footprints.

Real deployments additionally require quantization metadata, non-quantized tensors, runtime buffers, KV cache, context state, and framework overhead.

Therefore no candidate is declared compatible with the 16GB GPU until measured on the exact machine.

## 10. Local preflight before benchmark execution

For each local candidate/configuration measure:

```text
exact model revision
exact quantization artifact/revision
backend and backend version
successful load
time to first token
steady generation throughput
peak VRAM
peak system RAM
context length actually tested
output stability
one short coding smoke task
```

A model may qualify through partial CPU offload, but that execution mode becomes part of its immutable producer configuration and resource ledger.

Do not compare an offloaded model against a fully resident model while pretending the hardware conditions are identical.

## 11. Population selection is development-only

The candidate-selection algorithm may use only the selection split.

The protected confirmation split must not be queried while deciding:

```text
which four models to use
which quantization to use
which model prompt to use
which synthesis rule to use
whether a weak candidate should be swapped out
```

If the selected four later perform poorly on confirmation tasks, preserve that result.

Do not reopen confirmation and choose another four-model population post hoc.

## 12. First population controls after selection

Once the first four minds are frozen, compare:

```text
A. strongest constituent, one attempt
B. strongest constituent with matched extra inference budget
C. strongest constituent x4 isolated paths
D. four heterogeneous minds, independent outputs only
E. heterogeneous minds + selection-only aggregator
F. heterogeneous minds + constructive synthesis
```

Only after these are established add:

```text
G. harness-assisted collective
H. adversarial review / verification
I. continually refined harness
```

Every stage preserves its predecessor artifact.

## 13. Interpretation

A useful first population need not contain four equally strong models.

A model may earn a mind slot because it supplies rare correct repairs, catches failures that the strongest model misses, or contributes unusually valuable evidence to later synthesis.

Therefore:

```text
standalone capability != collective marginal value
```

The first four minds are selected as a population, not as four independent leaderboard entries.
