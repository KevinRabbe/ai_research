# Candidate-pool v3 calibration qualification freeze

## Scientific status

The repaired v3 development-calibration pack has completed deterministic Docker baseline/gold qualification successfully. This freeze is created before any candidate inference on the six fresh v3 calibration tasks. It is development evidence, not selection evidence.

The canonical calibration-qualification freeze SHA-256 is:

`b121dccd76616913fe144d8d298bc38a58bc278a1c6ba7e630e67c3bbaaef593`

This freeze does not itself authorize candidate-model calls. A separate restart-safe one-attempt calibration runner and gate must be implemented and validated before the 4 x 6 matrix can run.

## Bound identities

- repaired qualification software revision: `9dd4648f904df55dad3411c709d4f50f5a569a16`
- failed parent pack revision: `2fd0654aae7f4f8a336b509e3b6247833ee3b54f`
- v3 representation protocol SHA-256: `28243c1a330bbc51734aa9083f98ee8a2257c17f6290c71ec9bbb4404bca3c61`
- repair-record canonical SHA-256: `93a28f3e3f810182e4ce018aeab4f44103359e2f4251e9566e29335214d61bea`
- repair-record file SHA-256: `67042427cb8d4620265a13446073cfc4e73a3f4dc2b71a88e0cf3484b057a410`
- repaired calibration-pack canonical SHA-256: `c00d98ed758016dab5571570ababbcbb6c639aa39ad87be34f9c37cddc803513`
- repaired calibration-pack file SHA-256: `75fa710ada934da9e465721e38313ff1157c7b89963b18d760d1eca6703d43b0`
- repaired qualification canonical SHA-256: `255f7a1dadf12e0dfd5107ab21c48cbaa07fe91ae937095001f00249750b2923`
- repaired qualification file SHA-256: `732ebf9d9df79d00bda9de6ab0229784533a8ffad485aa4967bf746971be1ba1`
- qualified Docker report SHA-256: `2d2e3af2685a826b92cc03c36865cd74f1c4c954520b9448c82edbc294a70b04`

The repaired evidence root is `artifacts/capable-collective/c3q-r1`.

## Failed-evidence preservation

The failed deterministic evidence root `artifacts/capable-collective/c3q` remains immutable. Its ten-file manifest SHA-256 was

`10389a3bdd0c0db45d23a3a248a8a237906adac602433cd9033ceae499e4a276`

both before and after repaired qualification. The repaired qualification reports `failed_artifact_root_reused=False`.

## Qualification result

All six project-authored baselines are observably defective and all six gold repairs are exact and fully valid:

| Task | Baseline exact | Baseline valid | Gold exact | Gold valid |
|---|---:|---:|---:|---:|
| api-contract-0001 | 0.50 | 0.50 | 1.00 | 1.00 |
| boundary-0001 | 0.75 | 1.00 | 1.00 | 1.00 |
| error-handling-0001 | 0.50 | 0.75 | 1.00 | 1.00 |
| local-logic-0001 | 0.25 | 1.00 | 1.00 | 1.00 |
| multi-file-0001 | 0.00 | 1.00 | 1.00 | 1.00 |
| state-management-0001 | 0.00 | 1.00 | 1.00 | 1.00 |

No candidate model was invoked. No calibration candidate outcome or selection outcome was observed.

## Future calibration boundary

The future development-calibration matrix is frozen at four candidates x six tasks = 24 pairs:

1. `qwen3-8b-q8`
2. `qwen2.5-coder-14b-q5km`
3. `devstral-24b-q4km`
4. `gpt-oss-20b-mxfp4`

For each candidate the existing v3 representation protocol requires 6/6 parse-valid outputs and at least 4/6 solved tasks. Maximum attempts remain one per candidate/task pair. There is no candidate-specific tuning, no rerun of consumed pairs, and calibration remains development-only evidence.

Before any model call, the runner must bind the exact freeze above, verify model/runtime identities, preflight all 24 pair roots, treat any partial pair as blocking, write an attempt marker before inference, and preserve completed `result.json` evidence verbatim.
