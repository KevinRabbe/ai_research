# Adjacent Research and Primary Sources

This project combines ideas that have usually been studied separately. None of the sources below establishes the complete proposed architecture. They provide evidence, mechanisms, controls, or warnings relevant to specific parts of the research program.

## Representation convergence and multiple views

### Huh et al. — The Platonic Representation Hypothesis (2024)

https://arxiv.org/abs/2405.07987

Studies whether increasingly capable vision and language models organize data in more similar relational geometries. Relevant to the possibility that independently learned representations can preserve shared external structure without sharing coordinates or modalities.

The project treats strong universal convergence as a hypothesis, not an established guarantee. Plural cognition also values complementary differences that do not converge.

### Li, Yang, and Zhang — A Survey of Multi-View Representation Learning (2016)

https://arxiv.org/abs/1610.01206

Reviews representation alignment and fusion across multiple views. Relevant to the distinction between consensus structure shared across perspectives and complementary information unique to one view.

## Diverse learned functions and ensembles

### Fort, Hu, and Lakshminarayanan — Deep Ensembles: A Loss Landscape Perspective (2019)

https://arxiv.org/abs/1912.02757

Provides evidence that independent random initializations can explore different modes in function space. Relevant to the Version 0 assumption that identical architectures with independently learned weights may produce less-correlated cognitive behaviour.

This does not prove that different weights create useful high-level reasoning diversity; Version 0 must measure that directly.

### Abe et al. — Deep Ensembles Work, But Are They Necessary? (2022)

https://arxiv.org/abs/2202.06985

Shows that some ensemble benefits can be replicated by a larger single model. This is an important control argument: the proposed population must be compared against matched monolithic scaling rather than assuming that any ensemble gain implies a new architecture of intelligence.

## Multiple reasoning paths and test-time search

### Wang et al. — Self-Consistency Improves Chain of Thought Reasoning in Language Models (2022)

https://arxiv.org/abs/2203.11171

Samples multiple reasoning paths and aggregates the resulting answers. Relevant as a baseline, not as the target architecture. The project must show that structured synthesis exceeds majority-style marginalization over existing answers.

### Yao et al. — Tree of Thoughts: Deliberate Problem Solving with Large Language Models (2023)

https://arxiv.org/abs/2305.10601

Explores multiple intermediate reasoning states with evaluation, lookahead, and backtracking. Relevant to divergence, pruning, and search. The proposed population differs by emphasizing separately learned perspectives and synthesis across their extracted knowledge.

### Snell et al. — Scaling LLM Test-Time Compute Optimally Can Be More Effective than Scaling Model Parameters (2024)

https://arxiv.org/abs/2408.03314

Shows that the usefulness of inference-time computation depends strongly on task difficulty and that adaptive allocation can outperform fixed best-of-N strategies in the evaluated settings. Relevant to the later movable-compute allocator.

### Zhang et al. — Scaling LLM Inference with Optimized Sample Compute Allocation (2024)

https://arxiv.org/abs/2410.22480

Studies learned allocation across sampling configurations under bounded compute. Relevant to future experiments on deciding where additional cognitive paths are most valuable.

## Shared workspaces and modular coordination

### Goyal et al. — Coordination Among Neural Modules Through a Shared Global Workspace (2021/2022)

https://arxiv.org/abs/2103.01197

Studies communication among specialized modules through a shared bandwidth-limited workspace. Relevant to the proposed structured workspace, competition for publication, and the possibility that restricted communication can preserve specialization.

The proposed system operates at a higher level than the modules in this work and must test whether a workspace helps complete cognitive perspectives rather than only neural submodules.

## Verification

### Lightman et al. — Let’s Verify Step by Step (2023)

https://arxiv.org/abs/2305.20050

Compares process supervision with outcome supervision on mathematical reasoning and reports stronger results for process supervision in the studied setting. Relevant to evaluating claims, dependencies, and intermediate reasoning components instead of scoring only final answers.

### Execution-based program selection

Code generation research has repeatedly shown that executable tests can be stronger selectors than model confidence alone. Version 0 should prefer deterministic task verifiers so that synthesis quality is not confounded with an unreliable language-model judge.

## Conditional computation and mixture of experts

### Shazeer et al. — Outrageously Large Neural Networks: The Sparsely-Gated Mixture-of-Experts Layer (2017)

https://arxiv.org/abs/1701.06538

Demonstrates conditional activation of expert subnetworks. Relevant as an efficiency and routing precedent.

Conventional MoE is not equivalent to the proposed population intelligence: its experts are usually local neural components selected per input or token, not complete independently learned perspectives that construct and challenge hypotheses.

## Open-ended self-improvement

### Zhang et al. — Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents (2025)

https://arxiv.org/abs/2505.22954

Maintains an archive of coding-agent variants, modifies agent code, empirically evaluates descendants, and explores multiple branches. Relevant to immutable lineages, empirical promotion, archive-based search, and preservation of stepping stones.

Its reported experiments improve agent scaffolding around frozen foundation models. They do not establish autonomous evolution of model weights, complete cognitive architectures, or general recursive self-improvement.

## How these sources relate to the project

```text
representation convergence and multi-view learning
→ different internal worlds may preserve shared structure

deep ensembles
→ independently learned weights may produce functional diversity

self-consistency and tree search
→ multiple paths can improve inference

global workspace
→ independent components may coordinate through limited shared state

process verification
→ reasoning components can be checked before final integration

test-time allocation
→ compute should move toward tasks and hypotheses where it is valuable

Darwin Gödel Machine
→ alternative descendants and stepping stones can be preserved empirically
```

The unproven step is the central one:

> Can these principles be integrated into one system that creates verified collective knowledge beyond every constituent and later improves the machinery that produces such knowledge?

That is the purpose of this repository.
