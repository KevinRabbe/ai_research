# Consumed-selection development V5 partial recovery

The first targeted V5 same-mind self-review execution was interrupted by an orchestration-side artifact durability failure after the tenth of twelve review calls. The failure occurred after llama.cpp returned and the tenth transcript was readable, while the runner attempted to write the derived `.process-stdout.bin` sidecar. No complete V5 report or final output-channel manifest was produced.

This recovery is fixed before any V5 candidate output is inspected for scientific interpretation. The original partial artifact root is immutable and is not resumed in place. Recovery reconstructs the exact twelve V5 review prompts from the frozen V4 drafts and requires exactly the first ten transcript captures in deterministic candidate/task order. It refuses to continue if either of the final two expected transcript captures already exists.

The ten existing transcripts are reused without model inference. The only new model calls are the two missing DeepSeek review pairs:

- `repository-surgery-selection-multi-file-0001`
- `repository-surgery-selection-multi-file-0002`

The V5 scientific protocol remains unchanged at SHA-256 `6bba796afed7138f1a679e11cbc84b4c19512b5f86de2a70138f7e7d4f2638c1`. The recovery software revision is recorded separately from the original V5 software revision `e9fb2e9630080dfe88ad5faaf15702d5643032cd`. The recovery code changes only orchestration/evidence durability; it does not change prompts, visible task material, candidate identities, model resources, temperature, seed, output contract, parser, protected evaluator, or continuation rule.

The original partial root is content-manifested read-only into the fresh recovery artifact. Reused transcripts are prompt-bound again with the existing deterministic transcript parser, copied byte-for-byte into the fresh recovery artifact, and evaluated through the unchanged protected Docker evaluator. Resource telemetry that was held only in the interrupted process memory is not invented for reused calls; those fields remain unavailable. The two new calls retain full runtime telemetry.

The targeted V5 continuation rule remains exactly the predeclared rule: 12/12 reviewed outputs parse-valid, at least 11/12 solved, at least two of the three V4 failures recovered, and zero regressions among the nine V4 solved pairs. This recovery remains development-only use of the consumed V1 split and cannot support a new population-selection or generalization claim.
