# Population Cognitive Engine

## 1. Seed architecture

The first proposed implementation is a small population of structurally identical neural models with independently learned weights.

For member \(i\):

\[
h_i^{t+1} = F_{W_i}(h_i^t, x, b^t)
\]

where:

- \(W_i\) is the member's private learned weight set;
- \(h_i^t\) is its private cognitive state;
- \(x\) is the complete task and available evidence;
- \(b^t\) is selected information from the shared workspace.

The members are components of one larger cognitive system. No individual member is treated as the final intelligence.

## 2. Matrix execution with different weights

Identical topology does not require identical weights. For one layer:

\[
Y_i = X_i W_i
\]

Across \(N\) members, tensors can be stacked:

\[
X \in \mathbb{R}^{N \times M \times K}, \quad
W \in \mathbb{R}^{N \times K \times P}, \quad
Y \in \mathbb{R}^{N \times M \times P}
\]

and executed as batched or grouped matrix multiplication.

The cost is that different weight matrices reduce weight reuse. An ordinary batch applies one matrix to many inputs; a population may need to keep many matrices close to compute. This creates a hardware and memory-bandwidth problem rather than invalidating matrix execution.

A future implementation may favour:

- local weight storage per member or member group;
- broadcast of shared task data;
- compact publication of conclusions rather than raw activations;
- grouped matrix kernels;
- conditional activation of only a task-relevant subset;
- hierarchical populations that reduce global communication.

## 3. Cognitive engine components

```text
                         qualified system
                               │
                     objective and world state
                               │
          ┌────────────────────┴────────────────────┐
          │                                         │
  private cognitive population              metacognitive control
  W₁, W₂, ... Wₙ                            budget and strategy
          │                                         │
          └────────────────────┬────────────────────┘
                               │
                     structured workspace
                               │
             synthesis, tools, and verification
                               │
                      one final action/result
```

### 3.1 Population members

Members independently generate:

- interpretations;
- hypotheses;
- derivations;
- counterexamples;
- predictions;
- experiment proposals;
- uncertainty estimates;
- critiques of specific claims.

### 3.2 Shared world state

The system may share externally grounded information:

- observations;
- verified facts;
- source provenance;
- task constraints;
- current objective;
- tool outputs;
- experiment results;
- unresolved questions.

It should not force members to share the same interpretation of those facts.

### 3.3 Structured epistemic workspace

The initial workspace should not be a free-form group conversation. A minimal claim record may contain:

```text
claim_id
claim_type
content
assumptions
supporting_evidence
contradicting_evidence
predictions
proposed_tests
source_member
confidence
calibration_history
dependencies
status
```

Useful statuses include:

```text
proposed
supported
contested
falsified
superseded
merged
unresolved
verified
```

### 3.4 Translation layer

Different members may express equivalent structure differently. The translation layer attempts to detect:

- semantic equivalence;
- mathematical equivalence;
- shared predictions;
- contradictory assumptions;
- overlapping causal structure;
- compatible partial models.

Version 0 may implement this conservatively using explicit symbolic fields and deterministic task structure. Learned latent translation should come later.

### 3.5 Synthesis layer

The synthesis layer constructs new hypotheses from compatible components. It must record provenance so the new candidate can be audited.

```text
H-42
├── mechanism from H-7
├── boundary condition from H-19
├── counterexample from H-23
└── new relation introduced during synthesis
```

A synthesized candidate receives no automatic privilege. It must face the same evidence and verification process as an original proposal.

### 3.6 Verification layer

Verification may include:

- deterministic rule checking;
- unit tests or code execution;
- symbolic calculation;
- simulation;
- held-out prediction;
- external retrieval with source comparison;
- independent model critics;
- adversarial counterexample search.

Where no decisive verifier exists, the system should preserve calibrated uncertainty rather than manufacture certainty.

## 4. Cognitive cycle

A provisional fixed cycle is:

1. **Observe:** load the complete task and evidence.
2. **Diverge:** members reason independently without seeing other paths.
3. **Extract:** convert paths into claims, assumptions, tests, and uncertainties.
4. **Compare:** detect overlap, conflict, and missing variables.
5. **Eliminate:** reject components contradicted by verified evidence.
6. **Synthesize:** construct new candidates from compatible surviving knowledge.
7. **Attack:** allocate critics and tools to falsify the strongest candidates.
8. **Verify:** run deterministic or external checks.
9. **Converge:** produce one result, several unresolved alternatives, or an explicit insufficiency result.

## 5. Adaptive compute allocation

The eventual architecture should treat active cognition as a movable resource.

Let total budget be \(B\):

\[
B_t = B_t^{reason} + B_t^{research} + B_t^{simulation}
+ B_t^{critique} + B_t^{verification} + B_t^{synthesis}
\]

with:

\[
\sum_k B_t^k = B
\]

A trivial task should not activate the full population.

```text
simple known task
→ one generator
→ one checker
→ answer
```

A novel high-uncertainty task may activate a large fraction of the population and reallocate compute as the bottleneck changes.

Version 0 should not learn this allocator. It should use a fixed schedule so the central synthesis claim can be isolated.

## 6. Escalation rather than permanent full activation

A future controller may begin with a small subset:

```text
2 members
→ disagreement or failed verification
→ activate 4 more
→ unresolved causal question
→ allocate research/simulation group
→ strong candidate emerges
→ allocate adversarial verification
```

This is not necessarily about reducing total resource use. It is about placing resources where additional cognition has the highest expected value.

## 7. Failure modes

### 7.1 Groupthink

Communication causes members to imitate early confident claims.

**Control:** independent first round, private states, delayed publication.

### 7.2 Majority capture

Common errors outweigh decisive minority evidence.

**Control:** evidence-weighted claims, explicit counterexample handling, no default majority rule.

### 7.3 Coordination overhead

The workspace consumes more compute and bandwidth than useful reasoning.

**Control:** compact schemas, bounded publication, local state, communication accounting.

### 7.4 False synthesis

The integrator creates a plausible relation unsupported by the original evidence.

**Control:** provenance, derivation records, independent verification, held-out checks.

### 7.5 Diversity collapse

Different weights remain numerically distinct but become functionally equivalent.

**Control:** behavioural diversity metrics and protected minority exploration.

### 7.6 One supreme judge

A single evaluator becomes a hidden monolithic bottleneck and single point of failure.

**Control:** multiple evaluators, formal tools, environment feedback, and challengeable synthesis.

## 8. Mutable implementation

The following are explicitly provisional:

- transformer architecture;
- identical member topology;
- population size;
- claim schema;
- fixed rounds;
- central workspace;
- external textual representation;
- model-based synthesis;
- flat population topology.

The long-term system may replace all of them if a descendant demonstrates a better mechanism under controlled evaluation.
