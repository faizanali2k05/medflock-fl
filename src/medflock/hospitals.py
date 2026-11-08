"""Manual hospital admission grants portal access, independently of runner enrollment."""

import secrets
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from medflock.accounts import password_hash, quota, users
from medflock.security import authenticate
from medflock.store import event, fleet, now, snapshots

router = APIRouter(tags=["Hospital admission"])


class TransportBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flower_node_id: str = Field(pattern=r"^[1-9][0-9]{0,19}$")
    public_key_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    verification_reference: str = Field(min_length=10, max_length=500)


@router.post("/api/admin/nodes/{identifier}/transport-binding", status_code=201)
def bind_transport(
    identifier: str, body: TransportBinding, request: Request, principal=Depends(authenticate)
):
    principal.require("admin")
    if int(body.flower_node_id) >= 2**64:
        raise HTTPException(422, "Flower identity exceeds uint64")
    with request.app.state.store.engine.begin() as conn:
        node = (
            conn.execute(select(fleet).where(fleet.c.id == identifier).with_for_update())
            .mappings()
            .first()
        )
        if not node or node["kind"] != "registered_external" or node["status"] == "removed":
            raise HTTPException(409, "An admitted external node is required")
        bindings = (
            conn.execute(select(snapshots).where(snapshots.c.id.startswith("flower_identity_")))
            .mappings()
            .all()
        )
        if any(
            row["details"]["node_id"] == identifier
            or row["id"] == "flower_identity_" + body.flower_node_id
            for row in bindings
        ):
            raise HTTPException(409, "Transport identity or hospital already bound")
        details = {
            **body.model_dump(),
            "node_id": identifier,
            "verified_by": principal.subject,
            "created_at": now(),
        }
        conn.execute(
            snapshots.insert().values(id="flower_identity_" + body.flower_node_id, details=details)
        )
        event(
            conn,
            "hospital.transport_binding_recorded",
            {
                "node_id": identifier,
                "actor": principal.subject,
                "flower_node_id": body.flower_node_id,
            },
        )
    return {"status": "identity_bound", "connection_verified": False}


class Application(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organization: str = Field(min_length=3, max_length=160)
    contact_name: str = Field(min_length=3, max_length=120)
    contact_email: str = Field(pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$", max_length=254)
    location: str = Field(min_length=3, max_length=160)
    registration_reference: str = Field(min_length=3, max_length=200)
    intended_use: str = Field(min_length=20, max_length=1500)
    username: str = Field(pattern=r"^[A-Za-z0-9_.-]{3,64}$")
    password: str = Field(min_length=12, max_length=128)
    authorized_representative: Literal[True]
    local_data_acknowledgement: Literal[True]


@router.post("/api/hospital-applications", status_code=202)
def apply(body: Application, request: Request):
    store = request.app.state.store
    quota(store, "hospital-apply:" + request.client.host, 3, 3600)
    identifier, user_id = "hospital_" + secrets.token_hex(16), secrets.token_hex(16)
    details = body.model_dump(exclude={"password"})
    details.update(status="pending", created_at=now(), user_id=user_id)
    try:
        with store.engine.begin() as conn:
            conn.execute(
                users.insert().values(
                    id=user_id,
                    username=body.username,
                    password_hash=password_hash(body.password),
                    role="hospital",
                    enabled=False,
                    node_id=None,
                    created_at=time.time(),
                )
            )
            conn.execute(snapshots.insert().values(id=identifier, details=details))
            event(conn, "hospital.application_received", {"application_id": identifier})
    except IntegrityError:
        raise HTTPException(409, "Account name unavailable; choose another username") from None
    return {
        "id": identifier,
        "status": "pending",
        "message": "Manual verification required before sign-in",
    }


@router.get("/api/admin/hospital-applications")
def applications(request: Request, principal=Depends(authenticate)):
    principal.require("admin")
    with request.app.state.store.engine.connect() as conn:
        return [
            {"id": row["id"], **row["details"]}
            for row in conn.execute(
                select(snapshots).where(snapshots.c.id.startswith("hospital_"))
            ).mappings()
        ]


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "rejected"]
    verification_reference: str = Field(min_length=10, max_length=500)


@router.post("/api/admin/hospital-applications/{identifier}/decision")
def decide(identifier: str, body: Decision, request: Request, principal=Depends(authenticate)):
    principal.require("admin")
    with request.app.state.store.engine.begin() as conn:
        row = (
            conn.execute(
                select(snapshots)
                .where(snapshots.c.id == identifier, snapshots.c.id.startswith("hospital_"))
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(404, "Application not found")
        details = dict(row["details"])
        if details["status"] != "pending":
            raise HTTPException(409, "Application already decided")
        details.update(
            status=body.decision,
            reviewed_by=principal.subject,
            reviewed_at=now(),
            verification_reference=body.verification_reference,
        )
        node_id = "hospital-" + details["user_id"]
        if body.decision == "approved":
            conn.execute(
                fleet.insert().values(
                    id=node_id,
                    label=details["organization"],
                    status="suspended",
                    kind="registered_external",
                    created_at=now(),
                    last_seen=None,
                    details={"application_id": identifier, "enrollment": "pending"},
                )
            )
            conn.execute(
                users.update()
                .where(users.c.id == details["user_id"])
                .values(
                    enabled=True,
                    node_id=node_id,
                )
            )
            details["node_id"] = node_id
        conn.execute(snapshots.update().where(snapshots.c.id == identifier).values(details=details))
        event(
            conn,
            "hospital.application_decided",
            {
                "application_id": identifier,
                "actor": principal.subject,
                "decision": body.decision,
            },
        )
    return {"id": identifier, "status": body.decision, "transport": "not_connected"}
