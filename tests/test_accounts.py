from dataclasses import replace

from fastapi.testclient import TestClient

from medflock.accounts import create_user
from medflock.api import create_app
from medflock.config import Settings


def test_sessions_roles_csrf_and_revocation(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDFLOCK_COOKIE_SECURE", "true")
    settings = replace(Settings.load(), auth_required=True, api_key="x" * 40, embedded_worker=False)
    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'auth.db'}",
        dataset=tmp_path / "absent.csv",
        artifacts=tmp_path / "artifacts",
        settings=settings,
    )
    with TestClient(app, base_url="https://testserver") as client:
        create_user(app.state.store, "admin-test", "test-only-password", "admin")
        assert client.get("/api/models").status_code == 401
        result = client.post(
            "/api/auth/login", json={"username": "admin-test", "password": "test-only-password"}
        )
        assert result.status_code == 200
        assert (
            "HttpOnly" in result.headers["set-cookie"] and "Secure" in result.headers["set-cookie"]
        )
        csrf = result.json()["csrf"]
        headers = {"x-csrf-token": csrf}
        assert (
            client.post("/api/admin/nodes", json={"id": "n1", "label": "Test"}).status_code == 403
        )
        assert (
            client.post(
                "/api/admin/nodes", headers=headers, json={"id": "n1", "label": "Test"}
            ).status_code
            == 201
        )
        for role in ["viewer", "clinician", "researcher", "client"]:
            body = {
                "username": role + "-test",
                "password": "test-only-password",
                "role": role,
                "node_id": "n1" if role == "client" else None,
            }
            assert client.post("/api/admin/users", headers=headers, json=body).status_code == 201
        assert (
            client.post("/api/admin/corpora/import-bundled", headers=headers).json()["cases"] == 300
        )
        saved_cookie = client.cookies.get("medflock_session")
        assert client.post("/api/auth/logout", headers=headers).status_code == 200
        client.cookies.set("medflock_session", saved_cookie)
        assert client.get("/api/auth/me").status_code == 401
        client.cookies.clear()
        for role in ["viewer", "clinician", "researcher", "client"]:
            result = client.post(
                "/api/auth/login",
                json={"username": role + "-test", "password": "test-only-password"},
            )
            assert result.status_code == 200
            headers = {"x-csrf-token": result.json()["csrf"]}
            assert client.get("/api/admin/users").status_code == 403
            assert (
                client.patch(
                    "/api/admin/nodes/n1/policy", headers=headers, json={"status": "active"}
                ).status_code
                == 403
            )
            assert client.get("/api/audit").status_code == 403
            if role == "client":
                assert client.get("/api/client/node").json()["id"] == "n1"
                assert client.get("/api/models").status_code == 403
                assert (
                    client.post(
                        "/graphql", headers=headers, json={"query": "{ nodes { id } }"}
                    ).status_code
                    == 403
                )
            else:
                assert client.get("/api/models").status_code == 200
            if role == "clinician":
                assert (
                    client.post(
                        "/api/runs",
                        headers={**headers, "Idempotency-Key": "clinician-denied"},
                        json={"rounds": 2},
                    ).status_code
                    == 403
                )
                assert (
                    client.post(
                        "/api/llm/generate",
                        headers=headers,
                        json={"prompt": "Synthetic case", "synthetic_only": True},
                    ).status_code
                    == 503
                )
            if role == "viewer":
                assert (
                    client.post(
                        "/api/llm/generate",
                        headers=headers,
                        json={"prompt": "test", "synthetic_only": True},
                    ).status_code
                    == 403
                )
            client.post("/api/auth/logout", headers=headers)
            client.cookies.clear()


def test_login_throttle(tmp_path):
    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'throttle.db'}",
        dataset=tmp_path / "none",
        artifacts=tmp_path / "artifacts",
        settings=replace(
            Settings.load(), auth_required=True, api_key="x" * 40, embedded_worker=False
        ),
    )
    with TestClient(app) as client:
        for _ in range(5):
            assert (
                client.post(
                    "/api/auth/login", json={"username": "missing", "password": "wrong"}
                ).status_code
                == 401
            )
        assert (
            client.post(
                "/api/auth/login", json={"username": "missing", "password": "wrong"}
            ).status_code
            == 429
        )
