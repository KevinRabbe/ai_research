# Reasoning, Mathematics, and Search Design for Plural Cognition

## 1. Purpose

This document translates adjacent research on mathematical reasoning, process verification, program synthesis, ensemble diversity, search, active learning, and latent reasoning into concrete design decisions for this repository.

The immediate question is not whether a model can produce a persuasive chain of thought. It is:

> What internal representation and search process make it possible to combine partial knowledge from several learned minds into a new, exactly verified solution?

The strongest current answer is a neuro-symbolic design:

```text
learned minds propose structured hypotheses and useful fragments
→ a provenance-preserving graph stores them
→ bounded symbolic search composes and repairs candidates
→ visible evidence checks every step
→ hidden exact evaluation scores the fixed final result
```

Natural-language reasoning chains may be useful as temporary training or diagnostic material, but they must not be treated as ground truth.

## 2. Main conclusions

### 2.1 Do not make free-form chain of thought the central representation

Research on process supervision shows that intermediate reasoning can be valuable when steps are independently checkable. At the same time, chain-of-thought faithfulness research shows that verbalized reasoning is not guaranteed to describe the actual causal computation of a model.

Therefore Version 1 should use:

- exact programs;
- canonical fragments;
- explicit support and contradiction links;
- testable predictions;
- counterexamples;
- provenance;
- exact visible verification.

It should not depend on long natural-language explanations.

The rule is:

```text
reasoning text may propose a claim
verification determines whether the claim enters collective knowledge
```

### 2.2 Use learned proposal plus symbolic verification

DeepCoder and AlphaGeometry demonstrate a recurring successful pattern:

```text
neural model narrows or guides a large search space
+
formal or symbolic engine establishes correctness
```

For this project, each mind should propose:

- complete candidate mechanisms;
- subexpressions;
- likely operators;
- boundary conditions;
- counterexamples;
- repairs to another candidate.

The deterministic synthesizer should perform bounded composition and repair. It must never enumerate the unrestricted grammar or inspect hidden ground truth.

### 2.3 Replace a single reasoning chain with a hypothesis graph

A chain commits to one sequence of steps. Plural cognition requires branching, recombination, contradiction, and backtracking.

Use a directed typed graph or hypergraph:

```text
node types
- evidence case
- intervention
- atomic fragment
- composite fragment
- complete candidate
- counterexample
- uncertainty

edge types
- supports
- contradicts
- derived-from
- part-of
- equivalent-to
- repairs
- predicts
```

A hyperedge is useful when a conclusion requires several premises jointly.

The graph is not merely a transcript. It is the current collective model of the problem.

### 2.4 Measure functional diversity, not textual diversity

Different tokens or explanations do not establish different cognition.

For Boolean Mechanism Worlds, useful diversity can be measured exactly through:

1. normalized truth-table distance;
2. pairwise error correlation;
3. unique valid fragment coverage;
4. unique counterexample discovery;
5. operator and clause recovery differences;
6. minority-rescue events;
7. contribution to final synthesis.

For two candidate functions `f` and `g` over assignment set `X`, define semantic distance:

\[
d_{sem}(f,g)=\frac{1}{|X|}\sum_{x\in X}\mathbf{1}[f(x)\neq g(x)]
\]

This should be preferred over edit distance between generated token sequences.

Diversity alone is not sufficient. The relevant quantity is useful diversity:

\[
D_{useful}=D_{functional}\times Q_{fragment}
\]

where `Q_fragment` measures whether disagreements contain valid clauses, predictions, or counterexamples.

### 2.5 Evidence must outrank consensus

Recent multi-agent research reports that unconstrained teams can underuse their strongest member and converge through compromise. That is directly opposed to this project's goal.

The synthesizer must not use vote count as the primary truth criterion.

Use the priority order:

```text
exact contradiction or proof
> verified counterexample
> visible-evidence coverage
> calibrated prediction
> model confidence
> number of supporting minds
```

A minority fragment that eliminates a popular hypothesis must survive.

### 2.6 Use exact cooperative credit while the population is small

For four minds, all subsets can be evaluated cheaply:

\[
2^4=16
\]

This makes exact Shapley contribution practical for Version 1.

For mind `i`, with collective score function `v(S)`, define:

\[
\phi_i=\sum_{S\subseteq N\setminus\{i\}}
\frac{|S|!(|N|-|S|-1)!}{|N|!}
\left[v(S\cup\{i\})-v(S)\right]
\]

Use both:

- leave-one-source-out necessity;
- exact Shapley contribution across all sixteen subsets.

They answer different questions:

- removal asks whether a source was necessary in the realized synthesis;
- Shapley asks its average marginal value across possible coalitions.

A claimed collective result should not rely only on aggregate accuracy.

### 2.7 Maintain a version space of surviving hypotheses

For hypothesis class `H` and visible evidence `D`, define:

\[
V(D)=\{h\in H:\forall(x,y)\in D, h(x)=y\}
\]

The current V1.0 generator already ensures one target is identifiable relative to the hidden bounded catalog. The model-facing system must not see that catalog, but the synthesis process can maintain a local version space containing only member-proposed and boundedly composed candidates.

Do not force one candidate while several remain visibly consistent. Preserve the surviving set and its unresolved distinctions.

### 2.8 Use disagreement to choose future experiments

Later versions should be able to request an intervention that maximally separates surviving hypotheses.

A simple finite version-space acquisition rule is:

\[
x^*=\arg\max_x H\left(\{h(x):h\in V(D)\}\right)
\]

For binary outputs, this prefers assignments near a 50/50 split among surviving hypotheses.

A more explicit expected information-gain rule is:

\[
IG(x)=H(H\mid D)-\mathbb{E}_{y}[H(H\mid D\cup\{(x,y)\})]
\]

This is not needed for the initial static V1 proof, because every member receives the same fixed complete evidence. It is a strong candidate for a later active-science phase.

### 2.9 Latent reasoning is promising but should be a later ablation

Coconut reports that continuous latent reasoning can preserve multiple possible continuations and help with backtracking. Quiet-STaR and STaR show that models can learn useful internal rationales through self-generated supervision.

These ideas are relevant, but adding them now would confound the first test.

Version 1 must first establish whether independently learned models plus explicit structured synthesis work.

A later comparison should test:

```text
explicit symbolic fragments
versus
natural-language chains
versus
continuous latent reasoning states
versus
hybrid latent proposal plus symbolic verification
```

The hidden exact evaluator remains unchanged across those conditions.

### 2.10 Learn reusable abstractions only after the first signal

DreamCoder shows how a system can learn reusable symbolic abstractions and a search-guiding model together.

For this project, a later population could discover macros such as:

```text
XOR(A,B)
IMPLIES(A,B)
UNLESS(A,B)
MAJORITY(A,B,C)
GUARDED_CLAUSE(condition, clause)
```

The first V1 grammar should remain fixed. Learned abstraction changes the hypothesis language and therefore belongs after the central plural-synthesis mechanism is proven.

## 3. Revised V1 cognitive packet

The one-member learning preflight may continue to predict one canonical complete program. Population experiments should add a structured packet rather than replacing that exact output.

Proposed packet:

```text
member_id
complete_candidate
fragments[]
  fragment_id
  canonical_expression
  role
  supporting_case_ids[]
  contradicting_case_ids[]
  predicted_outputs[]
  confidence
counterexamples[]
uncertainties[]
```

Allowed fragment roles:

```text
atom
clause
condition
exception
repair
counterexample
alternative
```

Every packet is immutable after publication and receives a cryptographic hash.

## 4. Revised synthesis process

### Stage 1 — normalize

- parse all complete programs and fragments;
- reject malformed or out-of-task variables;
- normalize expressions;
- merge exact structural duplicates;
- link semantically equivalent candidates without losing provenance.

### Stage 2 — verify fragments

For each fragment, evaluate the claims it makes against visible evidence.

A fragment may be:

- supported;
- contradicted;
- not directly decidable from visible evidence.

Unsupported does not automatically mean false. Contradicted means it cannot enter a candidate without an explicit repair or scope restriction.

### Stage 3 — construct the graph

Store fragments, candidates, evidence, contradictions, and provenance as a typed graph.

### Stage 4 — bounded composition

Permitted operators:

- substitute one member fragment into another candidate;
- add a member-proposed condition;
- attach a member-proposed exception;
- replace a contradicted subexpression;
- combine two compatible clauses with an operator proposed by at least one member.

Prohibited in V1:

- unrestricted enumeration of all grammar programs;
- hidden evaluator access;
- arbitrary new atoms absent from all packets;
- an unrestricted language model judge.

### Stage 5 — visible verification

Rank surviving candidates by a tuple rather than a single opaque score:

```text
visible consistency
number of contradicted claims
visible coverage
verified fragment count
complexity tie-breaker
provenance breadth
```

Complexity may break ties but must not override evidence.

### Stage 6 — freeze and evaluate

Freeze the final candidate before hidden evaluation.

Hidden evaluation may score the candidate but must not feed information back into the synthesis of the same task.

## 5. Required new metrics

### 5.1 Semantic diversity matrix

For every pair of members, store normalized truth-table distance and error correlation.

### 5.2 Fragment precision and recall

Against the hidden target, measure which proposed fragments are semantically valid components of at least one minimal or normalized target expression.

Because Boolean expressions can have many equivalent decompositions, this metric must be defined carefully. Initial V1 may use bounded structural families and exact semantic substitution tests rather than string matching.

### 5.3 Novel composition

A synthesis is novel when:

- the final complete semantic function is absent from every initial complete candidate;
- at least one required combination relation is absent from every single packet;
- all of its atomic material is traceable to bounded permitted sources or explicit deterministic repair.

### 5.4 Multi-source necessity

Use leave-one-source-out evaluation and exact Shapley credit for four-member populations.

### 5.5 Minority rescue

Count tasks where:

- a majority supports an incorrect candidate family;
- a minority provides a valid counterexample or necessary fragment;
- synthesis uses that minority contribution;
- the final result becomes correct.

### 5.6 Search efficiency

Record:

- number of graph nodes;
- number of generated composites;
- verifier calls;
- candidates pruned by contradiction;
- candidates pruned by equivalence;
- final search depth;
- wall-clock synthesis cost.

This prevents hidden brute force from masquerading as cognition.

## 6. New controlled ablations

Add these after the individual preflight:

```text
A. complete candidate only
B. complete candidate + proof-carrying fragments
C. fragments + selection only
D. fragments + graph synthesis
E. graph synthesis without provenance
F. graph synthesis without fragment verification
G. linear chain synthesis instead of graph synthesis
H. same-weight packets with the same graph synthesizer
```

The important comparison is:

\[
D>B>A
\]

under matched generation and verifier budgets.

If `B > A` but `D = B`, structured fragments help but graph synthesis does not.

If `D > B` but the gain disappears without hidden brute force controls, the synthesizer is not scientifically valid.

## 7. GPU-independent work that can proceed now

The following work does not require the RTX 4060 Ti:

1. immutable run and checkpoint manifest schemas;
2. deterministic procedural training-stream contracts;
3. dataset split and seed manifests;
4. hypothesis-packet dataclasses and strict codecs;
5. graph and provenance schemas;
6. semantic diversity metrics;
7. exact four-member Shapley evaluator;
8. source-removal ablation;
9. bounded composition operators;
10. CPU unit and property tests;
11. preregistration of V1 success thresholds.

Do not run CUDA throughput measurement while another training job occupies the GPU. Shared GPU load would make throughput and peak-memory results scientifically invalid even if the benchmark technically completes.

## 8. Recommended implementation order

```text
1. run/checkpoint manifests
2. deterministic training-stream manifest
3. population hypothesis packet schema
4. semantic diversity metrics
5. exact leave-one-out and Shapley contribution code
6. provenance graph
7. bounded composition operators
8. visible-only fragment verifier
9. synthesis ablations
10. CUDA preflight when the GPU becomes free
11. one-member learning curves
12. four-member population experiment
```

## 9. Research sources

### Verifiable reasoning and chain-of-thought limits

- Lightman et al., *Let's Verify Step by Step*, arXiv:2305.20050.
- Kim et al., *Correct Answers from Sound Reasoning: Verifiable Process Supervision for Language Models*, arXiv:2605.12519.
- Tutek et al., *Measuring Chain of Thought Faithfulness by Unlearning Reasoning Steps*, EMNLP 2025.
- Young, *Lie to Me: How Faithful Is Chain-of-Thought Reasoning in Reasoning Models?*, arXiv:2603.22582.

### Structured and latent reasoning

- Yao et al., *Tree of Thoughts*, arXiv:2305.10601.
- Lei et al., *Graph of Thought*, arXiv:2308.08614.
- Hao et al., *Training Large Language Models to Reason in a Continuous Latent Space*, arXiv:2412.06769.
- Zelikman et al., *STaR*, arXiv:2203.14465.
- Zelikman et al., *Quiet-STaR*, arXiv:2403.09629.

### Neuro-symbolic search and program induction

- Balog et al., *DeepCoder: Learning to Write Programs*, arXiv:1611.01989.
- Trinh et al., *Solving Olympiad Geometry without Human Demonstrations*, Nature 2024.
- Chervonyi et al., *Gold-medalist Performance in Solving Olympiad Geometry with AlphaGeometry2*, arXiv:2502.03544.
- Ellis et al., *DreamCoder*, arXiv:2006.08381.
- de Moura and Bjørner, *Z3: An Efficient SMT Solver*, TACAS 2008.

### Diversity, teams, and credit assignment

- Ortega et al., *Diversity and Generalization in Neural Network Ensembles*, AISTATS 2022.
- Pappu et al., *Multi-Agent Teams Hold Experts Back*, arXiv:2602.01011.
- Rozemberczki et al., *The Shapley Value in Machine Learning*, arXiv:2202.05594.

### Version spaces and active experimentation

- Cortes et al., *Active Learning with Disagreement Graphs*, ICML 2019.
- Sloman et al., *Bayesian Active Learning in the Presence of Nuisance Parameters*, UAI 2024.

## 10. Decision

The project should not become a collection of debating language models.

The stronger architecture is:

\[
\boxed{
\text{plural learned proposal}
+\text{proof-carrying fragments}
+\text{hypothesis graph}
+\text{bounded symbolic synthesis}
+\text{exact verification}
}
\]

Version 1 should prove that this mechanism creates correct new knowledge beyond every individual member and beyond simpler sampling, voting, selection, and linear-chain controls.
