import hashlib
from dataclasses import replace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from medflock.api import create_app
from medflock.config import Settings
from medflock.store import Store, models, runs
from medflock.training.data import default_contract, fit_transform, read_dataset, split_indices
from medflock.training.engine import TrainingConfig, predict, train_run
from medflock.training.models import BinaryModel


@pytest.mark.parametrize("family", ["logistic", "mlp"])
def test_gradient_matches_numerical_derivative(family):
    model = BinaryModel(3, family, 4)
    rng = np.random.default_rng(7)
    x, y = rng.normal(size=(20, 3)), np.arange(20) % 2
    weights = model.initialize(8)

    def loss(w):
        p = np.clip(model.predict(w, x), 1e-12, 1 - 1e-12)
        return -(y * np.log(p) + (1 - y) * np.log(1 - p)).mean() + 0.005 * np.sum(w[:-1] ** 2)

    numerical = []
    for index in range(model.size):
        delta = np.zeros(model.size)
        delta[index] = 1e-6
        numerical.append((loss(weights + delta) - loss(weights - delta)) / 2e-6)
    np.testing.assert_allclose(model.gradient(weights, x, y, 0.01), numerical, atol=1e-7)


def test_group_split_and_training_only_preprocessing(dataset):
    values, labels, _, _ = read_dataset(dataset.read_bytes(), default_contract())
    groups = np.arange(len(labels)) // 2
    train, validation, test = split_indices(labels, groups, 42)
    assert not set(groups[train]) & set(groups[test])
    assert not set(groups[train]) & set(groups[validation])
    assert not set(groups[test]) & set(groups[validation])
    state = fit_transform(values[train])
    values[test] = 1e9
    assert state == fit_transform(values[train])


@pytest.mark.parametrize("family", ["logistic", "mlp"])
def test_training_warm_start_and_artifact_integrity(dataset, tmp_path, family):
    events = []
    contract = default_contract()
    config = TrainingConfig(rounds=3, family=family, seed=9)
    result, manifest = train_run(
        config,
        dataset.read_bytes(),
        contract,
        tmp_path,
        "first",
        lambda kind, details: events.append(kind),
        lambda: False,
    )
    assert (
        result["cohort"]["train_count"]
        + result["cohort"]["validation_count"]
        + result["cohort"]["test_count"]
        == 80
    )
    assert events.count("contribution.accepted") == 9
    features = {feature.name: None for feature in contract.features}
    output = predict(manifest, features, tmp_path)
    assert 0 <= output["score"] <= 1
    assert output["medication_status"] == "not_assessed"
    config.parent_model = "first"
    _, child = train_run(
        config,
        dataset.read_bytes(),
        contract,
        tmp_path,
        "second",
        lambda *_: None,
        lambda: False,
        parent=manifest,
    )
    assert child["parent_model"] == "first"
    mismatch = dict(manifest, contract_hash="incorrect")
    with pytest.raises(ValueError, match="does not match"):
        train_run(
            config,
            dataset.read_bytes(),
            contract,
            tmp_path,
            "bad",
            lambda *_: None,
            lambda: False,
            parent=mismatch,
        )
    (tmp_path / manifest["file"]).write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="integrity"):
        predict(manifest, features, tmp_path)


def test_cancellation_cannot_publish_candidate(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'cancel.db'}")
    run, _ = store.create_run("cancel-request", {})
    assert store.claim(run["id"])
    assert store.cancel(run["id"])
    store.finish(run["id"], {}, {"sha256": hashlib.sha256(b"x").hexdigest()})
    store.fail(run["id"], "late failure")
    assert store.get(runs, run["id"])["status"] == "cancelled"
    assert store.list(models) == []
    store.engine.dispose()


def test_authenticated_graphql_upload_queue_and_cursor(dataset, tmp_path):
    settings = replace(Settings.load(), auth_required=True, api_key="a" * 40, embedded_worker=False)
    app = create_app(
        f"sqlite:///{tmp_path / 'graphql.db'}", dataset, tmp_path / "artifacts", settings=settings
    )
    with TestClient(app) as client:
        assert client.post("/graphql", json={"query": "{ runs { id } }"}).status_code == 401
        client.headers["Authorization"] = "Bearer " + "a" * 40
        response = client.post(
            "/graphql", json={"query": "{ datasets { id profile } activityCursor }"}
        ).json()
        assert "errors" not in response
        dataset_id = response["data"]["datasets"][0]["id"]
        cursor = response["data"]["activityCursor"]
        mutation = (
            "mutation($c: JSON!, $k: String!) { "
            "startRun(config: $c, requestKey: $k) { id status } }"
        )
        variables = {"c": {"dataset_id": dataset_id, "rounds": 2}, "k": "graphql-request"}
        created = client.post("/graphql", json={"query": mutation, "variables": variables}).json()
        assert "errors" not in created
        run_id = created["data"]["startRun"]["id"]
        duplicate = client.post("/graphql", json={"query": mutation, "variables": variables}).json()
        assert duplicate["data"]["startRun"]["id"] == run_id
        activity = client.post(
            "/graphql", json={"query": f"{{ activity(after: {cursor}) {{ sequence kind }} }}"}
        ).json()
        assert activity["data"]["activity"][0]["kind"] == "run.queued"
        cancelled = client.post(
            "/graphql", json={"query": 'mutation { cancelRun(id: "' + run_id + '") }'}
        ).json()
        assert cancelled["data"]["cancelRun"]
        denied = client.post(
            "/api/runs",
            json={},
            headers={"Origin": "https://untrusted.example", "Idempotency-Key": "cross-origin"},
        )
        assert denied.status_code == 403


def test_new_binary_dataset_uses_same_application(tmp_path):
    import pandas as pd

    from medflock.service import Workbench
    from medflock.worker import Worker

    frame = pd.DataFrame({"measurement": np.linspace(1, 80, 80), "outcome": np.arange(80) % 2})
    contents = frame.to_csv(index=False).encode()
    contract = {
        "id": "new-binary-task",
        "features": [{"name": "measurement", "unit": "mg/L"}],
        "target": "outcome",
    }
    store = Store(f"sqlite:///{tmp_path / 'custom.db'}")
    service = Workbench(store, tmp_path / "absent.csv", tmp_path / "artifacts")
    snapshot = service.register_dataset(
        "Synthetic integration cohort",
        contents,
        contract,
        {"source": "synthetic fixture", "permission": "test"},
    )
    assert (
        service.register_dataset(
            "Duplicate", contents, contract, {"source": "fixture", "permission": "test"}
        )["id"]
        == snapshot["id"]
    )
    run = service.submit(
        {"dataset_id": snapshot["id"], "family": "mlp", "rounds": 2}, "new-task-request"
    )
    assert store.claim(run["id"])
    Worker(service).execute(run)
    assert store.get(runs, run["id"])["status"] == "completed"
    result = service.predict(run["id"], {"measurement": 12})
    assert 0 <= result["score"] <= 1
    assert (
        service.promote(run["id"], "Synthetic integration validation")["status"]
        == "active_research"
    )
    store.engine.dispose()


def test_node_bundle_contract_and_integrity(dataset, tmp_path):
    from medflock.node_data import load_node, prepare

    specification = prepare(dataset.read_bytes(), tmp_path, clients=3)
    values, labels = load_node(tmp_path / "node-0", specification["digest"])
    assert values.shape[1] == 11 and len(values) == len(labels)
    with pytest.raises(ValueError, match="does not match"):
        load_node(tmp_path / "node-0", "wrong-task")
    (tmp_path / "node-0/training.npz").write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="checksum"):
        load_node(tmp_path / "node-0", specification["digest"])
