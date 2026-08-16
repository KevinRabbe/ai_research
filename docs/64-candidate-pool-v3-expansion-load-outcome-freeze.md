# Candidate-pool v3 expansion load outcome freeze

## Status

The exact three-scout load-only qualification authorized by the v3 expansion load-runner freeze completed successfully at software revision `f0a0e59e38f9045485e11ce6b00da3290cc20bbc`.

All three frozen scouts were launched exactly once. The completed local evidence root contains three attempt markers, three completed result files, zero partial result directories, and the finalized suite. Every scout passed the load gate and proved full GPU layer offload.

This evidence is candidate-development load qualification only. It is not calibration evidence and is not selection evidence.

## Immutable evidence identities

- artifact root: `artifacts/capable-collective/e3l`;
- suite file SHA-256: `aff58fd340821e34893ee103d5e27c1e583fe18333a4e08e5a7d1ffdee8b99b0`;
- suite report SHA-256: `e6b99ab7dcb42b359204d3ae2c8b2d0a4c5ea43aaa4dfa198239b20495608966`;
- load-runner protocol SHA-256: `6670ae531b31bd0548947bcc4ce0b8248204648f0bd3d280c68e1211bed340a4`;
- load-runner freeze SHA-256: `f64bb5a63dbe9e9141f44840d55b33420decaca71cc108c2842e8d43175ec763`;
- expansion source-freeze SHA-256: `7e3a49def60361dc2ce82f32c750d44b4dd0cb2d024b79f76d8469be3e2bec03`;
- expansion load-outcome freeze SHA-256: `6d239aeb17b8c29e038cdde7babdd8db91ef7caa3ecb3a7f02ace0920d6c88bd`;
- new model launches consumed: `3/3`;
- completed results: `3`;
- partial results: `0`;
- qualified scouts: `3`;
- failed scouts: `0`.

## Frozen scout outcomes

| scout | status | full offload | peak GPU MiB | result SHA-256 |
| --- | --- | ---: | ---: | --- |
| `qwen3-14b-q5km` | `LOCAL_MODEL_LOAD_PASS` | 41/41 | 10914 | `ed07b5e6c09152c1a5a3d0a329074faa699d07aa39b8cb9d9d849ef5a6098995` |
| `ministral-3-14b-instruct-2512-q5km` | `LOCAL_MODEL_LOAD_PASS` | 41/41 | 10130 | `a456a460a8fc0f62bf22f46ad6a1aa8337866c8c4cb7923db8528eab253917c1` |
| `ministral-3-8b-instruct-2512-q5km` | `LOCAL_MODEL_LOAD_PASS` | 35/35 | 6706 | `8273e88b4df5319ebd91c465808c821821ae515e9856d940d099ee847fb13215` |

The frozen model artifact identities remain:

- `qwen3-14b-q5km`: 10,514,569,568 bytes, SHA-256 `e7c9aba1129ca2936be9eca01419d9f86af40e08caa01230d5574b34d08e3e31`;
- `ministral-3-14b-instruct-2512-q5km`: 9,621,091,904 bytes, SHA-256 `f16fef77021df0d4c22e69140a2038478370492f51867b6237699918ae711000`;
- `ministral-3-8b-instruct-2512-q5km`: 6,059,268,512 bytes, SHA-256 `7a5454127ec772e2389f0e71a77fedb88b83d4366d8a69facd0cfd0898f04d35`.

## Scientific consequence

The load qualification answered its only admissible question: all three predeclared scout artifacts fit and execute under the frozen target-machine resource envelope with full GPU offload. It did not test repository-surgery capability.

Accordingly:

- `e3l` is consumed and immutable;
- load qualification must not be rerun;
- model artifacts must not be substituted;
- scout ordering must not be changed after this outcome;
- candidate-specific runtime tuning is forbidden;
- calibration inference remains unauthorized;
- selection-pack authoring, selection inference, and plural synthesis remain unauthorized.

After this exact outcome-freeze commit passes CI, calibration-runner authoring is authorized. The runner must preserve the expansion prefreeze rule: calibrate the load-qualified scouts sequentially in the frozen order and stop immediately when the first scout passes the unchanged v3 development gate (`6/6` parse-valid and at least `4/6` solved). No candidate may receive more than one attempt on any consumed calibration pair, and the calibration outcome must be frozen before any further population or selection decision.
