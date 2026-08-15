# Candidate-pool v2 challenger source freeze

## Status

This is a pre-inference, development-only source freeze for the three challenger scouts predeclared by the candidate-pool v2 qualification protocol. It does not qualify capability and is not selection evidence.

Qualification protocol SHA-256:

`f3886fa683aeb5ab3343dc6c388da4b58ebc63f2911be01602fa2fdc2ddaa4b6`

Source-freeze SHA-256:

`22aa8b34a6f27cc87e651099d8194acce00ee736161d00d9866f4463322b9f2d`

No v2 challenger load inference had been performed when these identities were fixed.

## Frozen challengers

### `gpt-oss-20b-mxfp4`

- developer/source: OpenAI, `openai/gpt-oss-20b`
- first-party revision: `6cee5e81ee83917806bbde320786a8fb61efebee`
- artifact publisher: `ggml-org/gpt-oss-20b-GGUF`
- artifact revision: `b97cbb20d1995efd41dce8c4dd1ddf86e8db375b`
- filename: `gpt-oss-20b-MXFP4.gguf`
- SHA-256: `27cd6c432c7672cb812a92f611cf3ba7bbc35928262bb1e1253ff4ee6ae35901`
- exact size: `12109566624` bytes
- license: Apache-2.0

The ggml artifact repository's `.src_sha` binds this artifact generation to the same first-party OpenAI revision. During source qualification we found that ggml-org had recently replaced the older lowercase `gpt-oss-20b-mxfp4.gguf` artifact with a current uppercase `gpt-oss-20b-MXFP4.gguf`. Because this was resolved before any v2 challenger load outcome, the source freeze uses the current artifact and does not preserve the already-deleted historical artifact merely for continuity with scouting notes.

### `phi-4-reasoning-plus-14b-q5km`

- developer/source: Microsoft, `microsoft/Phi-4-reasoning-plus`
- artifact-era first-party revision: `609962c42f66296434ad0a4f3a99ac99381205c6`
- currently observed first-party revision: `69baf8528e1bcf05f475034d9e5dd32875ed125f`
- artifact publisher: `bartowski/microsoft_Phi-4-reasoning-plus-GGUF`
- artifact upload revision: `7724f4a631c905f40112df7104ec590dc3bf290a`
- filename: `microsoft_Phi-4-reasoning-plus-Q5_K_M.gguf`
- SHA-256: `7d4dd651787f16365d6ceed9bcc42fe76e47204dedf9ac3539a749e1c3f3b6f7`
- quantization: Q5_K_M, Bartowski imatrix, llama.cpp b5228
- license: MIT

The Bartowski repository names the Microsoft model as its original model but does not publish an immutable first-party source SHA for the conversion. The bound `609962...` revision is therefore explicitly an artifact-era provenance binding: it was the last first-party source snapshot before the May 1, 2025 quant upload. Later Microsoft revisions changed tokenizer/configuration files. We do not silently treat this GGUF as a reconstruction of current main.

The indexed Hugging Face artifact page exposes the exact file SHA-256 but only a rounded 10.6 GB size. The freeze therefore treats immutable artifact revision + SHA-256 as the content identity. Exact target byte count must be observed and recorded before load; a hash mismatch fails qualification.

### `devstral-small-2-24b-q4km`

- developer/source: Mistral AI, `mistralai/Devstral-Small-2-24B-Instruct-2512`
- artifact-era first-party revision: `839af38e4e97acc43ff9ca61dff0ef6efc1cf407`
- currently observed first-party revision: `c599e8e56f3f9110e97f0dc0450ce248e3334d84`
- artifact publisher: `bartowski/mistralai_Devstral-Small-2-24B-Instruct-2512-GGUF`
- artifact upload revision: `2926c4f9c89e15bdebd5c8f458acd9609e778631`
- filename: `mistralai_Devstral-Small-2-24B-Instruct-2512-Q4_K_M.gguf`
- SHA-256: `bfd11c8679c6b81eb43763505465d7dcfa72e460ab1c220ecc235a3efadd7f7f`
- exact size: `14334438272` bytes
- quantization: Q4_K_M, Bartowski imatrix, llama.cpp b7335
- license: Apache-2.0

The GGUF was uploaded on the same release date as Mistral's initial super-squashed first-party snapshot, which is the source revision bound here. Current first-party main later changed THINK-token handling, so the exact GGUF candidate is intentionally the December 2025 artifact lineage rather than current main.

Bartowski also warns that Mistral Vibe/tool-calling integration required more work. That caveat does not change this candidate identity: the predeclared v2 gate uses direct Repository Surgery prompts and no Mistral Vibe/tool-calling layer. Runtime compatibility and full GPU offload remain empirical load-qualification questions.

## Next gate

The next expensive stage is intentionally small: download/hash only these three immutable artifacts and perform exactly one formal full-offload load qualification per challenger under the already frozen llama.cpp b10361 runtime and RTX 4060 Ti target. A failed challenger is not retried or substituted. Existing incumbent load evidence is reused because incumbent model/runtime identities did not change.

Only challengers that pass source and load qualification can enter the six-task calibration gate. No fresh selection pack is created until calibration is complete and a new operational freeze is written.
