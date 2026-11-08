# Before renting a GPU

Start with the [hybrid training plan](HYBRID_TRAINING.md): adapter-first LoRA/QLoRA, then optional full-weight escalation. Profile both host RAM and dedicated VRAM. The full-weight sizing below does not apply to QLoRA, and no GPU fit has yet been measured.

The corpus contains 300 synthetic drafts across 60 families, not 300 independent or clinically approved cases. Do not rent compute based on row count alone.

1. Complete the clinical/source review and export an approved immutable corpus. Include complete actionable cases; current drafts do not train numerical prescribing.
2. Verify model access and cache the pinned tokenizer/weights on approved storage before the paid slot where possible. Confirm transfer size and the rental storage lifecycle.
3. Run all software tests locally. Validate JSON, source references, hashes, family splits and actual tokenizer lengths; inspect semantic leakage manually.
4. Freeze the base comparison, validation selection criteria and independent clinical challenge set. Keep research and clinical claims separate.
5. Verify dedicated VRAM with `nvidia-smi --query-gpu=name,memory.total --format=csv`. NVIDIA lists RTX 4050 Laptop GPU at 6 GB; shared system memory is not additional dedicated VRAM. A displayed total of 14 GB is not proof of a 14-GB GPU. This laptop can support smaller experiments; full-weight MedGemma fit is not established.
6. Select a rental with measured memory headroom for the chosen precision/optimizer, sufficient host RAM and checkpoint storage. The current full-weight path is not tested with disk offload. Prefer evaluating 80-GB-class capacity for the initial non-offloaded profile, not assuming 6 GB fits. Check actual stock, driver compatibility and prices before purchase.
7. Set a maximum spending window and start with a short profiling run. Model download, initialization, validation and checkpoint export take real time; zero setup overhead cannot be promised.
8. Export checkpoints and logs, verify hashes and restoration, then destroy the paid instance only after confirming the export. Hostinger states billing continues while an instance exists, including idle time, and rounds usage up to whole hours.

Sources checked: https://www.nvidia.com/en-us/geforce/laptops/40-series/ and https://www.hostinger.com/gpu-hosting . No GPU has been rented or charged by this work.
