# Candidate-pool v2 selection counterfactual forensics

This record is **post-selection development evidence only**. It does not change the frozen candidate-pool v2 selection result in `docs/56-candidate-pool-v2-selection-negative-outcome.md`.

## Frozen evidence identities

- Forensic implementation revision: `e3c51ea3541aa648c386d8a6396416d3fe5e443f`
- Frozen v2 selection suite file SHA-256: `ac77effa62f42cd6914b8a67765a2318b72281f59edc94e3a8e5cbc114c41fce`
- Frozen v2 selection report SHA-256: `713f25bc8635914bb8c491eb291f6355998995bb237d3d929a58d83a0db7a01c`
- Counterfactual report file SHA-256: `d99473a45835af905243cb9c860a2b1218ed0fca2bc61126b4f90c51abe6b63f`
- Counterfactual report SHA-256: `fbed493f89f2d2f442a837a0f355b48542b4c86e7f2919533825359f0e76ea13`
- Canonical forensic outcome freeze SHA-256: `8e03ebe5ac9e1d9c3f99e95523183bb94398bcfc75561340b4e40df03ddc5251`
- Parse-invalid frozen pairs examined: 27/60
- Candidate-model inference during forensics: false
- Selection rerun: false
- Threshold lowering: false
- Frozen v2 selection result changed: false

## Recovery ladder

The forensic evaluator reused only saved assistant outputs and qualified Docker grading. Each frozen parse-invalid pair was evaluated at the first cumulative parser level that could parse it.

1. `surface-tolerant`: accept `FILE:` as well as `FILE`, and allow blank lines between structured FILE blocks.
2. `prompt-path-tolerant`: additionally strip only the literal leading `relative/` prefix when the remainder exactly equals a solver-visible path. This level is diagnostic for the v2 prompt defect, not a proposed production rewrite.
3. `bare-file-tolerant`: additionally allow a FILE header followed directly by complete file contents without CONTENT delimiters.

Recovered-pair counts were:

- surface-tolerant: 13
- prompt-path-tolerant: 2
- bare-file-tolerant: 12

## Counterfactual diagnostics

At the frozen strict grammar:

| Candidate | Valid | Solved |
|---|---:|---:|
| qwen3-8b-q8 | 12/12 | 10/12 |
| qwen2.5-coder-14b-q5km | 11/12 | 10/12 |
| devstral-24b-q4km | 8/12 | 8/12 |
| gpt-oss-20b-mxfp4 | 2/12 | 2/12 |
| devstral-small-2-24b-q4km | 0/12 | 0/12 |

At `surface-tolerant`:

| Candidate | Valid | Solved |
|---|---:|---:|
| qwen3-8b-q8 | 12/12 | 10/12 |
| qwen2.5-coder-14b-q5km | 12/12 | 11/12 |
| devstral-24b-q4km | 10/12 | 10/12 |
| gpt-oss-20b-mxfp4 | 12/12 | 12/12 |
| devstral-small-2-24b-q4km | 0/12 | 0/12 |

At `prompt-path-tolerant`:

| Candidate | Valid | Solved |
|---|---:|---:|
| qwen3-8b-q8 | 12/12 | 10/12 |
| qwen2.5-coder-14b-q5km | 12/12 | 11/12 |
| devstral-24b-q4km | 12/12 | 12/12 |
| gpt-oss-20b-mxfp4 | 12/12 | 12/12 |
| devstral-small-2-24b-q4km | 0/12 | 0/12 |

At `bare-file-tolerant`, Devstral-Small-2 also reaches 12/12 parse validity but solves only 10/12; the other four remain unchanged from `prompt-path-tolerant`.

## V3 representation decision

The minimum non-bare representation that exposes a four-candidate development set is the surface-tolerant structured whole-file format plus removal of the v2 prompt-path ambiguity.

Therefore v3 development should:

- retain structured whole-file replacement with explicit CONTENT delimiters;
- accept optional `:` after the `FILE` keyword;
- accept blank lines between FILE blocks;
- change the prompt example so it never uses the misleading literal placeholder `relative/file.py`;
- continue to require exact solver-visible paths in production, with **no** automatic `relative/` prefix rewrite;
- reject bare-file mode from the production v3 representation;
- carry forward for v3 development the four candidates `qwen3-8b-q8`, `qwen2.5-coder-14b-q5km`, `devstral-24b-q4km`, and `gpt-oss-20b-mxfp4`.

Devstral-Small-2 is not declared incapable: its saved outputs show substantial semantic capability under bare-file parsing. But broadening the production grammar solely to admit its delimiter-free convention is not justified by the minimality principle because a four-candidate development population already exists at the narrower structured boundary.

## Scientific boundary

These counterfactuals must never be substituted for the v2 selection result. No v2 population was selected. Any v3 selection must use a newly frozen operational protocol and fresh untouched selection evidence after v3 representation development is complete.
