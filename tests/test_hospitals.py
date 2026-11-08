from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from medflock.accounts import create_user
from medflock.api import create_app
from medflock.config import Settings
from medflock.distillation import require_reviewed_corpus
from medflock.federation_policy import eligible_identities


@pytest.mark.parametrize("status", [None, "unreviewed", "unreviewed_teacher_output", "rejected"])
def test_training_rejects_unapproved_teacher_status(status):
    with pytest.raises(ValueError, match="explicitly approved"):
        require_reviewed_corpus([{"review_status": status, "reviewer_id": "someone"}])


def test_training_requires_reviewer_identity():
    with pytest.raises(ValueError, match="reviewer identity"):
        require_reviewed_corpus([{"review_status": "approved"}])
    require_reviewed_corpus([{"review_status": "approved", "reviewer_id": "reviewer"}])


def test_hospital_admission_and_isolation(tmp_path):
    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'app.db'}",
        dataset=tmp_path / "missing.csv",
        artifacts=tmp_path / "artifacts",
        settings=replace(Settings.load(), auth_required=True, embedded_worker=False),
    )
    with TestClient(app, base_url="https://testserver") as client:
        body = dict(
            organization="Synthetic Hospital",
            contact_name="Test Contact",
            contact_email="test@example.invalid",
            location="Synthetic city",
            registration_reference="TEST-ONLY-001",
            intended_use="Synthetic admission test only",
            username="hospital-test",
            password="test-only-password",
            authorized_representative=True,
            local_data_acknowledgement=True,
        )
        result = client.post("/api/hospital-applications", json=body)
        assert result.status_code == 202
        identifier = result.json()["id"]
        credentials = {key: body[key] for key in ("username", "password")}
        assert client.post("/api/auth/login", json=credentials).status_code == 401
        assert client.get("/api/admin/hospital-applications").status_code == 401
        create_user(app.state.store, "admin-test", "test-only-password", "admin")
        login = client.post(
            "/api/auth/login", json={"username": "admin-test", "password": "test-only-password"}
        )
        headers = {"x-csrf-token": login.json()["csrf"]}
        decision = {"decision": "approved", "verification_reference": "test-manual-verification"}
        url = f"/api/admin/hospital-applications/{identifier}/decision"
        assert client.post(url, json=decision).status_code == 403
        assert client.post(url, headers=headers, json=decision).status_code == 200
        assert client.post(url, headers=headers, json=decision).status_code == 409
        hospital = client.get("/api/admin/hospital-applications").json()[0]
        node_id = hospital["node_id"]
        binding_url = f"/api/admin/nodes/{node_id}/transport-binding"
        binding = {
            "flower_node_id": "123",
            "public_key_sha256": "a" * 64,
            "verification_reference": "synthetic-registration-test",
        }
        assert client.post(binding_url, headers=headers, json=binding).status_code == 201
        assert client.post(binding_url, headers=headers, json=binding).status_code == 409
        assert eligible_identities(app.state.store.engine) == set()
        policy_url = f"/api/admin/nodes/{node_id}/policy"
        assert (
            client.patch(policy_url, headers=headers, json={"status": "active"}).status_code == 200
        )
        assert eligible_identities(app.state.store.engine) == {123}
        assert (
            client.patch(policy_url, headers=headers, json={"status": "suspended"}).status_code
            == 200
        )
        client.cookies.clear()
        login = client.post("/api/auth/login", json=credentials)
        assert login.status_code == 200
        assert login.json()["user"]["role"] == "hospital"
        node = client.get("/api/client/node").json()
        assert node["status"] == "suspended"
        assert node["transport"] == "not_connected"
        assert client.get("/api/cases").status_code == 200
        assert client.get("/api/admin/hospital-applications").status_code == 403
        assert client.get("/api/runs").status_code == 403
        assert client.get("/api/datasets").status_code == 403
        assert client.post("/graphql", json={"query": "{ nodes { id } }"}).status_code == 403
