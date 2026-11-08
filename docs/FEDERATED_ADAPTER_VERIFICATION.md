# Hospital-local training and adapter verification

Updated 24 October 2026. This records working software tests, the deployment boundary and remaining evidence. It does not establish clinical validation or real hospital participation.

## What was exercised

1. `python scripts/flower_spike.py --dataset runtime/federation-check/synthetic.csv --tls` ran a real SuperLink and three SuperNodes with TLS and registered node keys. Separate synthetic tabular bundles remained in local node directories. Three rounds returned arrays and sample counts; the nonzero global-weight norm was 0.00431707. This is the tabular model, not MedGemma.
2. `python scripts/check_adapter_federation.py` created a tiny randomly initialized Gemma 3 text model and three separate software-fixture corpora. Each node performed one completion-loss training batch. Flower Message replies contained only `arrays` and `metrics`, with `num-examples: 1`. Fourteen adapter tensors occupied 2,048 bytes. Aggregation changed the global adapter. The fixture completion loss changed from 3.527132 to 3.517104; this is neither a clinical score nor a MedGemma result.
3. The same adapter runner was exercised through real TLS/authenticated SuperNodes using the command below. Three nodes returned three rounds with zero failed replies and `MEDFLOCK_ADAPTER_OK clients=3 tensors=14`. Initial and final arrays differed. Node logs show train messages being received and returned; no dataset upload endpoint is used by the runner.

```powershell
.venv/Scripts/python.exe -X utf8 scripts/check_adapter_federation.py
.venv/Scripts/python.exe -X utf8 scripts/flower_spike.py --tls --adapter-configs runtime/adapter-federation-check/hospital-0/runner.json runtime/adapter-federation-check/hospital-1/runner.json runtime/adapter-federation-check/hospital-2/runner.json
```

These are loopback simulated institutions on one workstation, not independent hospitals. Raw records are not part of the supported update payload; this is not a proof against malicious encoding or model inversion. Weight updates can leak information. Secure aggregation and differential privacy are not established by this test.

## Available runner contract

`adapter_federation.py` supports text LoRA and optional CUDA QLoRA using the existing distillation configuration schema. A node loads its own config/corpus locally. It verifies approved example declarations, fixed train/validation/test splits, tokenizer lengths and the immutable remote base revision. An adapter contract hashes task ID, base identity, tokenizer vocabulary/template, rank and sorted tensor names/shapes; local safetensors checkpoints are also checksummed. Bad shapes, dtype, non-finite arrays and mismatched contracts are rejected. Only the training split is used for the batch.

The batch runner deliberately performs one local example per round. The coordinator receives adapter tensors and sample counts, not losses or records. The server manifest contains compatibility metadata and the initial adapter bundle. Aggregation remains experimental FedAvg of compatible LoRA matrices; matrix averaging can lose accuracy as client adapters diverge. It requires comparison against local-only and centralized adapter baselines, non-IID tests, clinical evaluation and promotion review before use. A successful transport test cannot establish that the aggregate is better.

Run `scripts/prepare_adapter_round.py --local-config PATH --output NEW_BUNDLE_DIRECTORY` on a trusted preparation/hospital machine. It exports `initial-adapter.npz` and `server.json`; transfer only those files to the coordinator. Do not transfer local config paths containing credentials or the corpus. The loopback spike automates this preparation on the shared test workstation, so it is not evidence of independent machine isolation.

For an actual hospital, install the locked `llm` dependencies (plus `qlora` for a supported GPU) in a dedicated runner environment. The ordinary web-serving image does not include PyTorch. Use the existing authenticated SuperNode command but provide `--node-config 'adapter-config="/hospital/private/runner.json"'`. Preserve the trusted CA and registered private key locally. Configure the coordinator with `server-manifest` pointing to the transferred `server.json`; enable hospital mode only with real approved node-to-Flower identity bindings. `HospitalFedAvg` checks eligibility at dispatch and aggregation. Deployment/node credentials and local permissions still need operational verification on real machines.

## What this does not do

- No MedGemma 4B training was run. No GPU was available; a 4B frozen FP32 base alone is roughly 14.9 GiB before activation/adapter/runtime overhead. A single batch does not remove that memory requirement, and the shared VPS also hosts other clients.
- The deployed GGUF inference model was not updated by these tests. `global-adapter.npz` is a research candidate, not a release. It still needs evaluation, an approved PEFT checkpoint/export, conversion/quantization compatibility checks, signing/checksums and a deliberate inference rollout.
- No hospital-controlled GPU, QLoRA CUDA execution, independent hospital data, clinical reviewer approval, secure aggregation or poisoning robustness was tested here.
- Portal login and notification activity do not prove a training runner is connected. Automatic dashboard-to-hospital training orchestration and hospital-specific round history remain separate integration work.
- CSV outcomes train the tabular model. A language-model runner needs permissioned, reviewed prompt/response examples. Images/waveforms require separate validated contracts; they do not become MedGemma training labels automatically.

## Kafka decision

Keep model updates on Flower's authenticated transport and aggregation path. Flower already defines the ServerApp/SuperLink/SuperNode/ClientApp flow; Kafka would add another delivery/replay/security boundary without validating base compatibility, participant eligibility or model quality. If durable integration events become necessary, Kafka can carry versioned lifecycle metadata and artifact references, while weights remain in the Flower/artifact flow. No broker was installed on the shared VPS. Architecture references: [Flower](https://flower.ai/docs/framework/explanation-flower-architecture.html), [Apache Kafka](https://kafka.apache.org/documentation/). Implementation uses the project's pinned installed Flower API; the public architecture page is background, not a replacement version specification.
