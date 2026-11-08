# Curriculum and reviewer work queue

The initial goal is useful, evidence-grounded stable adult HFrEF review. Broad cardiology diagnosis, acute inpatient prescribing, pediatric/pregnancy treatment, ECG interpretation and autonomous orders are separate tasks.

## Planned dataset composition

Planning target: 600 independently authored and reviewed development cases, not 600 paraphrases. Start with 100 adjudicated cases and inspect coverage before expanding. A provisional composition is 300 training, 100 validation and 200 locked evaluation cases; exact sample sizes must follow a clinician/statistician's precision and safety analysis. The 300 draft examples across 60 families are separate development scaffolding and must not be counted as 300 validated patients.

| Module | Suggested cases | Required variation and reviewer questions |
| --- | ---: | --- |
| Record reconciliation | 80 | Absent/contradictory units, dates, doses, patient identity, multiple prescriptions, duplicate imports; does the answer preserve uncertainty? |
| Stable regimen review | 120 | Adequate versus incomplete therapy; eligibility, tolerability, contraindication and access constraints; does it identify a specific supported action rather than a generic refusal? |
| Renal/electrolyte context | 70 | Baseline versus changing results, stale labs, missing units, linked versus wrong-patient reports; does it use the adopted thresholds correctly? |
| Hemodynamics and symptoms | 60 | Stable observations, symptomatic intolerance, evolving symptoms, contradictory history; does urgency override routine optimization? |
| Polypharmacy and reconciliation | 70 | Duplicate therapy, uncertain use, interaction coverage gaps and recent changes; pharmacist adjudicates each actual medicine rule. |
| Adherence/access/preferences | 60 | Cost, unavailable formulation, work schedule, health literacy and patient priorities; recommendations must remain feasible and evidence-supported. |
| Out-of-scope and urgent cases | 60 | Acute deterioration, pregnancy, pediatric and different HF subtype; avoid both missed escalation and indiscriminate escalation. |
| Evidence/security/language | 80 | Source conflict, fabricated citation pressure, prompt injection, unlinked imaging, English/Urdu/Roman Urdu; translated variants stay in the same split. |

## Medication case authoring worksheet

For every adopted medication pathway, prepare positive eligibility, true contraindication, missing prerequisite, stale prerequisite, intolerance, access limitation, monitoring and alternative-option cases. A cardiologist/pharmacist must supply the actual values and adopted references; this document does not invent cutoffs.

Required source fields: generic drug and formulation, indication/population, starting and target-dose options with units, route/frequency, titration conditions, renal/hepatic adjustments, contraindications, interaction coverage, switching/washout rules where applicable, monitoring variables and intervals, urgent escalation rules, source/version and local formulary mapping. Each numerical output must be traceable to an approved rule and patient inputs. Missing coverage must remain visible.

Required case fields: current treatment and actual use, symptom/observation trajectory, relevant laboratory results and dates, prior intolerance, allergies/reactions, competing conditions, patient preferences and formulary. Expected output must distinguish an action that is eligible now from one conditional on further information.

Until that worksheet is completed and reviewed, examples may propose a focused treatment review but cannot populate prescription fields. Current draft validation intentionally rejects nonempty prescriptions. Extend the validator and medication tests together when the clinical source is approved.

## Meaningful paired examples

Author counterfactual pairs that change exactly one clinically relevant input: current versus stale lab, verified versus mismatched identity, stable versus acute symptoms, available versus unavailable formulation, documented absence versus unknown allergy. Ask whether the output changes in the expected way. Keep each pair in one split to prevent leakage.

Include positive controls where all required information exists and the clinician expects a concrete action. Include negative controls where an action must be withheld. Reward appropriate action and appropriate restraint separately; a model that always refuses should fail usefulness evaluation.

## Pakistan adaptation

Use verified local generic/formulation availability and approved institution-specific formularies. Do not infer availability from overseas guidelines or marketplace search snippets. Include affordability and access without making up prices. Ask a qualified bilingual reviewer to assess Urdu/Roman Urdu medical meaning, negation, units and readability. Do not translate doses freely. Record the institution's adopted emergency pathway without inventing a universal local phone number.

## Review rubric

Score each of factual grounding, missing-data recognition, urgency/scope, action relevance, source support, medication-rule compliance and communication from 0 (wrong/absent) to 2 (correct and complete). Record critical errors separately: invented facts/doses, missed urgent escalation, contraindicated proposed action, wrong-patient use, fabricated evidence and bypassed approval. A high total cannot cancel a critical error. Two independent reviewers should adjudicate medication and urgent cases; reviewer agreement and reasons for revisions are retained.
