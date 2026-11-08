import hashlib
import json

import pytest

from medflock.distillation import (
    DistillationConfig,
    split_manifest,
    verify_adapter,
    verify_stage_splits,
)


def config(tmp_path, **kwargs):
    return DistillationConfig.model_validate(
        dict(
            student="test/base",
            revision="a" * 40,
            corpus=tmp_path / "corpus.jsonl",
            output=tmp_path / "output",
            model_permission_reference="synthetic test only",
            **kwargs,
        )
    )


def test_hybrid_stage_requires_explicit_full_training(tmp_path):
    with pytest.raises(ValueError, match="explicit full-weight"):
        config(tmp_path, initial_adapter=tmp_path / "adapter")


def test_adapter_parent_identity_and_integrity(tmp_path):
    parent = tmp_path / "adapter"
    parent.mkdir()
    files = {}
    for name in ["adapter_config.json", "adapter_model.safetensors"]:
        (parent / name).write_bytes(b"synthetic fixture")
        files[name] = hashlib.sha256(b"synthetic fixture").hexdigest()
    record = dict(
        mode="sequence_distillation_lora", student="test/base", revision="a" * 40, files=files
    )
    path = parent / "distillation-report.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    settings = config(tmp_path, method="full", initial_adapter=parent)
    assert verify_adapter(settings) == hashlib.sha256(path.read_bytes()).hexdigest()
    record["revision"] = "b" * 40
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="base model/revision"):
        verify_adapter(settings)
    record["revision"] = "a" * 40
    path.write_text(json.dumps(record), encoding="utf-8")
    (parent / "adapter_model.safetensors").write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        verify_adapter(settings)


def test_escalation_cannot_reuse_parent_training_cases_as_test(tmp_path):
    parent = tmp_path / "adapter"
    parent.mkdir()
    rows = [{"patient_group": "family-a", "prompt": "Synthetic question", "split": "train"}]
    (parent / "distillation-report.json").write_text(
        json.dumps({"split_manifest": split_manifest(rows)}), encoding="utf-8"
    )
    settings = config(tmp_path, method="full", initial_adapter=parent)
    assert verify_stage_splits(settings, rows) == split_manifest(rows)
    with pytest.raises(ValueError, match="changes split"):
        verify_stage_splits(settings, [{**rows[0], "split": "test"}])
