# Consumed-selection V5 self-review outcome freeze

V5 tested one same-mind self-review pass over immutable V4 drafts. It is development evidence on the already-consumed V1 selection split and is not population-selection or generalization evidence.

The original targeted V5 execution completed and captured the first 10 of 12 review calls before failing while persisting a non-scientific sidecar. Recovery was fail-closed: the original partial root was treated as immutable, the exact first ten transcript captures were reused without model inference, and only the final two predeclared DeepSeek multi-file reviews were generated. A first recovery attempt made zero new inference calls and failed on a Windows path-length boundary. A subsequent short-path preflight attempt also made zero new inference calls and failed before inference because an underscored helper was not imported explicitly. The final short-path recovery reused the ten existing calls and executed exactly the two missing calls once.

## Frozen identities

- original V5 software revision: `e9fb2e9630080dfe88ad5faaf15702d5643032cd`
- recovery software revision: `b2d4b3052124da46f37692e24c2fdaab164943fd`
- V5 development protocol SHA-256: `6bba796afed7138f1a679e11cbc84b4c19512b5f86de2a70138f7e7d4f2638c1`
- predecessor V4 outcome freeze SHA-256: `93c0d0bd15092e3a7c5d7664461f8542b6d203ff0c64132ad0517183bd370e9a`
- recovered V5 report SHA-256: `588ff8a6c619934b1ef0237ca09f1fe53bac3d971d56ca87af1cfa2e2470c5e1`
- recovered V5 output-manifest SHA-256: `aa6c150962aa606559d09e4aef13e73e4c82114af0ba5bf74ade788a0caefc7a`
- original partial-root manifest SHA-256: `bee3bdd30334bdeba2eaeeb1c22e21e98e1e8a8302c393552a05166847a9b6d1`
- failed long-path recovery-root manifest SHA-256: `4db80825c52d690098bdc578d48c025e4e524c7d9d39b932988562c273d80d14`
- content-addressed V5 outcome freeze SHA-256: `738d1e633c767f09f5d11c46e71eb7e552adfe424b93b826f3834380af7af58d`

## Targeted result

The immutable V4 baseline on the same 12 candidate/task pairs was 11/12 parse-valid and 9/12 solved. V5 reached 12/12 parse-valid and 10/12 solved, for deltas of +1 parse-valid and +1 solved. It recovered one of the three V4 failures, regressed none of the nine V4 solves, and changed four of twelve outputs.

Per candidate:

- `qwen3-8b-q8`: V4 3/3 parsed, 2/3 solved -> V5 3/3 parsed, 3/3 solved.
- `qwen2.5-coder-14b-q5km`: 3/3, 3/3 -> 3/3, 3/3.
- `devstral-24b-q4km`: 3/3, 3/3 -> 3/3, 3/3.
- `deepseek-coder-v2-lite-q5km`: V4 2/3 parsed, 1/3 solved -> V5 3/3 parsed, 1/3 solved.

The two remaining partial results are both DeepSeek outputs. `repository-surgery-selection-error-handling-0002` remained parse-valid but semantically partial at exact accuracy 0.5. `repository-surgery-selection-multi-file-0001` improved from a V4 parse-invalid draft to a parse-valid V5 review, but remained semantically partial at exact accuracy 0.5.

## Predeclared continuation gate

V5 required all of the following before target inference:

- 12/12 reviewed outputs parse-valid;
- at least 11/12 solved;
- at least two of the three V4 failures recovered;
- zero regressions among the nine V4 solved pairs.

Observed: 12/12 parsed, 10/12 solved, one failure recovered, zero solved-pair regressions. Therefore the gate is **REJECT**.

No broader V5 self-review probe should be run under this gate. The useful result is narrower: same-mind self-review can repair at least one real V4 failure without damaging the nine already-solved targeted pairs, and it eliminated the remaining targeted parse failure, but it did not provide the required semantic uplift. The next development decision should therefore not reinterpret the gate or rerun the consumed targeted matrix.
