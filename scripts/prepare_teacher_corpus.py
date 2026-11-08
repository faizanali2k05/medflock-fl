"""Validate synthetic drafts; export only an explicitly reviewed, hash-bound corpus."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from medflock.distillation import load_corpus


def case_hash(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()


def validate(path):
    rows = load_corpus(path)
    families = {}
    for row in rows:
        family = row["scenario_family"]
        if families.setdefault(family, row["split"]) != row["split"]:
            raise ValueError("Scenario family crosses splits")
        response = json.loads(row["response"])
        required = {
            "status",
            "assessment",
            "missing_information",
            "proposed_actions",
            "prescription_draft",
            "medication_assessment",
            "not_recommended",
            "citations",
            "clinician_review_required",
        }
        if set(response) != required:
            raise ValueError("Unexpected teacher response fields")
        if response["status"] not in {
            "DRAFT_FOR_REVIEW",
            "NEEDS_INFORMATION",
            "OUT_OF_SCOPE",
            "URGENT_REVIEW",
            "VALIDATION_FAILED",
        }:
            raise ValueError("Unknown response status")
        if response["clinician_review_required"] is not True:
            raise ValueError("Clinical review cannot be bypassed")
        if response["prescription_draft"] or response["medication_assessment"] != "not_assessed":
            raise ValueError("This seed package has no approved medication rule source")
        if not set(response["citations"]).issubset(row["source_ids"]):
            raise ValueError("Unsupported response citation")
    return rows


def export_reviewed(rows, reviews, output):
    if output.exists():
        raise ValueError("Use a new corpus path")
    indexed = {review["case_id"]: review for review in reviews}
    if len(indexed) != len(reviews):
        raise ValueError("Duplicate review records")
    selected = []
    for row in rows:
        review = indexed.get(row["case_id"], {})
        if review.get("decision") != "approve":
            raise ValueError(f"Case {row['case_id']} lacks approval")
        if review.get("case_sha256") != case_hash(row):
            raise ValueError("Review does not match current case contents")
        for field in [
            "reviewer_id",
            "professional_registration",
            "reviewed_at",
            "source_adoption_reference",
            "findings",
        ]:
            if not isinstance(review.get(field), str) or not review[field].strip():
                raise ValueError(f"Review is missing {field}")
        if review.get("corrected_response") is not None:
            raise ValueError("Apply corrections to the draft and review its new hash")
        selected.append({**row, "review_status": "approved", "reviewer_id": review["reviewer_id"]})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(json.dumps(row) for row in selected) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--drafts", type=Path, default=Path("training/cardiology/teacher-drafts.jsonl")
    )
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = validate(args.drafts)
    if bool(args.reviews) != bool(args.output):
        parser.error("Export requires both --reviews and --output")
    if args.output:
        export_reviewed(rows, json.loads(args.reviews.read_text(encoding="utf-8")), args.output)
    print(
        json.dumps(
            {
                "cases": len(rows),
                "splits": dict(Counter(row["split"] for row in rows)),
                "clinical_validation": False,
                "case_hashes": {row["case_id"]: case_hash(row) for row in rows},
            },
            indent=2,
        )
    )
