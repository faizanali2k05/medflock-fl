"""External-cohort evaluation produces evidence; it never grants clinical approval."""

import hashlib
import io
import json

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


class EvaluationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    task_id: str = Field(min_length=1)
    model_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    cohort_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    cohort_source: str = Field(min_length=3)
    independence_declaration: str = Field(min_length=20)
    threshold: float = Field(gt=0, lt=1)
    minimum_patients: int = Field(ge=40)
    minimum_events: int = Field(ge=10)
    auroc_lower_bound: float = Field(gt=0, lt=1)
    sensitivity_lower_bound: float = Field(gt=0, lt=1)
    maximum_brier: float = Field(gt=0, lt=1)
    bootstrap_samples: int = Field(default=1000, ge=200, le=2000)
    seed: int = 42


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def metrics(labels, scores, threshold):
    positive = scores >= threshold
    tp = int(((labels == 1) & positive).sum())
    tn = int(((labels == 0) & ~positive).sum())
    fp = int(((labels == 0) & positive).sum())
    fn = int(((labels == 1) & ~positive).sum())
    both = len(np.unique(labels)) == 2
    return {
        "patients": len(labels),
        "events": int(labels.sum()),
        "auroc": float(roc_auc_score(labels, scores)) if both else None,
        "average_precision": float(average_precision_score(labels, scores)) if both else None,
        "brier": float(brier_score_loss(labels, scores)),
        "sensitivity": tp / (tp + fn) if tp + fn else None,
        "specificity": tn / (tn + fp) if tn + fp else None,
        "ppv": tp / (tp + fp) if tp + fp else None,
        "npv": tn / (tn + fn) if tn + fn else None,
        "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
    }


def evaluate_cohort(contents, plan, training_patient_hashes=()):
    plan = EvaluationPlan.model_validate(plan)
    if hashlib.sha256(contents).hexdigest() != plan.cohort_sha256:
        raise ValueError("Evaluation cohort differs from the locked plan")
    frame = pd.read_csv(io.BytesIO(contents), dtype={"patient_hash": str})
    if not 40 <= len(frame) <= 5000:
        raise ValueError("Evaluation supports 40–5000 patients per report")
    if not {"patient_hash", "label", "score", "site"}.issubset(frame.columns):
        raise ValueError("Required columns: patient_hash,label,score,site")
    if not frame.patient_hash.str.fullmatch(r"[a-f0-9]{64}").fillna(False).all():
        raise ValueError("Use site-issued pseudonymous patient hashes, never names or MRNs")
    if frame.patient_hash.duplicated().any():
        raise ValueError("One prespecified index encounter per patient is required")
    if set(frame.patient_hash) & set(training_patient_hashes):
        raise ValueError("Evaluation patients overlap training lineage")
    labels = frame.label.to_numpy(dtype=float)
    scores = frame.score.to_numpy(dtype=float)
    if not np.isin(labels, [0, 1]).all() or not np.isfinite(scores).all():
        raise ValueError("Labels and scores must be finite and labels binary")
    if not ((scores >= 0) & (scores <= 1)).all() or frame.site.isna().any():
        raise ValueError("Scores must be probabilities and site identifiers complete")
    if len(np.unique(labels)) != 2:
        raise ValueError("Both outcomes are required")
    rng = np.random.default_rng(plan.seed)
    samples = {name: [] for name in ["auroc", "sensitivity", "specificity", "brier"]}
    for _ in range(plan.bootstrap_samples):
        indices = rng.integers(0, len(labels), len(labels))
        row = metrics(labels[indices], scores[indices], plan.threshold)
        for key in samples:
            if row[key] is not None:
                samples[key].append(row[key])
    intervals = {
        key: np.quantile(values, [0.025, 0.975]).tolist() for key, values in samples.items()
    }
    summary = metrics(labels, scores, plan.threshold)
    checks = {
        "sample_size": len(labels) >= plan.minimum_patients,
        "event_count": int(labels.sum()) >= plan.minimum_events,
        "non_event_count": int((labels == 0).sum()) >= plan.minimum_events,
        "discrimination": intervals["auroc"][0] >= plan.auroc_lower_bound,
        "sensitivity": intervals["sensitivity"][0] >= plan.sensitivity_lower_bound,
        "brier": intervals["brier"][1] <= plan.maximum_brier,
    }
    calibration = []
    for lower, upper in zip(np.linspace(0, 0.9, 10), np.linspace(0.1, 1, 10)):
        selected = (scores >= lower) & ((scores < upper) if upper < 1 else (scores <= upper))
        if selected.any():
            calibration.append(
                {
                    "lower": float(lower),
                    "upper": float(upper),
                    "count": int(selected.sum()),
                    "predicted": float(scores[selected].mean()),
                    "observed": float(labels[selected].mean()),
                }
            )
    groups = {}
    for column in ["site", "sex_group", "age_group"]:
        if column in frame:
            groups[column] = {}
            for name, indices in frame.groupby(column, dropna=False).groups.items():
                if len(indices) < 10:
                    groups[column][str(name)] = {"status": "suppressed_small_group"}
                else:
                    groups[column][str(name)] = metrics(
                        labels[indices], scores[indices], plan.threshold
                    )
    report = {
        "plan": plan.model_dump(),
        "plan_hash": digest(plan.model_dump()),
        "metrics": summary,
        "bootstrap_95_percent": intervals,
        "calibration": calibration,
        "subgroups": groups,
        "statistical_checks": checks,
        "statistical_gate": "passed" if all(checks.values()) else "failed",
        "clinical_status": "awaiting_independent_clinical_review",
        "lineage_overlap_checked": bool(training_patient_hashes),
        "limitations": [
            "Independence and label quality require external verification",
            "Bootstrap intervals assume independent patients, not independent hospitals",
            "Passing numerical thresholds does not authorize patient care",
        ],
    }
    report["report_hash"] = digest(report)
    return report
