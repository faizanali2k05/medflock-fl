> Updated 24 October 2026: adapter-first LoRA/QLoRA with optional explicit full-weight consolidation is authorized. See [hybrid training](../training/cardiology/HYBRID_TRAINING.md). Tiny-model tests cover LoRA-to-full escalation; CUDA QLoRA and actual MedGemma training remain unverified. No medical-model quality or clinical validation is implied.

# Clinical and deployment readiness

This is a research beta. Implemented preparation is not evidence of clinical effectiveness or an authorized hospital deployment.

| Track | Implemented and locally exercised | Required external evidence |
| --- | --- | --- |
| Distillation | Completion-only LoRA, immutable remote revisions, patient-disjoint splits, validation checkpoint selection, held-out loss, teacher provenance; tiny GPT-2 and Gemma 3 integration tests | Authorized medical model weights, licensed teacher corpus and evidence, GPU capacity, clinician review |
| Clinical evaluation | Frozen cohort hashes, bootstrap intervals, calibration, subgroup summaries, statistical gates and separate clinician review records | Independent cohort, verified prediction provenance, prespecified clinical thresholds, qualified reviewer |
| Image and ECG | Image feature baseline and raw-waveform feature adapter with versioned semantics and local manifests | Cleared patient grouping, modality-specific labels and external evaluation; raw ECG signals are not available yet |
| Deployment | Isolated VPS Compose bundle, resource limits, least-privilege database role, read-only preflight, TLS Flower node enrollment and local bundle preparation | SSH access, capacity inspection, DNS/proxy agreement, backup restore exercise, hospital authorization |

## Distillation workflow

Install the optional training dependencies with `uv sync --locked --extra dev --extra llm` on the training machine. The API/VPS image does not require these packages. Run `python scripts/llm_smoke.py` for a synthetic transformer integration exercise. This does not train a medical model.

The first medical student candidate remains `google/medgemma-1.5-4b-it`, pinned to revision `91850547d9f0b2fdd21aa7c5f4f3d1a8a52c243b`. Model access and applicable terms must be accepted by the owner before downloading. See the [model card](https://developers.google.com/health-ai-developer-foundations/medgemma/model-card). No acceptance is inferred from a configuration value.

`python scripts/generate_teacher.py --help` describes local teacher generation. Each case supplies evidence and a privacy declaration. Generated JSON and citations are structurally checked; factual accuracy still needs review. Teacher agreement is not clinical truth.

`python scripts/distill.py --config PATH` accepts a JSON object containing `student`, `revision`, `corpus`, `output`, `model_permission_reference`, and optional `device`, `epochs`, `learning_rate`, `max_tokens`, `rank`, `seed`. Use a new output directory for each run. The JSONL corpus requires `case_id`, `patient_group`, `split` (train/validation/test), `prompt`, `response`, `teacher`, `teacher_revision`, `permission_reference`, `privacy` (synthetic/approved_deidentified), `source_ids` and `citations` lists.

Patient groups and identical prompts cannot cross splits. Prompt tokens are excluded from the loss. The initial adapter is retained if training does not improve validation loss; test loss is measured after checkpoint selection. Reports preserve corpus and artifact hashes. Loss improvement alone does not authorize clinical use. The standalone token-KL utility requires identical vocabulary and alignment; the medical training entry point uses sequence distillation, not cross-tokenizer logit matching. Federated aggregation of these LLM adapters is not wired into dashboard training yet.

## Clinical evaluation workflow

Run `python scripts/evaluate_clinical.py --help` for offline evaluation. Prediction CSV columns are `patient_hash`, `label`, `score`, `site`, with optional `sex` and `age_group`. Use institution-controlled pseudonyms, not plain hashes of guessable identifiers. Supply training patient hashes to check overlap; absent lineage is explicitly reported as unchecked.

`EvaluationPlan` in `src/medflock/validation.py` defines the frozen task/model/cohort hashes, independence declaration, decision threshold, sample requirements and statistical acceptance thresholds. Agree these before examining results. The evaluator accepts supplied predictions: their actual generation by the stated model requires independently retained provenance. It cannot establish independence from a declaration alone.

Authenticated operators can POST multipart data to `/api/validation/evaluate`; researchers can GET `/api/validation/reports`. Reviews at `/api/validation/reviews` require an OIDC principal with both researcher and clinician roles. Assign clinician access only after verifying qualifications. Shared operator keys cannot approve clinical evidence. Review records do not authorize release; no medication safety or prescription capability is enabled.

## Modality workflow

Run `python scripts/adapt_modality.py --help`. Manifests refer only to files beneath the supplied local root. Each record requires a binary label, patient group and explicit privacy clearance. Image preprocessing produces 19 interpretable statistical features, not a trained diagnostic vision encoder. Raw ECG inputs are finite NumPy arrays with declared ordered leads, sampling frequency and millivolt units. They produce five summary features per lead, not a validated arrhythmia model. Different preprocessing or lead semantics change the feature contract.

Exact duplicates are removed; conflicting labels or patient assignments are rejected. Near duplicates and printed identifiers still require review. The available Pakistan ECG archive contains report photographs: 928 files, 491 unique contents in the earlier inventory. It cannot be treated as raw waveform data or linked to CSV patients without evidence. The review-only KEMU material is excluded. Privacy clearance and patient grouping remain prerequisites for real training.

## VPS and hospital preparation

The VPS already hosts other applications. Nothing here connects to it or changes its proxy, firewall or workloads. `scripts/prepare_hostinger.py --image registry.gitlab.com/mashhood0x7e-group/medflock-fl:FULL_COMMIT --output runtime/deployment/hostinger` produces an ignored local bundle and private `.env` without printing credentials. Only use a commit whose container publication and checks succeeded.

Before deployment, run the bundle's `preflight.sh` read-only on the host and inspect existing services, ports, free memory and disk. Review the proposed combined limits (2 CPU cores and about 3.75 GiB RAM), plus host overhead, against current usage. API binds loopback port 18088; PostgreSQL has no host port. Retain existing apps and configure only an agreed dedicated TLS hostname using the provided nginx snippet. The VPS is a coordinator/API candidate; GPU training capacity is unconfirmed.

After authorized deployment, `sh verify.sh` checks readiness and anonymous GraphQL rejection; pass a changed port as its first argument. `backup.sh` pauses only this Compose project's API and worker while copying the database and artifacts. Before a hospital pilot, restore that pair into a separately named disposable Compose project with different ports, verify artifact hashes and model loading, and record the result. Backup/restore and capacity behavior have not been exercised on the VPS. Never use `down -v` on the live project. Rollback requires a compatible image and schema; retain a pre-upgrade backup.

Hospital Compose files are separate from the VPS web stack. Use a private/VPN fleet address, managed TLS certificates and enrolled node public keys. `scripts/generate_node_identity.py` generates a node key locally; keep private keys at the node. `scripts/prepare_hospital_node.py` applies the agreed coordinator feature contract locally and currently supports the logistic runtime. `scripts/flower_spike.py --tls --dataset data/heart_failure.csv` exercises three authenticated local nodes; its ephemeral loopback certificates are test-only. This is not an independent hospital federation and is not connected to dashboard orchestration.

## Remaining release gates

No real medical-model distillation, independent clinical validation or hospital deployment has occurred. The owner deferred VPS access until preparation is ready. We still need permissioned weights and teacher cases, suitable training hardware, a cleared independent cohort, clinician availability, hospital authorization and the later SSH/domain/proxy details. Synthetic tests demonstrate software behavior only.
