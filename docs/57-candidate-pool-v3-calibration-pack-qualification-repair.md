# Candidate-pool v3 calibration-pack qualification repair

## Scientific status

This is development-only repair evidence. It is not candidate calibration evidence and not selection evidence.

The first deterministic v3 calibration-pack qualification attempt executed exact software revision `2fd0654aae7f4f8a336b509e3b6247833ee3b54f`. Preflight and deterministic tests passed. During qualification, materialization of the first calibration task raised:

`ValueError: runtime input and expected output must be distinct artifacts`

No candidate model was invoked. No calibration candidate outcome or selection outcome was observed. The failed local artifact root `artifacts/capable-collective/c3q` must be preserved and must never be reused for the repaired qualification.

A second invocation of the original wrapper correctly stopped before target execution because `c3q` was nonempty. This confirms the evidence-preservation barrier behaved as intended.

## Root cause

The v3 API-contract task had two protected cases where runtime input and expected output were distinct Python dictionary constructions but canonicalized to identical JSON bytes:

- `repository-surgery-calibration-v3-api-contract-0001/case-01-explicit`
- `repository-surgery-calibration-v3-api-contract-0001/case-04-other`

`ProtectedCase` intentionally rejects this aliasing because privileged runtime input and expected-output artifacts must have distinct content identities.

## Minimal repair

The repair branch is rooted exactly at the failed revision and does not mutate the original failed branch. The repair adds ignored `request_id` metadata only to the runtime input of those two protected cases. Expected outputs are unchanged.

The following remain unchanged and are regression-checked:

- task IDs and seeds;
- defect families and mutation configurations;
- clean and buggy repository bytes;
- issue prompts and public cases;
- v3 solver prompts;
- gold patches and structured whole-file gold outputs;
- four-model v3 development candidate set;
- frozen v3 representation protocol.

The repair record canonical SHA-256 is `93a28f3e3f810182e4ce018aeab4f44103359e2f4251e9566e29335214d61bea`.

## Evidence-root rule

The failed `c3q` root is immutable evidence. Repaired Docker baseline/gold qualification must use a fresh root, `artifacts/capable-collective/c3q-r1`.

No candidate inference is authorized by this repair. After successful repaired qualification, the exact pack, qualification, repair-record, and Docker identities must be frozen before any 4 x 6 v3 calibration inference is authorized.
