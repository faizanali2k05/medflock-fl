"""Account-owned preferences and a filtered activity inbox never expose raw audit payloads."""

import base64
import hashlib
import warnings
from datetime import datetime, timezone
from io import BytesIO
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from medflock.accounts import session_principal
from medflock.store import events, snapshots

router = APIRouter(prefix="/api/workspace", tags=["Workspace"])


def identity(request):
    principal = session_principal(request)
    if not principal:
        raise HTTPException(401, "Login required")
    return principal


def read_profile(conn, subject, locked=False):
    if locked:
        if conn.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        conn.execute(
            insert(snapshots)
            .values(id="profile_" + subject, details={})
            .on_conflict_do_nothing(index_elements=["id"])
        )
    row = (
        conn.execute(
            select(snapshots).where(snapshots.c.id == "profile_" + subject).with_for_update()
        )
        .mappings()
        .first()
    )
    return dict(row["details"]) if row else {}


def write_profile(conn, subject, data):
    key = "profile_" + subject
    if conn.execute(select(snapshots.c.id).where(snapshots.c.id == key)).first():
        conn.execute(snapshots.update().where(snapshots.c.id == key).values(details=data))
    else:
        conn.execute(snapshots.insert().values(id=key, details=data))


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(default="", max_length=80)
    avatar: Literal["initials", "leaf", "sun", "moon", "star"] = "initials"
    theme: Literal["light", "dark", "system"] = "system"


@router.get("/profile")
def profile(request: Request):
    principal = identity(request)
    with request.app.state.store.engine.connect() as conn:
        data = read_profile(conn, principal.subject)
    return {
        **Preferences.model_validate(data.get("preferences", {})).model_dump(),
        "photo_version": data.get("photo_version"),
    }


@router.post("/profile/photo")
async def upload_photo(request: Request, file: UploadFile):
    principal = identity(request)
    content = await file.read(2 * 1024 * 1024 + 1)
    await file.close()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(413, "Choose an image smaller than 2 MiB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("Unsupported image")
                if source.width * source.height > 16_000_000:
                    raise ValueError("Image dimensions exceed limit")
                source.load()
                image = ImageOps.fit(ImageOps.exif_transpose(source).convert("RGB"), (256, 256))
                output = BytesIO()
                image.save(output, format="JPEG", quality=85)
                normalized = output.getvalue()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise HTTPException(422, "Use a valid JPEG, PNG or WebP image up to 16 megapixels") from exc
    version = hashlib.sha256(normalized).hexdigest()[:20]
    with request.app.state.store.engine.begin() as conn:
        data = read_profile(conn, principal.subject, locked=True)
        data.update(photo=base64.b64encode(normalized).decode("ascii"), photo_version=version)
        write_profile(conn, principal.subject, data)
    return {"photo_version": version}


@router.get("/profile/photo")
def get_photo(request: Request):
    principal = identity(request)
    with request.app.state.store.engine.connect() as conn:
        data = read_profile(conn, principal.subject)
    if not data.get("photo"):
        raise HTTPException(404, "No profile photo")
    return Response(
        base64.b64decode(data["photo"]),
        media_type="image/jpeg",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/profile/photo")
def delete_photo(request: Request):
    principal = identity(request)
    with request.app.state.store.engine.begin() as conn:
        data = read_profile(conn, principal.subject, locked=True)
        data.pop("photo", None)
        data.pop("photo_version", None)
        write_profile(conn, principal.subject, data)
    return {"photo_version": None}


@router.put("/profile")
def update_profile(body: Preferences, request: Request):
    principal = identity(request)
    with request.app.state.store.engine.begin() as conn:
        data = read_profile(conn, principal.subject, locked=True)
        data["preferences"] = body.model_dump()
        write_profile(conn, principal.subject, data)
    return body.model_dump()


TITLES = {
    "llm.completed": "Model response completed",
    "llm.failed": "Model request needs attention",
    "account.password_changed": "Your password was changed",
    "hospital.application_received": "Hospital application received",
    "hospital.application_decided": "Hospital application decision recorded",
    "node.policy_changed": "Hospital participation policy changed",
}


def visible_notifications(conn, principal, account):
    rows = conn.execute(
        select(events).order_by(events.c.created_at.desc(), events.c.id.desc()).limit(500)
    ).mappings()
    result = []
    for row in rows:
        details = row["details"] or {}
        own = details.get("actor") == principal.subject
        assigned = account.get("node_id") and details.get("node_id") == account["node_id"]
        # Only an explicit per-node policy event can be shared with its assigned account.
        node_notice = assigned and row["kind"] in {
            "node.policy_changed",
            "node.removed",
            "node.transport_bound",
        }
        recipient = details.get("user_id") == principal.subject and row["kind"] in {
            "account.sessions_revoked",
            "hospital.application_decided",
        }
        research = bool(principal.roles & {"researcher", "viewer"}) and row["kind"].startswith(
            ("run.", "round.", "contribution.", "model.")
        )
        if not (own or node_notice or recipient or research or "admin" in principal.roles):
            continue
        result.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "title": TITLES.get(
                    row["kind"], row["kind"].replace(".", " ").replace("_", " ").capitalize()
                ),
            }
        )
        if len(result) == 100:
            break
    return result


@router.get("/notifications")
def notifications(request: Request):
    principal = identity(request)
    with request.app.state.store.engine.connect() as conn:
        data = read_profile(conn, principal.subject)
        items = visible_notifications(conn, principal, request.state.account)
    seen = set(data.get("seen_notifications", []))
    return {"items": [{**item, "read": item["id"] in seen} for item in items]}


class ReadNotifications(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[str] = Field(max_length=100)


@router.post("/notifications/read")
def mark_read(body: ReadNotifications, request: Request):
    principal = identity(request)
    with request.app.state.store.engine.begin() as conn:
        visible = {
            item["id"] for item in visible_notifications(conn, principal, request.state.account)
        }
        if not set(body.ids).issubset(visible):
            raise HTTPException(403, "Notification unavailable")
        data = read_profile(conn, principal.subject, locked=True)
        data["seen_notifications"] = list(
            dict.fromkeys(data.get("seen_notifications", []) + body.ids)
        )[-1000:]
        write_profile(conn, principal.subject, data)
    return {"read": len(body.ids), "at": datetime.now(timezone.utc).isoformat()}
