# Candidate-pool v2 fresh selection: negative outcome

The fresh candidate-pool v2 Repository Surgery selection run completed successfully at software revision `3f67203429c31ab05970bbe476b965b5c1c1213c`.

The five-candidate population, twelve-task pack, target qualification, V4 whole-file representation, resource envelope, pair-attempt policy, 95% validity threshold, population size four, and deterministic selector were all frozen before any fresh v2 selection output existed. The run consumed all sixty authorized candidate/task calls exactly once.

## Immutable target evidence

- selection suite file SHA-256: `ac77effa62f42cd6914b8a67765a2318b72281f59edc94e3a8e5cbc114c41fce`
- selection suite report SHA-256: `713f25bc8635914bb8c491eb291f6355998995bb237d3d929a58d83a0db7a01c`
- selection protocol SHA-256: `85cb58d4bcb8dbbc2418251197880c80df6e0f1a85b889bdaa5e41fda2ea5762`
- qualified selection-pack freeze SHA-256: `1fb5ff94d0e36ece19c64819e737172d2cd55f620273334f58ee6f940324d10a`
- selection pack SHA-256: `e9bbd38067d5b18b043b2f6eecc87f8f3795fc37b43edcbd0bf391ef6f6212b4`
- qualification report SHA-256: `4e24679d44e63757c481cd2c21cd13d54d6b3aa4fcc780a26d4a6363c58c6134`
- operational configuration freeze SHA-256: `9fabeaaed55d4dfd8a500dec5346450cf5a497ed8f7fb3a65d5fec6b2307380b`
- frozen negative-outcome SHA-256: `b22e5c6fded1e9d0bd94fd4a8cd45bd4712ea9782d58a1f8820a6fdcb35d9517`
- pair count: `60`
- parse-valid count: `33/60`
- solved count: `30/60`
- candidate selection calls consumed: `60/60`

## Candidate diagnostics

| candidate | valid | solved | validity rate | score | accelerator time ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| `qwen3-8b-q8` | 12/12 | 10/12 | 1.0000 | 0.8333 | 308774 |
| `qwen2.5-coder-14b-q5km` | 11/12 | 10/12 | 0.9167 | 0.8333 | 127614 |
| `devstral-24b-q4km` | 8/12 | 8/12 | 0.6667 | 0.6667 | 344101 |
| `gpt-oss-20b-mxfp4` | 2/12 | 2/12 | 0.1667 | 0.1667 | 138091 |
| `devstral-small-2-24b-q4km` | 0/12 | 0/12 | 0.0000 | 0.0000 | 264873 |

Token-count extraction remained unavailable for these calls and therefore records zero tokens. This does not affect the outcome because the selection stopped at the validity gate before strongest-member or coalition tie-breaking could be used.

## Frozen selection result

The predeclared operational-validity threshold is `0.95`. With twelve tasks, one invalid result already yields `11/12 = 0.9167`, which is below the threshold. Only `qwen3-8b-q8` is eligible.

The deterministic result is therefore:

```text
selection_status=insufficient-eligible
eligible_candidate_ids=qwen3-8b-q8
strongest_candidate_id=
selected_candidate_ids=
```

The insufficient-eligible branch intentionally does not designate a strongest candidate and does not instantiate a four-mind population.

## Scientific interpretation

This is a valid negative population-selection result, not an infrastructure failure. All sixty pair results completed and the suite finalized with fresh selection evidence. Candidate-pool v2 therefore does not support the predeclared four-mind population under the frozen 95% validity gate.

The v2 selection split is now consumed. It must not be rerun, rescored at a lower validity threshold, edited to remove difficult tasks, used for candidate-specific prompt repair, or used to manually nominate four models despite the frozen rule.

Because no four-mind population was selected, a plural/synthesis experiment that claims to test the predeclared v2 population is not authorized. Any continuation must be a separately versioned development study with a decision-relevant hypothesis and new untouched selection evidence. Both the v1 and v2 negative selection outcomes remain immutable evidence.
