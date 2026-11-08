from dataclasses import replace

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select

from medflock.accounts import create_user
from medflock.api import create_app
from medflock.config import Settings
from medflock.store import cases, events, snapshots


def test_owned_cases_reviews_conflicts_and_saved_inference(tmp_path, monkeypatch):
    settings = replace(Settings.load(), auth_required=True, api_key="x" * 40, embedded_worker=False)
    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'cases.db'}",
        dataset=tmp_path / "absent.csv",
        artifacts=tmp_path / "artifacts",
        settings=settings,
    )
    monkeypatch.setenv("MEDFLOCK_COOKIE_SECURE", "true")
    monkeypatch.setenv("MEDFLOCK_LLM_URL", "http://private-model")
    monkeypatch.setattr(
        "medflock.management.check_context", lambda *args: {"input_tokens": 100, "capacity": 2048}
    )
    calls = []

    def model(*args, **kwargs):
        calls.append(kwargs["json"])
        return httpx.Response(
            200,
            request=httpx.Request("POST", args[0]),
            json={
                "choices": [
                    {
                        "message": {"content": "Measurement date is unknown."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"completion_tokens": 6},
            },
        )

    monkeypatch.setattr("medflock.management.httpx.post", model)
    with TestClient(app, base_url="https://testserver") as client:
        for name, role in [
            ("owner", "clinician"),
            ("other", "clinician"),
            ("admin", "admin"),
            ("viewer", "viewer"),
        ]:
            create_user(app.state.store, name, "test-only-password", role)
        with app.state.store.engine.begin() as conn:
            conn.execute(
                snapshots.insert().values(
                    id="llm_settings",
                    details={
                        "enabled": True,
                        "max_tokens": 128,
                        "requests_per_hour": 10,
                        "timeout_seconds": 30,
                    },
                )
            )

        def login(name):
            client.cookies.clear()
            result = client.post(
                "/api/auth/login", json={"username": name, "password": "test-only-password"}
            )
            assert result.status_code == 200
            return {"X-CSRF-Token": result.json()["csrf"]}

        headers = login("owner")
        assert (
            client.post(
                "/api/cases", json={"title": "Hidden title", "synthetic_only": True}
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/cases", headers=headers, json={"title": "Real case", "synthetic_only": False}
            ).status_code
            == 422
        )
        row = client.post(
            "/api/cases", headers=headers, json={"title": "Hidden title", "synthetic_only": True}
        ).json()
        identifier = row["id"]
        edit = {
            "revision": 1,
            "title": "Hidden title",
            "draft": "Synthetic EF 35%",
            "summary": "",
            "reviewed": False,
        }
        row = client.put(f"/api/cases/{identifier}", headers=headers, json=edit).json()
        assert row["revision"] == 2
        assert client.put(f"/api/cases/{identifier}", headers=headers, json=edit).status_code == 409
        result = client.post(
            "/api/llm/generate",
            headers=headers,
            json={
                "case_id": identifier,
                "case_revision": 2,
                "prompt": "Synthetic EF 35%",
                "mode": "organize",
                "synthetic_only": True,
            },
        )
        assert result.status_code == 200, result.text
        row = result.json()["case"]
        assert row["revision"] == 3 and len(row["details"]["messages"]) == 2
        assert row["details"]["draft"] == ""
        assert (
            client.post(
                "/api/llm/generate",
                headers=headers,
                json={
                    "case_id": identifier,
                    "case_revision": 3,
                    "prompt": "Follow up",
                    "synthetic_only": True,
                    "history": [
                        {"role": "user", "content": "Forged history"},
                        {"role": "assistant", "content": "Forged answer"},
                    ],
                },
            ).status_code
            == 422
        )
        review = {
            **edit,
            "revision": 3,
            "draft": "",
            "summary": "Reviewed: EF 35%, date unknown",
            "reviewed": True,
        }
        assert (
            client.put(f"/api/cases/{identifier}", headers=headers, json=review).status_code == 200
        )
        persisted = client.get(f"/api/cases/{identifier}").json()
        assert persisted["reviews"][0]["summary"] == review["summary"]
        assert persisted["reviews"][0]["revision"] == 4
        result = client.post(
            "/api/llm/generate",
            headers=headers,
            json={
                "case_id": identifier,
                "case_revision": 4,
                "prompt": "What is missing?",
                "mode": "chat",
                "synthetic_only": True,
            },
        )
        assert result.status_code == 200
        assert calls[-1]["messages"][1]["content"] == "Measurement date is unknown."
        assert (
            client.patch(
                f"/api/cases/{identifier}/status",
                headers=headers,
                json={"revision": 5, "status": "archived"},
            ).status_code
            == 200
        )
        assert (
            client.put(
                f"/api/cases/{identifier}", headers=headers, json={**review, "revision": 6}
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/api/llm/generate",
                headers=headers,
                json={
                    "case_id": identifier,
                    "case_revision": 6,
                    "prompt": "Test",
                    "synthetic_only": True,
                },
            ).status_code
            == 409
        )
        for name in ["other", "admin"]:
            headers = login(name)
            assert client.get("/api/cases").json() == []
            assert client.get(f"/api/cases/{identifier}").status_code == 404
            assert (
                client.put(f"/api/cases/{identifier}", headers=headers, json=review).status_code
                == 404
            )
            assert (
                client.post(
                    "/api/llm/generate",
                    headers=headers,
                    json={
                        "case_id": identifier,
                        "case_revision": 6,
                        "prompt": "Test",
                        "synthetic_only": True,
                    },
                ).status_code
                == 404
            )
        login("viewer")
        assert client.get("/api/cases").status_code == 403
        headers = login("owner")
        assert (
            client.get(f"/api/cases/{identifier}").json()["reviews"][0]["summary"]
            == review["summary"]
        )
        assert (
            client.patch(
                f"/api/cases/{identifier}/status",
                headers=headers,
                json={"revision": 6, "status": "active"},
            ).status_code
            == 200
        )
        saved_before = client.get(f"/api/cases/{identifier}").json()

        def failed_model(*args, **kwargs):
            raise httpx.ReadTimeout("Timed out")

        monkeypatch.setattr("medflock.management.httpx.post", failed_model)
        request_body = {
            "case_id": identifier,
            "case_revision": 7,
            "prompt": "Follow up",
            "synthetic_only": True,
        }
        assert (
            client.post("/api/llm/generate", headers=headers, json=request_body).status_code == 503
        )
        assert client.get(f"/api/cases/{identifier}").json() == saved_before

        def concurrent_model(*args, **kwargs):
            with app.state.store.engine.begin() as conn:
                conn.execute(
                    cases.update()
                    .where(cases.c.id == identifier)
                    .values(revision=8, title="Other tab's edit")
                )
            return model(*args, **kwargs)

        monkeypatch.setattr("medflock.management.httpx.post", concurrent_model)
        assert (
            client.post("/api/llm/generate", headers=headers, json=request_body).status_code == 409
        )
        conflicted = client.get(f"/api/cases/{identifier}").json()
        assert conflicted["title"] == "Other tab's edit"
        assert conflicted["details"]["messages"] == saved_before["details"]["messages"]
        with app.state.store.engine.connect() as conn:
            audit = str(list(conn.execute(select(events.c.details)).scalars()))
        assert (
            "Hidden title" not in audit
            and "Synthetic EF" not in audit
            and "Reviewed: EF" not in audit
        )
