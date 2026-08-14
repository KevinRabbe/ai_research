# Consumed-selection development V5: same-mind self-review

V4 whole-file replacement substantially improved the consumed four-candidate matrix from 43/48 parse-valid and 42/48 solved under V1 to 47/48 parse-valid and 45/48 solved. Its predeclared full-matrix continuation gate still rejected because DeepSeek regressed to 11/12 parse-valid and 10/12 solved. That outcome is frozen separately and remains development-only evidence.

V5 tests a different intervention: one non-privileged same-mind review layer on top of the already-generated V4 draft. It does **not** regenerate V4 base answers. The immutable V4 assistant sidecars are reused after hash and output-manifest verification, so this experiment adds only one new review inference per candidate/task pair.

The reviewer sees exactly the same solver-visible issue, repository files, and public examples plus its own raw previous draft. It receives no V4 parse error, no evaluator score, no hidden test, no protected expectation, and no population-selection information. The reviewer identity must equal the draft candidate identity. The final answer uses the unchanged V4 whole-file FILE/CONTENT contract and deterministic interpreter.

The first probe is fixed at four non-Gemma candidates over three consumed tasks: `error-handling-0002`, `multi-file-0001`, and `multi-file-0002`. The first two contain the three V4 failure/partial observations; the third is a same-family control on which all four V4 drafts solved. This gives 12 reviewed pairs while requiring only 12 new inference calls.

The frozen V4 baseline on those exact pairs is 11/12 parse-valid and 9/12 solved. Before any V5 target inference, the continuation gate is fixed as follows: all 12 reviewed outputs must be parse-valid; at least 11/12 must solve; at least two of the three V4 failure/partial pairs must be recovered; and none of the nine V4-solved pairs may regress to unsolved.

Passing this targeted gate is necessary but not sufficient for operational promotion. A pass would justify one broader review-only replay across the full immutable 48-pair V4 development matrix, again without regenerating base drafts. A rejection closes this self-review protocol rather than prompting post-hoc edits on the consumed split; the next development direction would then be candidate-pool expansion/replacement under a separately predeclared source and hardware qualification protocol.

Nothing in V5 is selection evidence. Any future population selection requires a new operational configuration freeze and a fresh untouched selection pack.
