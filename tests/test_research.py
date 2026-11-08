import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from medflock.experiment import ExperimentConfig, aggregate, run_experiment, validate_update
from medflock.inference import score_candidate
from medflock.learning import partition
from medflock.task import FEATURES, PatientFeatures, load_cohort, transform


def test_censoring_and_followup_not_a_predictor(dataset):
    original = pd.read_csv(dataset)
    original.loc[1, "time"] = 89
    original.loc[2, "time"] = 90
    original.loc[3, "time"] = 91
    original.to_csv(dataset, index=False)
    frame, stats = load_cohort(dataset)
    assert stats["early_censored_excluded"] == 1
    assert 1 not in frame.row_id.values
    assert frame.loc[frame.row_id == 2, "target"].item() == 0
    assert frame.loc[frame.row_id == 3, "target"].item() == 0
    before = transform(frame)
    frame["time"] = 100000
    frame["DEATH_EVENT"] = 1 - frame.DEATH_EVENT
    np.testing.assert_array_equal(before, transform(frame))


def test_reject_missing_feature_and_single_class(dataset):
    frame = pd.read_csv(dataset)
    frame.drop(columns=["age"]).to_csv(dataset, index=False)
    with pytest.raises(ValueError, match="columns"):
        load_cohort(dataset)
    frame.DEATH_EVENT = 0
    frame.time = 120
    frame.to_csv(dataset, index=False)
    with pytest.raises(ValueError, match="outcome classes"):
        load_cohort(dataset)


@pytest.mark.parametrize("mode", ["iid", "label_skew", "feature_skew"])
def test_partition_is_complete_disjoint_and_reproducible(mode):
    x = np.arange(101).reshape(-1, 1)
    y = np.arange(101) % 2
    parts = partition(x, y, 5, mode, 42)
    np.testing.assert_array_equal(np.sort(np.concatenate(parts)), np.arange(101))
    for a, b in zip(parts, partition(x, y, 5, mode, 42), strict=True):
        np.testing.assert_array_equal(a, b)
    if mode == "label_skew":
        assert len(np.unique(y[parts[0]])) == 1


def test_flower_weighted_aggregation_and_invalid_updates():
    actual = aggregate([np.array([1.0, 2.0]), np.array([5.0, 6.0])], [1, 3], 1)
    np.testing.assert_allclose(actual, [4, 5])
    with pytest.raises(ValueError):
        validate_update(np.array([np.nan]), (1,))
    with pytest.raises(ValueError):
        validate_update(np.zeros(3), (2,))
    with pytest.raises(ValueError):
        aggregate([np.zeros(2)], [0], 1)


def test_defense_needs_more_clients():
    with pytest.raises(ValidationError):
        ExperimentConfig(clients=3, defense="clip")


def test_artifact_integrity_contract_and_paired_baselines(dataset, tmp_path):
    result, manifest = run_experiment(ExperimentConfig(rounds=2), dataset, tmp_path, "test")
    assert result["centralized"]["count"] == result["fedavg"]["count"] == 20
    assert sum(p["count"] for p in result["partitions"]) == 60
    patient = PatientFeatures.model_validate(pd.read_csv(dataset)[FEATURES].iloc[0].to_dict())
    score = score_candidate(patient, manifest, tmp_path)
    assert 0 < score["score"] < 1
    assert score["medication_status"] == "not_assessed"
    with pytest.raises(ValueError, match="contract"):
        score_candidate(patient, {**manifest, "contract_hash": "other"}, tmp_path)
    (tmp_path / manifest["file"]).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="integrity"):
        score_candidate(patient, manifest, tmp_path)


def test_same_seed_reproduces_result(dataset, tmp_path):
    config = ExperimentConfig(
        clients=5, rounds=2, partition="label_skew", attack="sign_flip", defense="clip"
    )
    a, _ = run_experiment(config, dataset, tmp_path, "a")
    b, _ = run_experiment(config, dataset, tmp_path, "b")
    assert a["fedavg"] == b["fedavg"]
    assert a["split_hash"] == b["split_hash"]
