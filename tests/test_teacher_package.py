import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = runpy.run_path(str(ROOT / "scripts/prepare_teacher_corpus.py"))
DRAFTS = ROOT / "training/cardiology/teacher-drafts.jsonl"


def test_seed_package_is_explicitly_unreviewed():
    rows = TOOLS["validate"](DRAFTS)
    assert len(rows) == 300
    assert len({row["scenario_family"] for row in rows}) == 60
    assert {row["review_status"] for row in rows} == {"unreviewed"}
    assert all(row["privacy"] == "synthetic" for row in rows)


def test_export_requires_current_hash_bound_review(tmp_path):
    rows = TOOLS["validate"](DRAFTS)
    target = tmp_path / "approved.jsonl"
    with pytest.raises(ValueError, match="lacks approval"):
        TOOLS["export_reviewed"](rows, [], target)
    reviews = [
        {
            "case_id": row["case_id"],
            "case_sha256": TOOLS["case_hash"](row),
            "decision": "approve",
            "reviewer_id": "test-fixture-not-real-review",
            "professional_registration": "synthetic-test-only",
            "reviewed_at": "2026-10-20",
            "source_adoption_reference": "fixture",
            "findings": "synthetic fixture for export testing",
        }
        for row in rows
    ]
    reviews[0]["case_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="current case"):
        TOOLS["export_reviewed"](rows, reviews, target)
    assert not target.exists()
    reviews[0]["case_sha256"] = TOOLS["case_hash"](rows[0])
    TOOLS["export_reviewed"](rows, reviews, target)
    exported = [json.loads(line) for line in target.read_text().splitlines()]
    assert all(row["review_status"] == "approved" for row in exported)
    with pytest.raises(ValueError, match="new corpus"):
        TOOLS["export_reviewed"](rows, reviews, target)


def test_unreviewed_drafts_cannot_enter_training(tmp_path):
    pytest.importorskip("torch")
    from medflock.distillation import run

    with pytest.raises(ValueError, match="explicitly approved"):
        run(
            {
                "student": "fixture/not-downloaded",
                "revision": "a" * 40,
                "corpus": str(DRAFTS),
                "output": str(tmp_path / "model"),
                "model_permission_reference": "test fixture only",
            }
        )


def test_variants_stay_with_family_and_citations_match():
    rows = TOOLS["validate"](DRAFTS)
    groups = {}
    for row in rows:
        groups.setdefault(row["scenario_family"], set()).add(row["split"])
        answer = json.loads(row["response"])
        for action in answer["proposed_actions"]:
            assert set(action["evidence_ids"]).issubset(row["source_ids"])
    assert all(len(splits) == 1 for splits in groups.values())
    assert len({row["prompt"] for row in rows}) == len(rows)
    report = json.loads((DRAFTS.parent / "coverage.json").read_text())
    assert report["reviewed_cases"] == 0
    assert report["train_ready"] is False
