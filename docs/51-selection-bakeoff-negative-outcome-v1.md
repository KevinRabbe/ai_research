# Frozen Repository Surgery selection bakeoff: negative outcome v1

The first target execution of the frozen five-candidate by twelve-task Repository Surgery selection bakeoff completed successfully at software revision `5e79a7b448ad3bdccbeb17132ce44861593f6ff9`.

The selection pack, qualification report, candidate identities, V8 structured-edit protocol, operational resource settings, and deterministic population rule were all frozen before these candidate outputs existed. No selection task or threshold was changed after observing the run.

## Immutable target evidence

- selection bakeoff report SHA-256: `cfb56dd84564db7de09be590c93107cf7d2c7e76f8971eabbe41a2f8926826fd`
- bakeoff plan SHA-256: `88183d2393942608c5953740cefb5ebfc6be5c493f323b9c8b8daffa75b58e69`
- selection-pack freeze SHA-256: `7dea54974ee3ee86fedbac1b5ed85bffbe8dee6a31ee325cda2fc03c748c41d1`
- output-channel manifest SHA-256: `fa80dcc9fa8939d0d5585dee2912757860dd2596c75bd9a94274320fdf51f2d2`
- selection-outcome freeze SHA-256: `e579e01b0c1d710a4ca303896da84801ef27d9502b66782c88f384129fbe4eb5`
- result count: `60`
- parse-valid count: `45/60`
- solved count: `44/60`

## Candidate diagnostics

| candidate | valid | solved | validity rate | score |
| --- | ---: | ---: | ---: | ---: |
| qwen3-8b-q8 | 9/12 | 9/12 | 0.7500 | 0.7500 |
| qwen2.5-coder-14b-q5km | 11/12 | 11/12 | 0.9167 | 0.9167 |
| gemma4-12b-it-qat-q4 | 2/12 | 2/12 | 0.1667 | 0.1667 |
| devstral-24b-q4km | 11/12 | 11/12 | 0.9167 | 0.9167 |
| deepseek-coder-v2-lite-q5km | 12/12 | 11/12 | 1.0000 | 0.9167 |

The frozen `BakeoffPlan` required `min_valid_rate=0.95`, `population_size=4`, and inclusion of the strongest eligible member when selection is possible. With twelve tasks, an 11/12 validity rate is approximately 0.9167 and therefore does not pass the threshold. Only `deepseek-coder-v2-lite-q5km` was eligible.

The deterministic result is consequently:

```text
selection_status=insufficient-eligible
eligible_candidate_ids=deepseek-coder-v2-lite-q5km
strongest_candidate_id=
selected_candidate_ids=
```

The insufficient-eligible branch intentionally does not designate a strongest candidate or any four-mind population.

## Scientific interpretation

This is a valid negative population-selection result, not an infrastructure failure. The 60 candidate calls completed and the report was finalized. The outcome says that the v1 frozen candidate pool cannot instantiate the predeclared four-mind population under the v1 validity gate.

The existing selection split is now consumed. It must not be rescored with a lower threshold, rerun with easier resource settings, edited to remove difficult tasks, or used to manually choose four models despite the frozen rule.

This result also does not establish plural uplift: no four-mind population was selected, so the planned plural-condition experiment cannot begin under the v1 selection protocol.

Any continuation must be explicitly versioned as a new development study. A scientifically defensible recovery path is to expand or otherwise revise the candidate-pool development process using calibration-only material, freeze a new operational configuration and a fresh untouched selection pack, and then execute a new predeclared selection study. The v1 negative result remains immutable evidence and must not be overwritten.

Token-count extraction was unavailable for all sixty calls, so the report records zero tokens in the bakeoff diagnostics. This does not affect the v1 outcome because selection stopped at the insufficient-eligible gate before strongest-member or coalition tie-breaking was reached. Future protocol versions may improve this observability only before a new untouched selection split is exposed.
