# Cardiology distillation preparation package

Prepared 20 October 2026. Scope: clinician-facing review of adults with established, stable outpatient HFrEF. Student: MedGemma 1.5 4B; adapter-first sequence distillation with optional full-weight consolidation (see HYBRID_TRAINING.md). Teacher: assistant-authored examples with explicit provenance, followed by independent clinical review. This package is an engineering and reviewer handoff, not a validated clinical corpus or a completed medical training run.

## Files and commands

- `teacher-drafts.jsonl`: 300 synthetic drafts across 60 authored scenario families, complete prompts, structured target answers, case/family IDs, frozen draft splits, source IDs, review status, expected and prohibited behaviors.
- `sources.json`: candidate source register. A URL is not approval for adoption or reuse.
- `review-template.json`: fields required for each clinical review. Fill real reviewer details; never manufacture approval.
- `EVALUATION.md`: baseline comparisons, scoring and release evidence.
- `GPU_RUNBOOK.md`: environment, hardware profiling, launch and recovery requirements.
- `CURRICULUM.md`: detailed expansion plan for therapeutic cases and Pakistan context.

From the repository root:

```powershell
.venv/Scripts/python.exe scripts/prepare_teacher_corpus.py
```

This validates provenance, split separation, output fields and the currently empty prescription channel. It prints case hashes for reviewer binding. It does not download model weights or contact the VPS.

Store a JSON array of completed reviews in a private local path. After review:

```powershell
.venv/Scripts/python.exe scripts/prepare_teacher_corpus.py --reviews data/reviews/hfref-reviews.json --output data/teacher-approved/hfref-v1.jsonl
```

All cases must have matching hash-bound approvals before this export succeeds. Corrections change the draft and invalidate the old hash. The tool checks record completeness, not a reviewer's identity or clinical competence; identity verification and source adoption remain external responsibilities. A clinical lead must resolve disagreements. The exported corpus includes all splits; the trainer only optimizes on `train` and uses validation for checkpoint selection. Never publish real patient records in this folder.

## Input contract

Every case describes an encounter time, adult status, confirmed diagnosis/subtype, symptoms and changes, relevant history, EF and date, BP/heart rate/weight with units and dates, renal function/potassium with units and dates, medication names/doses/formulation/route/frequency, adherence, allergies and reaction details, comorbidities, preferences and formulary/access constraints. Unknown fields stay unknown. A source report and its patient linkage are separate evidence requirements. Synthetic cases intentionally omit some fields to test behavior.

The model receives only the record and explicitly supplied evidence. Do not add hidden target facts to a prompt. Structured lab parsing, unit conversion and validated calculators should occur outside the LLM. No private chain-of-thought is collected; targets contain concise patient-specific explanations and source references.

## Output contract

`status`: DRAFT_FOR_REVIEW, NEEDS_INFORMATION, OUT_OF_SCOPE, URGENT_REVIEW or VALIDATION_FAILED.

`assessment`: concise factual synthesis; distinguish reported facts from interpretation. `missing_information`: precise missing/stale/conflicting items and why they matter. `proposed_actions`: action, concise rationale and evidence IDs. `not_recommended`: unsupported actions and case-specific reasons. `citations`: only supplied evidence. `clinician_review_required`: always true. `prescription_draft`: empty in this seed release. `medication_assessment`: not_assessed until an approved rules source and clinician-reviewed prescribing cases exist.

A useful partial response is allowed: explain the specific problem, preserve reliable facts and identify the next decision. Do not collapse every case to a generic refusal. Conversely, a complete-looking JSON object is not proof of correct medicine.

## Teacher authoring workflow

1. Clinical lead selects an adopted pathway/version, local scope and source-use permissions.
2. Author an entirely fictional encounter or use explicitly cleared, de-identified clinical material within its authorized node. Keep patient-level grouping before any paraphrasing.
3. Supply evidence snippets with stable IDs, version/date and approved reuse status. Do not copy complete guidelines into training without permission.
4. Teacher writes the structured answer and expected/forbidden behaviors. Never treat teacher confidence as the label.
5. Reviewer checks factual grounding, clinically relevant omissions, urgency, action eligibility, evidence interpretation, monitoring and language. Pharmacist reviews medication-specific cases.
6. Adjudicate disputed cases, correct targets, hash the final case and record approval. Keep rejected drafts outside training exports.
7. Split by patient AND scenario family before generating variants. Translate or paraphrase only within that same split. Deduplicate normalized prompts and inspect semantic duplicates.
8. Freeze the corpus manifest and source versions. New data creates a new version; never silently append to a completed evaluation release.

The current 300 drafts contain 160 train, 65 validation and 75 test cases. There are 60 scenario families with five context variants each; no family crosses splits. They are a seed/smoke set, not sufficient coverage or an independent clinical benchmark. Because the same author made all splits, teacher bias remains shared. Create a separate clinician-authored locked challenge cohort before measuring clinical gains.

## Existing data boundaries

The Faisalabad 299-row CSV supports a separate risk task; it cannot supply treatment targets. The ECG collection is unlinked report images, not paired cardiac patient histories or raw signals. KEMU material stays review-only pending privacy/permission resolution. Observed prescriptions are not automatically optimal treatment labels. This corpus contains no copied patient records.

## Future datasets and federated nodes

Retain base-model revision, tokenizer hash, task/output schema, preprocessing revision, source versions and trainable-parameter layout as the training contract. New compatible data creates a versioned node snapshot. Validate schema, permissions, patient splits and source coverage before inclusion. A changed task/schema or model family requires a separate model lineage and evaluation; do not average incompatible tensors.

Full-weight 4B updates can be several gigabytes per node per round. Current Flower integration is logistic and does not implement full-weight MedGemma aggregation. Add chunked/checksummed transport, restart behavior and measured bandwidth tests before describing LLM training as federated. A central synthetic corpus experiment is explicitly centralized. Hospital records remain local; raw prompts and gradients both require privacy consideration, and federation alone does not guarantee privacy.

## Completion boundary

Prepared now: 300 draft examples, structured output expectations, source register, review/export tooling, curriculum, evaluation design and a GPU handoff. Still required: approved clinical sources and numerical medication rules, a substantial reviewed corpus, independent clinical challenge cases, model access, hardware-specific profiling and a trained/evaluated checkpoint. GPU availability does not automatically resolve these clinical gates.


## Expanded review package

`scenario-families.jsonl` preserves 60 distinct authored starting scenarios. `scripts/build_cardiology_drafts.py` deterministically creates five contexts per family: standard, remote access, language support, cost constraints and handoff. Each context changes the target action, not only a patient name. `coverage.json` reports family counts, exact uniqueness, status balance and corpus hash. Exact uniqueness does not prove semantic independence.

`CASEBOOK.md` presents all 300 drafts for human inspection. These cases still emphasize evidence, scope, reconciliation and appropriate review. They are not a dose-training dataset. There are only two urgent scenario families and three out-of-scope families; their ten/fifteen variants are not independent safety evidence. Positive complete prescribing cases remain a clinical-authoring priority before training a useful treatment assistant. Do not purchase compute merely because the file reached 300 rows.

`COMPUTE_READINESS.md` lists the pre-rental gates and hardware verification command. No GPU instance has been purchased or started.
