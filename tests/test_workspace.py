from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from medflock.accounts import create_user
from medflock.api import create_app
from medflock.config import Settings
from medflock.store import event


@pytest.mark.parametrize(
    "role", ["clinician", "researcher", "hospital", "client", "viewer", "admin"]
)
def test_preferences_notifications_and_password_require_own_session(tmp_path, role):
    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'workspace.db'}",
        dataset=tmp_path / "missing",
        artifacts=tmp_path / "artifacts",
        settings=replace(Settings.load(), auth_required=True, embedded_worker=False),
    )
    with TestClient(app, base_url="https://testserver") as client:
        user = create_user(app.state.store, "fixture-" + role, "fixture-password-123", role)
        other = create_user(app.state.store, "other", "fixture-password-123", "admin")
        with app.state.store.engine.begin() as conn:
            event(conn, "llm.completed", {"actor": user["id"], "secret": "private clinical text"})
            event(conn, "account.created", {"actor": other["id"], "secret": "admin secret"})
        assert client.get("/api/workspace/profile").status_code == 401
        login = client.post(
            "/api/auth/login",
            json={"username": user["username"], "password": "fixture-password-123"},
        ).json()
        headers = {"X-CSRF-Token": login["csrf"]}
        body = {"display_name": "Fixture Name", "avatar": "moon", "theme": "dark"}
        assert client.put("/api/workspace/profile", json=body).status_code == 403
        assert client.put("/api/workspace/profile", json=body, headers=headers).json() == body
        assert client.get("/api/workspace/profile").json() == {**body, "photo_version": None}
        items = client.get("/api/workspace/notifications").json()["items"]
        assert "Model response completed" in [item["title"] for item in items]
        assert ("Account created" in [item["title"] for item in items]) == (role == "admin")
        assert "secret" not in str(items) and "private clinical" not in str(items)
        ids = [item["id"] for item in items]
        assert (
            client.post(
                "/api/workspace/notifications/read", json={"ids": ids}, headers=headers
            ).status_code
            == 200
        )
        assert all(
            item["read"] for item in client.get("/api/workspace/notifications").json()["items"]
        )
        assert (
            client.post(
                "/api/workspace/notifications/read", json={"ids": ["foreign-id"]}, headers=headers
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/auth/password",
                json={"current_password": "wrong", "new_password": "new-fixture-password"},
                headers=headers,
            ).status_code
            == 401
        )
        client.cookies.clear()
        login = client.post(
            "/api/auth/login", json={"username": "other", "password": "fixture-password-123"}
        ).json()
        assert client.get("/api/workspace/profile").json()["display_name"] == ""


def test_clean_workspace_urls_and_unknown_api_are_distinct(tmp_path):
    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'routes.db'}",
        dataset=tmp_path / "missing",
        artifacts=tmp_path / "artifacts",
        settings=replace(Settings.load(), embedded_worker=False),
    )
    with TestClient(app) as client:
        for path in ["/cases", "/cases/new", "/account", "/research/overview", "/institution"]:
            assert client.get(path).status_code == 200
        assert client.get("/api/no-such-resource").status_code == 404
        assert client.get("/.env").status_code == 404


def test_profile_photo_is_validated_normalized_and_private(tmp_path):
    from io import BytesIO

    from PIL import Image

    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'photos.db'}",
        dataset=tmp_path / "missing",
        artifacts=tmp_path / "artifacts",
        settings=replace(Settings.load(), auth_required=True, embedded_worker=False),
    )
    output = BytesIO()
    photo = Image.new("RGB", (400, 300), "red")
    photo.save(output, "PNG", pnginfo=None)
    with TestClient(app, base_url="https://testserver") as client:
        for username in ("photo-owner", "photo-other"):
            create_user(app.state.store, username, "fixture-password-123", "clinician")
        assert client.get("/api/workspace/profile/photo").status_code == 401
        login = client.post(
            "/api/auth/login", json={"username": "photo-owner", "password": "fixture-password-123"}
        ).json()
        headers = {"X-CSRF-Token": login["csrf"]}
        url = "/api/workspace/profile/photo"
        assert client.post(url, files={"file": ("photo.png", output.getvalue())}).status_code == 403
        assert (
            client.post(
                url, headers=headers, files={"file": ("photo.svg", b"<svg></svg>")}
            ).status_code
            == 422
        )
        assert (
            client.post(
                url, headers=headers, files={"file": ("large.png", b"x" * (2 * 1024 * 1024 + 1))}
            ).status_code
            == 413
        )
        result = client.post(url, headers=headers, files={"file": ("photo.png", output.getvalue())})
        assert result.status_code == 200
        assert (
            client.get("/api/workspace/profile").json()["photo_version"]
            == result.json()["photo_version"]
        )
        response = client.get(url)
        assert response.headers["content-type"] == "image/jpeg"
        assert "no-store" in response.headers["cache-control"]
        image = Image.open(BytesIO(response.content))
        assert image.size == (256, 256) and not image.getexif()
        client.cookies.clear()
        client.post(
            "/api/auth/login", json={"username": "photo-other", "password": "fixture-password-123"}
        )
        assert client.get(url).status_code == 404
        client.cookies.clear()
        login = client.post(
            "/api/auth/login", json={"username": "photo-owner", "password": "fixture-password-123"}
        ).json()
        assert client.delete(url, headers={"X-CSRF-Token": login["csrf"]}).status_code == 200
        assert client.get(url).status_code == 404
