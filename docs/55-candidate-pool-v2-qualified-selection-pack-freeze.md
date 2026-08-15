# Candidate-pool v2 qualified selection-pack freeze

## Status

The fresh candidate-pool v2 Repository Surgery selection pack has been qualified on the target machine and is frozen before any candidate selection inference is authorized.

This boundary is pre-selection evidence. No candidate output on the fresh selection tasks has been observed, and zero of the planned 60 candidate/task selection calls have been consumed.

## Bound identities

- selection-pack source revision: `1e74b8234c21dc5a1bbf6b2c240e1407a0334479`
- selection-pack SHA-256: `e9bbd38067d5b18b043b2f6eecc87f8f3795fc37b43edcbd0bf391ef6f6212b4`
- target qualification-report SHA-256: `4e24679d44e63757c481cd2c21cd13d54d6b3aa4fcc780a26d4a6363c58c6134`
- five-survivor operational-freeze SHA-256: `9fabeaaed55d4dfd8a500dec5346450cf5a497ed8f7fb3a65d5fec6b2307380b`
- qualified Docker report SHA-256: `2d2e3af2685a826b92cc03c36865cd74f1c4c954520b9448c82edbc294a70b04`
- canonical v2 selection-pack-freeze SHA-256: `1fb5ff94d0e36ece19c64819e737172d2cd55f620273334f58ee6f940324d10a`

## Candidate set

The exact candidates authorized for the one-shot selection run are:

1. `qwen3-8b-q8`
2. `qwen2.5-coder-14b-q5km`
3. `devstral-24b-q4km`
4. `gpt-oss-20b-mxfp4`
5. `devstral-small-2-24b-q4km`

`phi-4-reasoning-plus-14b-q5km` remains excluded by the completed calibration gate and is not part of this selection pack.

## Task qualification

The pack contains exactly 12 fresh tasks, two per frozen defect family. Target qualification established for every task that:

- the project-authored buggy baseline is observably defective (`exact_accuracy < 1.0`), and
- the project-authored gold repair restores `exact_accuracy = 1.0` and `valid_rate = 1.0`.

The two multi-file tasks retain the canonical mutation value `multi-file-behavior` and require repairs across both affected files.

## Selection rule remains unchanged

The subsequent candidate selection run is still governed by the predeclared candidate-pool v2 operational freeze:

- 12 fresh tasks per candidate,
- exactly one candidate/task attempt,
- `min_valid_rate = 0.95`,
- final population size 4,
- no threshold lowering after observing outcomes,
- no prompt or representation tuning after selection begins.

The qualified pack may now be consumed exactly once by the selection runner. The selection runner must bind this freeze identity before authorizing any candidate inference.
