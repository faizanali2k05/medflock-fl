"""Evaluate a frozen external-cohort prediction file against predeclared thresholds."""

import argparse
import json
from pathlib import Path

from medflock.validation import evaluate_cohort

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--training-patient-hashes", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Choose a new report path; prior evidence must remain intact")
    hashes = (
        args.training_patient_hashes.read_text().splitlines()
        if args.training_patient_hashes
        else []
    )
    report = evaluate_cohort(
        args.predictions.read_bytes(), json.loads(args.plan.read_text()), hashes
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(report["statistical_gate"], report["clinical_status"])
