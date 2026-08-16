# Candidate-pool v3 calibration outcome freeze

## Status

The exact fresh candidate-pool v3 development calibration authorized by the runner freeze completed successfully at software revision `d8972e2ecc51f86c286169899024baea3850f33c`.

All 24 frozen candidate/task pairs were attempted exactly once. The completed root contains 24 completed pair results, 24 attempt markers, zero partial pairs, and the finalized calibration suite. The wrapper also confirmed that the preserved failed `c3q` evidence and the repaired `c3q-r1` qualification evidence were unchanged before versus after the run.

This calibration is development evidence only and is **not** selection evidence.

## Immutable calibration evidence

- artifact root: `artifacts/capable-collective/c3`;
- completed suite file SHA-256: `b1c8b697fcf2e7ccba5f60ac51ee67067e093f81c5342b4e6fdb791e9a74424e`;
- completed suite report SHA-256: `b9d45942ef96d62babf048aaf9661fa6b018d9881ae526029a5fd6e1c638d668`;
- runner protocol SHA-256: `2e3984de232ddab4b9a96f8363a331b013ce1c68f9a1b91bc651f1312ad9b600`;
- runner-freeze SHA-256: `6a2b815a3d2cd6b21c77f10bcd4725c05ba34a9a4605506940d85e72c5373cf9`;
- qualification-freeze SHA-256: `b121dccd76616913fe144d8d298bc38a58bc278a1c6ba7e630e67c3bbaaef593`;
- representation-protocol SHA-256: `28243c1a330bbc51734aa9083f98ee8a2257c17f6290c71ec9bbb4404bca3c61`;
- repaired calibration-pack SHA-256: `c00d98ed758016dab5571570ababbcbb6c639aa39ad87be34f9c37cddc803513`;
- frozen calibration-outcome SHA-256: `b82b08ea6603719ec70e250bf5635ea1c1443db25703b3dafd5e189b0a281f56`;
- pair count: `24`;
- new inference attempts consumed: `24/24`;
- parse-valid total: `23/24`;
- solved total: `19/24`.

## Predeclared calibration gate

The gate remains unchanged:

- required parse-valid count: `6/6`;
- minimum solved count: `4/6`.

No threshold or gate adjustment is permitted after observing these outcomes.

## Candidate outcomes

| candidate | parse-valid | solved | gate |
| --- | ---: | ---: | --- |
| `qwen3-8b-q8` | 5/6 | 1/6 | fail |
| `qwen2.5-coder-14b-q5km` | 6/6 | 6/6 | pass |
| `devstral-24b-q4km` | 6/6 | 6/6 | pass |
| `gpt-oss-20b-mxfp4` | 6/6 | 6/6 | pass |

Peak observed GPU use recorded by the completed suite was 9003 MiB, 11049 MiB, 14839 MiB, and 11823 MiB respectively.

The frozen eligible development population is therefore exactly:

1. `qwen2.5-coder-14b-q5km`;
2. `devstral-24b-q4km`;
3. `gpt-oss-20b-mxfp4`.

`qwen3-8b-q8` is ineligible under the frozen calibration gate.

## Scientific consequence

The predeclared downstream population size is four. Only three candidates passed calibration. The current v3 development set therefore cannot instantiate the required four-member population.

This is a valid negative calibration outcome, not an infrastructure failure. The 24-pair calibration matrix completed and the evidence root is consumed.

Accordingly:

- the calibration must not be rerun;
- the calibration gate must not be lowered;
- candidate-specific tuning based on these observed tasks is forbidden;
- an ineligible candidate must not be manually retained to reach four;
- an unqualified replacement candidate must not be inserted post hoc;
- a fresh v3 selection pack must **not** be authored from this three-candidate set;
- selection inference and plural/synthesis execution remain unauthorized.

If the project continues toward a four-member population, candidate expansion must be a separately versioned development step with a new pre-outcome source/load/qualification protocol completed and frozen before observing the new candidate's calibration outcome. It cannot reuse the consumed v3 calibration tasks as selection evidence or treat this freeze as authorization for ad-hoc model rescue.
