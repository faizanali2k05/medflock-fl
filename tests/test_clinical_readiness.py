import hashlib
import io
import json
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from medflock.api import create_app
from medflock.config import Settings
from medflock.distillation import load_corpus
from medflock.modalities import adapt, ecg_features
from medflock.security import Principal
from medflock.validation import evaluate_cohort


def cohort():
    frame = pd.DataFrame(
        {
            "patient_hash": [hashlib.sha256(str(i).encode()).hexdigest() for i in range(80)],
            "label": np.arange(80) % 2,
            "score": np.where(np.arange(80) % 2, 0.8, 0.2),
            "site": ["synthetic-site"] * 80,
        }
    )
    contents = frame.to_csv(index=False).encode()
    plan = {
        "task_id": "synthetic",
        "model_sha256": "a" * 64,
        "cohort_sha256": hashlib.sha256(contents).hexdigest(),
        "cohort_source": "synthetic integration fixture",
        "independence_declaration": "Synthetic independent patients for a software test only",
        "threshold": 0.5,
        "minimum_patients": 40,
        "minimum_events": 10,
        "auroc_lower_bound": 0.6,
        "sensitivity_lower_bound": 0.6,
        "maximum_brier": 0.2,
        "bootstrap_samples": 200,
    }
    return frame, contents, plan


def test_validation_never_grants_clinical_release():
    frame, contents, plan = cohort()
    report = evaluate_cohort(contents, plan)
    assert report["statistical_gate"] == "passed"
    assert report["clinical_status"] == "awaiting_independent_clinical_review"
    assert not report["lineage_overlap_checked"]
    assert report["metrics"]["auroc"] == 1
    with pytest.raises(ValueError, match="overlap"):
        evaluate_cohort(contents, plan, [frame.patient_hash.iloc[0]])
    with pytest.raises(ValueError, match="locked plan"):
        evaluate_cohort(contents + b"\n", plan)


def test_validation_rejects_duplicates_and_failed_thresholds():
    frame, contents, plan = cohort()
    frame.loc[1, "patient_hash"] = frame.loc[0, "patient_hash"]
    duplicate = frame.to_csv(index=False).encode()
    plan["cohort_sha256"] = hashlib.sha256(duplicate).hexdigest()
    with pytest.raises(ValueError, match="One prespecified"):
        evaluate_cohort(duplicate, plan)
    _, contents, plan = cohort()
    plan["minimum_patients"] = 100
    assert evaluate_cohort(contents, plan)["statistical_gate"] == "failed"


def test_operator_cannot_impersonate_clinician(dataset, tmp_path):
    with pytest.raises(HTTPException) as error:
        Principal("operator", frozenset({"operator"})).require("clinician")
    assert error.value.status_code == 403
    settings = replace(Settings.load(), embedded_worker=False)
    app = create_app(
        f"sqlite:///{tmp_path / 'clinical.db'}", dataset, tmp_path / "artifacts", settings
    )
    with TestClient(app) as client:
        result = client.post(
            "/api/validation/reviews",
            json={
                "report_hash": "a" * 64,
                "decision": "accept_for_pilot_review",
                "professional_registration": "synthetic-test",
                "evidence_reference": "synthetic-test",
                "findings": "This is only a synthetic software test.",
            },
        )
        assert result.status_code == 403


def test_image_adapter_reuses_versioned_training_contract(tmp_path):
    records = []
    rng = np.random.default_rng(4)
    for index in range(60):
        path = tmp_path / f"image-{index}.png"
        Image.fromarray(rng.integers(0, 255, (32, 32), dtype=np.uint8)).save(path)
        records.append(
            {
                "path": path.name,
                "patient_group": f"synthetic-{index}",
                "label": index % 2,
                "privacy_review": "cleared",
            }
        )
    spec = {
        "task_id": "synthetic-images",
        "modality": "image",
        "privacy_review_reference": "synthetic-fixture",
        "source": "generated",
        "permission": "test",
    }
    contents, contract, provenance = adapt(json.dumps(records), tmp_path, spec)
    assert len(pd.read_csv(io.BytesIO(contents))) == 60
    assert len(contract.features) == 19 and contract.group_column == "patient_group"
    assert provenance["clinical_status"] == "research_only"
    _, changed, _ = adapt(json.dumps(records), tmp_path, dict(spec, image_size=64))
    assert changed.digest != contract.digest
    records[1]["path"] = records[0]["path"]
    with pytest.raises(ValueError, match="conflicting"):
        adapt(json.dumps(records), tmp_path, spec)
    records[0]["path"] = "../outside.png"
    with pytest.raises(ValueError, match="within"):
        adapt(json.dumps(records), tmp_path, spec)


def test_waveform_adapter_checks_lead_contract_and_sampling(tmp_path):
    time = np.arange(1000) / 250
    signal = np.column_stack([np.sin(2 * np.pi * time), 0.5 * np.cos(2 * np.pi * time)])
    buffer = io.BytesIO()
    np.save(buffer, signal)
    features = ecg_features(buffer.getvalue(), 250, 125, ["I", "II"], "mV")
    assert features.shape == (10,) and np.isfinite(features).all()
    with pytest.raises(ValueError, match="mV"):
        ecg_features(buffer.getvalue(), 250, 125, ["I", "II"], "uV")
    with pytest.raises(ValueError, match="ordered leads"):
        ecg_features(buffer.getvalue(), 250, 125, ["I"], "mV")


def test_distillation_corpus_prevents_group_and_evidence_leakage(tmp_path):
    rows = [
        {
            "case_id": str(index),
            "patient_group": str(index),
            "split": split,
            "prompt": f"Synthetic question {index}",
            "response": "Synthetic answer",
            "teacher": "test-teacher",
            "teacher_revision": "test-revision",
            "permission_reference": "software-fixture",
            "privacy": "synthetic",
            "source_ids": ["source-1"],
            "citations": ["source-1"],
        }
        for index, split in enumerate(["train", "validation", "test"])
    ]
    path = tmp_path / "teacher.jsonl"

    def save():
        path.write_text("\n".join(json.dumps(row) for row in rows))

    save()
    assert len(load_corpus(path)) == 3
    rows[1]["patient_group"] = "0"
    save()
    with pytest.raises(ValueError, match="overlap"):
        load_corpus(path)
    rows[1]["patient_group"] = "1"
    rows[0]["citations"] = ["invented"]
    save()
    with pytest.raises(ValueError, match="not supplied"):
        load_corpus(path)
