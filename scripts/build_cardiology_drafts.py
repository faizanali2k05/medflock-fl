"""Expand reviewed-in-future scenario families without presenting variants as independent cases."""

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "training/cardiology"
CONTEXTS = [
    ("standard", "The encounter has no additional communication or access constraints.", None),
    (
        "remote-access",
        "This is a remote encounter; the patient cannot attend the usual clinic this week.",
        (
            "Identify an accessible local clinical contact; remote access does"
            " not replace required assessment."
        ),
    ),
    (
        "language-support",
        (
            "The patient prefers Urdu; the current record is in English and no"
            " verified translation exists."
        ),
        (
            "Arrange qualified language support and confirm understanding "
            "without claiming an unreviewed translation is verified."
        ),
    ),
    (
        "cost-constraint",
        "The patient reports difficulty paying for care and asks which next step is essential.",
        (
            "Ask the care team to prioritize necessary assessment and "
            "affordable access without inventing prices or omitting essential "
            "care."
        ),
    ),
    (
        "handoff",
        (
            "Another care team will receive this encounter; no receipt or "
            "completed action is documented."
        ),
        (
            "Prepare a handoff separating documented facts, unresolved items "
            "and pending actions; do not mark transfer as completed."
        ),
    ),
]


def build():
    families = [
        json.loads(line) for line in (ROOT / "scenario-families.jsonl").read_text().splitlines()
    ]
    rows = []
    for index, base in enumerate(families, 1):
        for variation, context, action in CONTEXTS:
            row = dict(base)
            prompt = json.loads(base["prompt"])
            prompt["encounter_context"] = context
            answer = json.loads(base["response"])
            if action:
                if answer["status"] == "URGENT_REVIEW":
                    action = (
                        "Do not delay urgent assessment for these additional constraints. " + action
                    )
                answer["proposed_actions"].append(
                    {
                        "action": action,
                        "rationale": (
                            "The supplied encounter context affects how the next step can be "
                            "carried out."
                        ),
                        "evidence_ids": ["PROJECT_SCOPE_V1"],
                    }
                )
                if "PROJECT_SCOPE_V1" not in row["source_ids"]:
                    prompt["evidence"].append(
                        {
                            "id": "PROJECT_SCOPE_V1",
                            "text": (
                                "Respect communication and access needs without inventing facts, "
                                "orders or approvals."
                            ),
                        }
                    )
                    row["source_ids"] = [*row["source_ids"], "PROJECT_SCOPE_V1"]
                    row["citations"] = [*row["citations"], "PROJECT_SCOPE_V1"]
                    answer["citations"].append("PROJECT_SCOPE_V1")
            row.update(
                case_id=f"hfref-v2-{index:03}-{variation}",
                variant=variation,
                prompt=json.dumps(prompt),
                response=json.dumps(answer),
                review_status="unreviewed",
                reviewer_id=None,
                required_behavior=[*base["required_behavior"], *([action] if action else [])],
                provenance=(
                    "Original family plus deterministic context variation; not an "
                    "independent clinical case"
                ),
            )
            rows.append(row)
    content = "\n".join(json.dumps(row) for row in rows) + "\n"
    (ROOT / "teacher-drafts.jsonl").write_text(content, encoding="utf-8", newline="\n")
    report = {
        "draft_cases": len(rows),
        "scenario_families": len(families),
        "independent_clinical_cases": 0,
        "reviewed_cases": 0,
        "splits": dict(Counter(row["split"] for row in rows)),
        "family_splits": dict(Counter(row["split"] for row in families)),
        "statuses": dict(Counter(json.loads(row["response"])["status"] for row in rows)),
        "unique_prompts": len({row["prompt"] for row in rows}),
        "unique_responses": len({row["response"] for row in rows}),
        "corpus_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "train_ready": False,
        "limits": [
            "Unreviewed synthetic drafts",
            "No validated dose/order targets",
            "Context variants share a family",
            "Not an independent clinical benchmark",
        ],
    }
    (ROOT / "coverage.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
