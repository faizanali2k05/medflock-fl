# Adapter-first distillation and optional consolidation

Decision updated 24 October 2026: the owner authorized LoRA alongside optional full-weight training. This supersedes the earlier full-only restriction. Teacher responses remain completion-only sequence-distillation targets; changing the trainable parameters does not remove corpus review, evidence, privacy or evaluation requirements.

## Stages and selection

1. Freeze the approved corpus, source bundle, base revision and patient/family-disjoint splits. Train a LoRA adapter first. Use QLoRA on a supported CUDA GPU when a quantized frozen base is needed for memory savings.
2. Inspect validation performance and generated answers against the unchanged model. Loss is only an engineering signal: evaluate omissions, contradictions, unsupported claims and treatment safety with independent review. Keep the held-out test set out of hyperparameter selection.
3. Escalate only when documented validation failures persist after checking data quality, retrieval and adapter settings. Full-weight training is a separate, explicitly configured job. It loads the exact original base, verifies and merges the selected adapter, then unfreezes parameters. Include reviewed difficult cases plus representative replay cases to check forgetting. Complexity alone does not prove that LoRA lacks capacity.
4. Preserve both artifacts and their evidence. No job automatically replaces the deployed model. Compare generations and clinical review results before any promotion; retain the original baseline if candidates regress.

This is sequential training, not per-patient routing between two live models. Merging an adapter alone is not full-weight training. Text-only distillation does not validate the image/ECG pathways.

## Configuration

Use `python scripts/distill.py --config PATH` with a private JSON file. Existing corpus fields and review/export commands in README still apply. Set an immutable authorized base revision, real permission reference, approved corpus path and a fresh output directory.

```json
{
  "student": "google/medgemma-1.5-4b-it",
  "revision": "REPLACE_WITH_AUTHORIZED_IMMUTABLE_COMMIT",
  "model_permission_reference": "REPLACE_WITH_REAL_APPROVAL_REFERENCE",
  "corpus": "data/teacher-approved/hfref-v1.jsonl",
  "output": "artifacts/hfref-adapter-v1",
  "method": "qlora",
  "device": "cuda",
  "precision": "bfloat16",
  "memory_budget_gib": 6,
  "gradient_checkpointing": true,
  "rank": 16,
  "max_tokens": 1024,
  "epochs": 1,
  "learning_rate": 0.0002,
  "seed": 42
}
```

These are candidate settings, not measured hardware recommendations. The 6-GiB value does not establish fit or reserve memory. For ordinary LoRA use `method: lora`; its frozen base is loaded in the explicit precision. For consolidation use a new output directory, `method: full`, `initial_adapter: artifacts/hfref-adapter-v1`, and an independently measured memory budget. Start with a conservative validation sweep for full-weight learning rate, rather than retaining the adapter rate automatically. The runner requires explicit full mode for `initial_adapter`.

Install from the lockfile in an isolated training environment: `uv sync --locked --extra llm --extra qlora --extra dev`. The optional QLoRA extra pins bitsandbytes 0.48.2. Validate the CUDA driver, wheel and BF16 support on that machine. This implementation restricts QLoRA to CUDA; CPU runs use FP32 LoRA/full mode. It uses NF4, double quantization and PEFT k-bit preparation as described in [PEFT's quantization guide](https://huggingface.co/docs/peft/developer_guides/quantization); package metadata is available at [bitsandbytes 0.48.2](https://pypi.org/project/bitsandbytes/0.48.2/).

## Integrity and memory

The report records the original-base and selected-student held-out completion losses, loss delta, trainable parameter count, precision, training configuration, corpus hash, parent adapter-report hash and artifact hashes. QLoRA's baseline is the same NF4 base, not an FP32 comparison. The parent must match the exact base/revision and pass artifact checksums. Hashed group/prompt split assignments prevent known cases from changing splits between stages. These hashes do not detect paraphrases or authenticate a reviewer's identity; semantic leakage and review provenance still require an independent audit.

Preflight rejects clearly inadequate MedGemma budgets before downloading weights. Full mode retains a conservative 59.6-GiB FP32 training-state allowance. LoRA checks frozen-base storage (about 14.9 GiB FP32 or 7.5 GiB BF16); QLoRA checks about 1.9 GiB of nominal packed base storage. Adapter optimizer state, quantization metadata, unquantized modules, activations, evaluation and checkpoint operations all add memory. These checks are rejection floors, not fit guarantees. Profile peak device and host memory on dedicated hardware before long jobs. No swap or offload changes are made to the shared VPS.

## Evidence and remaining gates

CPU integration tests train tiny GPT-2 and Gemma 3 checkpoints, reload selected weights, evaluate the original baseline, and run Gemma 3 LoRA-to-full consolidation. Negative tests cover mismatched/tampered adapters and cross-stage split leakage. They prove software paths, not MedGemma quality.

No actual MedGemma weight training, CUDA QLoRA execution or clinical validation has been completed by this change. Reviewed corpus, GPU profiling, independent generation evaluations and clinical sign-off remain gates. There is no exact optimizer/RNG resume, distributed offload, automatic inference export or dashboard job-dispatch integration. The CLI produces candidate artifacts; the existing corpus upload UI does not silently launch expensive training.
