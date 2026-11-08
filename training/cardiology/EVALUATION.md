# Evaluation plan before clinical claims

## Comparators

Evaluate the unchanged MedGemma base, deterministic record/rule baseline, base plus the same approved retrieval/rules, and distilled model plus that identical retrieval/rules bundle. Hold prompt format, evidence availability and decoding settings fixed. This separates the effect of distillation from better retrieval. Test medication generation only when approved numerical rules and reviewer labels exist.

## Data separation

Development seed cases are visible to authors and useful for regression tests only. Freeze an independent clinician-authored challenge set with patient/family separation, including complete actionable records, complex comorbidity, local access constraints, urgent/out-of-scope cases and unavailable information. No prompt paraphrases, patient repeats, translated variants or near-duplicates may cross splits. Where feasible reserve a separate institution/time cohort for external assessment. Simulated clients are not independent hospital validation.

## Measurements

- Schema success: valid JSON and required field types; report denominator and failure examples.
- Grounding: unsupported patient-fact rate and correct handling of unknown/absent/stale/conflicting information.
- Citation correctness: supplied ID membership plus clinical support verified by a reviewer. Membership alone is not entailment.
- Clinical action relevance: reviewer-scored useful actions, omitted necessary actions, unsupported actions and inappropriate withholding.
- Urgency: confusion matrix for urgent/nonurgent cases and review of every missed urgent case; report both sensitivity and unnecessary escalation.
- Medication safety: coverage-aware rule checks, contraindicated actions, dose/unit/route/frequency errors, monitoring omissions and inappropriate interactions-clear claims. Untested coverage is not a pass.
- Communication: concise explanation, preserved uncertainty and bilingual meaning where reviewed.
- Systems: peak memory, total elapsed time, latency distribution, tokens/second, failure rate and checkpoint integrity on the actual hardware.

Use blind paired evaluation of base and candidate on the same cases; randomize display order. Retain original judgments and adjudication. Bootstrap confidence intervals by patient/scenario family, not by repeated generated answers. Show subgroup denominators; small subgroups cannot support confident fairness claims. Synthetic performance is reported separately from real-cohort performance.

## Provisional engineering gates

All required schema fields valid in the regression suite; no fabricated source ID; no silent loss of input units/dates; no training/test group overlap; no bypassed clinician approval. Every critical error triggers investigation. Zero errors in a small sample does not prove safety: with zero observed events in n independent cases, the rough 95% upper bound is about 3/n, under its independence assumptions.

Clinical thresholds and acceptable failure rates must be prespecified by the clinical lead before unblinding. Do not invent a pass threshold after looking at results. A lower completion loss or better similarity to teacher text is insufficient. An always-refusing model should fail usefulness despite having few medication errors.

## Required result artifacts

Base/tokenizer/checkpoint hashes; corpus/split/evidence hashes; reviewer and permission references; exact training config and package versions; hardware profile; validation selection history; generation outputs; scored errors and adjudication; statistical uncertainty; limitations and model-card scope. Retain baseline outputs so regression can be measured after future dataset additions.

## Repeated releases

New datasets require permission/schema/privacy checks and an immutable snapshot. Retrain a new lineage version, compare against both the original base and last accepted release, and run forgetting checks on earlier reviewed tasks. Keep a replay set with documented permission; do not grow it by silently pulling from the locked test set. Retire or rotate exposed challenge sets transparently rather than claiming them as fresh external validation.
