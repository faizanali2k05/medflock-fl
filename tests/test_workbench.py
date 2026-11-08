import time

import pytest
from fastapi.testclient import TestClient

from medflock.api import create_app
from medflock.store import Store, runs


def test_idempotent_request_conflict_and_restart(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'test.db'}")
    first, created = store.create_run("same-key", {"clients": 3})
    second, duplicate = store.create_run("same-key", {"clients": 3})
    assert created and not duplicate and first["id"] == second["id"]
    with pytest.raises(ValueError, match="different settings"):
        store.create_run("same-key", {"clients": 5})
    assert store.claim(first["id"])
    assert not store.claim(first["id"])
    store.recover()
    assert store.list(runs)[0]["status"] == "aborted"
    store.engine.dispose()


def test_api_run_end_to_end(dataset, tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'api.db'}", dataset, tmp_path / "artifacts")
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/api/status").json()["clinical_review"] == "pending"
        assert client.get("/api/status", headers={"host": "untrusted.example"}).status_code == 400
        assert client.post("/api/runs", json={}).status_code == 422
        headers = {"Idempotency-Key": "test-request-123"}
        response = client.post("/api/runs", json={"rounds": 2}, headers=headers)
        assert response.status_code == 202
        run_id = response.json()["id"]
        assert client.post("/api/runs", json={"rounds": 2}, headers=headers).json()["id"] == run_id
        assert client.post("/api/runs", json={"rounds": 3}, headers=headers).status_code == 409
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            run = client.get(f"/api/runs/{run_id}").json()
            if run["status"] in {"completed", "failed"}:
                break
            time.sleep(0.05)
        assert run["status"] == "completed", run
        assert client.get("/api/models").json()[0]["status"] == "research_candidate"
        assert client.get("/api/audit").status_code == 403
        from medflock.store import events

        assert any(e["kind"] == "model.candidate" for e in app.state.store.list(events))
        assert client.get("/api/runs/missing").status_code == 404
