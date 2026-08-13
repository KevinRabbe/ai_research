# Local raw calibration reasoning EOF v5

Target v4 all-five boundary evidence exposed one remaining output-transport edge case. A candidate transcript can finish its generation after emitting `[End thinking]` but before emitting any assistant answer bytes. The v3/v4 extractor removed the transcript's final blank-line terminator and then searched for an end marker that still included those blank lines, incorrectly raising `llama output transcript has unterminated reasoning`.

V5 changes only this transport classification. When the normalized transcript closes reasoning exactly at EOF, the reasoning bytes are preserved and the assistant answer is the empty byte string. The existing strict unified-diff parser therefore records `model output is empty` as an ordinary candidate parse failure and the calibration batch continues. A transcript that genuinely lacks `[End thinking]` still fails closed as infrastructure.

V5 does not increase the 2048-token prediction budget, retry inference, repair or infer a patch, alter the prompt, relax unified-diff grammar, change Docker execution, change privileged grading, expose protected material, or alter the one-attempt raw condition. The protocol identity adds `reasoning_eof_policy=closed-reasoning-empty-answer-v1` and advances the report/protocol schema identity.

The failed v4 all-five artifact remains immutable and is not a five-model capability report. Its partial transcript inventory reached Qwen3, Qwen2.5-Coder, and Gemma; Gemma ended at the reasoning close marker with no assistant sidecar, and Devstral/DeepSeek were not reached. The earlier standalone clean Qwen3 v4 smoke remains a valid candidate-specific malformed-diff result.
