# GPU execution handoff

Current training choice: [adapter-first hybrid training](HYBRID_TRAINING.md). The full-weight configuration below is the optional escalation path. No MedGemma weights have been trained.

## Disk offload decision

Disk can store model/optimizer state between calculations. DeepSpeed ZeRO-Infinity supports CPU/NVMe offloading: https://www.deepspeed.ai/tutorials/zero/ . Offloading is a training-engine feature, not a directory setting or inference `device_map` setting. Active tensors still need working memory; compute and storage bandwidth limit speed. The current MedFlock trainer has no DeepSpeed integration. An offload configuration pasted into it would do nothing.

Do not enable host swap, allocate a giant scratch file, run an I/O benchmark or install GPU libraries on the shared Hostinger server. Existing databases share that storage. The agreed 2-core/6-GiB ceiling remains aggregate across all project processes. Large offload experiments belong on dedicated hardware after storage type/throughput and isolation are confirmed. Disk capacity alone does not establish feasibility.

The approximately 59.6-GiB estimate is 4 billion parameters times 16 bytes for FP32 weights, gradients and two Adam moments. It excludes activations, temporary buffers and checkpoint loading. It is not a universal lower bound for every possible optimizer/precision/offload method. CUDA precision is explicit (`precision: bfloat16` or `float32`); default is FP32, and actual optimizer storage must be profiled; the current MedGemma preflight is a conservative FP32 reference check, not an allocator or a proven CUDA fit estimator. Setting a larger budget value does not create or reserve memory.

## Hardware acceptance record

Record GPU model/count/VRAM, CUDA driver and torch compatibility, BF16 support, RAM available, CPU allocation, disk type/free space, dedicated scratch path and I/O restrictions. Obtain permission for model access and source reuse without placing tokens in configs or Git. Record the accepted MedGemma base revision and verify downloaded file hashes. Check the official model card: https://developers.google.com/health-ai-developer-foundations/medgemma/model-card .

Keep a dedicated training environment separate from the API/VPS. Lock dependencies from `uv.lock`; install `--extra llm --extra dev`. Confirm the platform's torch build matches the GPU and avoid silently replacing a working shared runtime. The current lock was tested with CPU torch locally; GPU driver compatibility is still a hardware acceptance step.

## Before the first expensive run

1. Run `python scripts/prepare_teacher_corpus.py` and review the printed split counts and hashes.
2. Complete genuine review records and export the approved corpus using the README command. Run the exporter again after any case correction.
3. Run `pytest -q tests/test_distillation_torch.py tests/test_teacher_package.py`. These tiny-model tests do not download MedGemma.
4. Freeze prompt template, output contract, tokenizer revision, evidence bundle and review identities. Confirm no unreviewed draft enters training.
5. Tokenize all approved examples with the actual tokenizer. The current trainer rejects overlength examples; shorten with review rather than silently dropping clinically relevant evidence.
6. Measure the unchanged base model on validation and the separate development checks. Keep the locked clinical test set inaccessible during tuning.
7. On the dedicated training machine, profile a short subset using a new output directory, fixed seed, one example per step and a short sequence. Record peak host/GPU memory, wall time, loss and tokens/second. The current trainer evaluates held-out loss after each run; use development-only fixture splits for hardware profiling, not the locked clinical test cohort.
8. Select memory strategy from measurements: native full-weight training if it fits; otherwise implement/test a pinned DeepSpeed/FSDP integration on the dedicated machine. Do not claim offload support before a real round-trip and recovery test.

## Candidate configuration

Create a private JSON configuration from these fields after the hardware and corpus gates pass:

```json
{
  "student": "google/medgemma-1.5-4b-it",
  "revision": "91850547d9f0b2fdd21aa7c5f4f3d1a8a52c243b",
  "corpus": "data/teacher-approved/hfref-v1.jsonl",
  "output": "artifacts/hfref-full-v1",
  "model_permission_reference": "REPLACE_WITH_REAL_APPROVAL_REFERENCE",
  "method": "full",
  "device": "cuda",
  "precision": "bfloat16",
  "memory_budget_gib": 6,
  "epochs": 1,
  "learning_rate": 0.000005,
  "max_tokens": 1024,
  "seed": 42
}
```

This is deliberately NOT launch-ready: replace the permission reference and set a measured hardware budget; 6 GiB is rejected for MedGemma. The small learning rate is a candidate, not an established optimum. Try a prespecified validation-only sweep of 1e-6, 5e-6 and 1e-5 after the pilot; retain the unchanged baseline if all candidates regress. Compare fixed seeds and select using clinical validation metrics as well as loss.

Launch with `python scripts/distill.py --config PATH`. The runner masks prompt tokens, trains on completions, selects the best validation checkpoint including the initial checkpoint, reloads it and measures test completion loss. It saves weights/tokenizer and hashes. Full mode updates all parameters that receive gradients; the text-only workload does not exercise the vision branch. Do not claim that visual reasoning improved from text training.

## Recovery and limitations

The current runner stores the best model checkpoint but does not persist Adam state, RNG state or an exact mid-epoch resume cursor. An interrupted run must restart into a new output directory; loading its weights is not equivalent to exact training resume. Implement and test optimizer/RNG/scheduler/data-cursor restoration before a long production training job. Likewise, gradient accumulation, distributed/offloaded training and automated generative clinical evaluation remain additional runtime work, not hidden working capabilities.

Never delete prior evidence to reuse a directory. Record failures, observed peak memory, the last completed epoch and the hash of any retained checkpoint. Before publishing a model, require structured-generation evaluation, blind clinical review, source/permission checks and a model card. Do not automatically deploy the lowest-loss model.

## Hostinger's role now

Keep the shared VPS available for light orchestration or future bounded tabular experiments. No model installation, disk offload or training service is required there to prepare this corpus. CI validates source code and synthetic fixtures remotely. Future training CI should dispatch an explicitly approved GPU job, preserve evidence artifacts and require model promotion checks; it should not train on every source-code push.
