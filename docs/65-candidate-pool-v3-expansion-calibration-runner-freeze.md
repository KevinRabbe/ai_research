# Candidate-pool v3 expansion calibration runner freeze

## Status

The sequential v3 expansion calibration runner passed the full repository test suite at revision `8a6506700e5eea79afbece4b7b112215f8552b3a` before any expansion calibration model call.

This freeze authorizes the development calibration specified by the pre-outcome expansion protocol and nothing beyond it. The three load-qualified scouts are evaluated in their already frozen order, six reused V3 development-calibration tasks per scout, and execution stops permanently after the first scout that passes the unchanged gate.

## Frozen runner identities

- runner source revision: `8a6506700e5eea79afbece4b7b112215f8552b3a`;
- runner source Git blob SHA-1: `9d063bcad030aa728aa670acb6b400633df6933d`;
- runner test Git blob SHA-1: `76e9f658a356cd727c5cc237fe97b56a6d41762f`;
- runner protocol SHA-256: `2135fa7de82f14a024927792ea91f4e0d01b78115e6fd549b1f06e716a22e17f`;
- reused base V3 calibration engine Git blob SHA-1: `e4e03da726ecf0ce2694c49b69a3c32896dfbaa3`;
- predecessor expansion load-outcome freeze SHA-256: `6d239aeb17b8c29e038cdde7babdd8db91ef7caa3ecb3a7f02ace0920d6c88bd`;
- calibration-runner freeze SHA-256: `8986bcc869326493483e239da153965000d9f8c65254baf67c903e9959e5da26`.

## Frozen scout order

1. `qwen3-14b-q5km`;
2. `ministral-3-14b-instruct-2512-q5km`;
3. `ministral-3-8b-instruct-2512-q5km`.

All three previously passed the exact load-only gate with full GPU offload. `e3l` remains immutable and is verified by the calibration runner before any new inference.

## Calibration task material

The runner reuses the exact six completed V3 **development** calibration tasks, as predeclared before the scout identities were chosen:

1. `repository-surgery-calibration-v3-api-contract-0001`;
2. `repository-surgery-calibration-v3-boundary-0001`;
3. `repository-surgery-calibration-v3-error-handling-0001`;
4. `repository-surgery-calibration-v3-local-logic-0001`;
5. `repository-surgery-calibration-v3-multi-file-0001`;
6. `repository-surgery-calibration-v3-state-management-0001`.

The repaired pack identity, representation, transport, resource envelope, and qualified-Docker grading path are unchanged. This remains development evidence and cannot become selection evidence.

## Unchanged gate

A scout passes only with:

- parse-valid: `6/6`;
- solved: at least `4/6`.

No threshold lowering, candidate-specific prompt tuning, failed-candidate rerun, task repair, output repair, or scout reordering is authorized.

## Sequential inference authorization

The upper bound is 18 pair calls, but it is not a license to consume all 18 unconditionally:

- first evaluate `qwen3-14b-q5km` on exactly six tasks;
- if it passes, stop and leave both later scouts unevaluated;
- if it fails, evaluate `ministral-3-14b-instruct-2512-q5km` on exactly six tasks;
- if it passes, stop and leave the final scout unevaluated;
- only if both earlier scouts fail may `ministral-3-8b-instruct-2512-q5km` receive its six calls;
- if all three fail, freeze the negative expansion outcome and stop.

Each candidate/task pair receives at most one call. `attempt.json` is written before inference; a partial pair blocks all new inference; a completed `result.json` is reused verbatim without another call. The first invocation must use fresh `artifacts/capable-collective/e3c` evidence.

## Post-run boundary

After the expansion calibration completes or stops, its evidence must be frozen before any population or selection decision. Selection-pack authoring, selection inference, and plural synthesis remain unauthorized by this freeze.
