# Candidate-pool v3 fresh selection-pack authoring

## Boundary

The positive V3 expansion-calibration outcome is frozen before this pack exists. The exact four-member population is:

1. `qwen2.5-coder-14b-q5km`;
2. `devstral-24b-q4km`;
3. `gpt-oss-20b-mxfp4`;
4. `qwen3-14b-q5km`.

No candidate-model selection inference is authorized by this authoring step.

## Fresh selection split

The V3 selection pack contains exactly 12 new tasks using seeds `401` through `412`, with two tasks in each frozen defect family:

- API contract;
- boundary;
- error handling;
- local logic;
- multi-file behavior;
- state management.

The task IDs use the new `repository-surgery-selection-v3-*` namespace. The module validates that task IDs and generation seeds do not overlap prior calibration or selection blueprints and also compares content fingerprints against the consumed legacy task material.

## Representation qualification

Every task uses the frozen V3 structured full-file representation. Before Docker grading, the deterministic gold whole-file answer is passed through the production V3 interpreter and must reconstruct the exact canonical gold patch. This prevents a pack from qualifying merely because its direct gold patch is correct while its solver-visible representation is broken.

## Deterministic Docker qualification

Qualification is project-authored evidence only:

- baseline repository must be observably defective (`exact_accuracy < 1` and not qualified);
- gold repair must be qualified with `exact_accuracy = 1` and `valid_rate = 1`;
- V3 gold output must parse through the production interpreter to the exact gold patch;
- candidate-model inference is false;
- selection outcomes observed is false;
- selection evidence is false.

The qualification root is `artifacts/capable-collective/s3q`.

## Frozen selection constraints

The pack binds the positive expansion-calibration outcome freeze and the V3 representation protocol. Future selection remains fixed at:

- 12 fresh untouched tasks;
- population size 4;
- minimum valid rate `0.95`;
- one selection run after pack qualification/freeze;
- no threshold lowering after outcomes.

## Next boundary

This branch must pass full CI before local deterministic qualification is run. After local qualification succeeds, the exact pack and qualification report identities must be frozen on a separate branch before any selection runner or selection-model inference is authorized.
