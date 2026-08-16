# Candidate-pool v3 expansion calibration outcome freeze

## Status

The sequential V3 expansion calibration completed successfully on the first pre-frozen scout. `qwen3-14b-q5km` received exactly the six authorized development-calibration calls, achieved `6/6` parse-valid and `5/6` solved, passed the unchanged gate, and triggered the mandatory stop rule.

The two later scouts were not evaluated. They are neither calibration failures nor members of the frozen four-model population.

## Frozen execution evidence

- execution software revision: `ac7f15152d12e56a3062aa72276dc8b9292c14b7`;
- evidence root: `artifacts/capable-collective/e3c`;
- suite file SHA-256: `bb628f97e9775b997369449bffe1a128ff11f3c05fa4bbc023b462fb2aac7c68`;
- suite report SHA-256: `6c54e6b3b57752dbde1bacc9f2bd2b5fdb6264a26bcdb63692d7510dabf7aa2a`;
- expansion calibration runner protocol SHA-256: `2135fa7de82f14a024927792ea91f4e0d01b78115e6fd549b1f06e716a22e17f`;
- expansion calibration runner-freeze SHA-256: `8986bcc869326493483e239da153965000d9f8c65254baf67c903e9959e5da26`;
- expansion load-outcome freeze SHA-256: `6d239aeb17b8c29e038cdde7babdd8db91ef7caa3ecb3a7f02ace0920d6c88bd`;
- predecessor V3 calibration outcome freeze SHA-256: `b82b08ea6603719ec70e250bf5635ea1c1443db25703b3dafd5e189b0a281f56`;
- canonical expansion-calibration outcome-freeze SHA-256: `d39b2d3da6d156485e957e8e37f7eb2e961364e45c936fd15b673f67ecc61f12`.

Exactly six new inference attempts were consumed. No expansion-calibration rerun is authorized.

## First-scout result

`qwen3-14b-q5km`:

- parse-valid: `6/6`;
- solved: `5/6`;
- gate: PASS;
- peak observed GPU usage: `15338 MiB`.

The only unsolved task was `repository-surgery-calibration-v3-error-handling-0001`; its output remained parse-valid. The five other tasks were both parse-valid and solved.

The six immutable pair-report identities are bound in the outcome-freeze module.

## Sequential stopping result

The predeclared order was:

1. `qwen3-14b-q5km`;
2. `ministral-3-14b-instruct-2512-q5km`;
3. `ministral-3-8b-instruct-2512-q5km`.

Because the first scout passed, execution stopped after six calls. The two Ministral scouts remain deliberately unevaluated. Evaluating either after this pass would violate the frozen stopping rule.

## Preserved predecessor evidence

The local wrapper verified that these read-only roots were byte-identical before and after `e3c`:

- `e3l`: `2a4aade4a78f45eb0160963b6d90e3f8c5f2d2cd63250570a23873f4b4fce5b4`;
- `c3q-r1`: `200c70894de8c017d25b11074c2d7b89333fd47165134d23e46c590029a41a71`;
- original `c3`: `492e44a3efe9bbef19a3abb6ae2ed592a481de4e6e9cb73bdc9feaafc6098a3f`.

`e3c` itself is immutable evidence and must be preserved.

## Frozen four-member population

The prior V3 calibration outcome had three eligible candidates:

1. `qwen2.5-coder-14b-q5km`;
2. `devstral-24b-q4km`;
3. `gpt-oss-20b-mxfp4`.

The positive expansion calibration adds exactly:

4. `qwen3-14b-q5km`.

This yields the required four-member population. Population feasibility is therefore `True`.

This is a development-population decision only. The consumed calibration tasks are not selection evidence.

## Next authorization boundary

After this outcome-freeze branch is CI-green, authoring a **fresh untouched 12-task V3 selection pack** is permitted for the exact four frozen candidates above.

The following remain forbidden:

- rerunning `e3c`;
- lowering the `6/6` parse-valid and `>=4/6` solved calibration gate;
- evaluating either unevaluated Ministral scout after the first-scout pass;
- candidate-specific tuning or output repair;
- substituting another model into the four-member population;
- reusing V2 selection tasks or any consumed V3 calibration task as selection evidence;
- V3 selection inference before the new selection pack is deterministically qualified and frozen;
- plural synthesis before the V3 selection population is frozen.

The future V3 selection keeps the already frozen selection constraints: 12 fresh untouched tasks, population size 4, and minimum valid rate `0.95`.
