"""Case ownership and revision checks apply equally to administrators and care professionals."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from medflock.security import authenticate
from medflock.store import case_reviews, cases, event, now

router = APIRouter(prefix="/api/cases", tags=["Case workspace"])


def case_user(principal=Depends(authenticate)):
    if not principal.roles.intersection({"admin", "clinician", "researcher", "hospital"}):
        raise HTTPException(403, "A care-professional or research account is required")
    return principal


def owned(connection, identifier, owner):
    row = (
        connection.execute(
            select(cases).where(
                cases.c.id == identifier,
                cases.c.owner == owner,
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(404, "Case not found")
    return dict(row)


def current(row, revision):
    if row["status"] != "active":
        raise HTTPException(409, "Restore this archived case before editing it")
    if row["revision"] != revision:
        raise HTTPException(409, "This case changed in another session. Reopen it before editing")


def update(connection, row, **values):
    result = connection.execute(
        cases.update()
        .where(
            cases.c.id == row["id"],
            cases.c.owner == row["owner"],
            cases.c.revision == row["revision"],
        )
        .values(**values, revision=row["revision"] + 1, updated_at=now())
    )
    if result.rowcount != 1:
        raise HTTPException(409, "This case changed in another session. Reopen it before editing")
    return owned(connection, row["id"], row["owner"])


class CreateCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    synthetic_only: Literal[True]


class EditCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=120)
    draft: str = Field(default="", max_length=20000)
    summary: str = Field(default="", max_length=20000)
    reviewed: bool = False


class CaseStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    status: Literal["active", "archived"]


@router.get("")
def list_cases(request: Request, principal=Depends(case_user)):
    with request.app.state.store.engine.connect() as conn:
        return [
            dict(row)
            for row in conn.execute(
                select(
                    cases.c.id,
                    cases.c.title,
                    cases.c.status,
                    cases.c.revision,
                    cases.c.created_at,
                    cases.c.updated_at,
                )
                .where(cases.c.owner == principal.subject)
                .order_by(cases.c.updated_at.desc())
                .limit(200)
            ).mappings()
        ]


@router.post("", status_code=201)
def create_case(body: CreateCase, request: Request, principal=Depends(case_user)):
    with request.app.state.store.engine.begin() as conn:
        count = conn.scalar(
            select(func.count()).select_from(cases).where(cases.c.owner == principal.subject)
        )
        if count >= 200:
            raise HTTPException(409, "The preview supports 200 saved cases per account")
        identifier = uuid.uuid4().hex
        conn.execute(
            cases.insert().values(
                id=identifier,
                owner=principal.subject,
                title=body.title.strip() or "Untitled case",
                status="active",
                revision=1,
                created_at=now(),
                updated_at=now(),
                details={
                    "messages": [],
                    "draft": "",
                    "summary": "",
                    "reviewed": False,
                    "synthetic_only": True,
                },
            )
        )
        event(conn, "case.created", {"actor": principal.subject, "case_id": identifier})
        return owned(conn, identifier, principal.subject)


@router.get("/{identifier}")
def get_case(identifier: str, request: Request, principal=Depends(case_user)):
    with request.app.state.store.engine.connect() as conn:
        row = owned(conn, identifier, principal.subject)
        row["reviews"] = [
            dict(review)
            for review in conn.execute(
                select(case_reviews)
                .where(
                    case_reviews.c.case_id == identifier,
                )
                .order_by(case_reviews.c.revision.desc())
            ).mappings()
        ]
        return row


@router.put("/{identifier}")
def edit_case(identifier: str, body: EditCase, request: Request, principal=Depends(case_user)):
    with request.app.state.store.engine.begin() as conn:
        row = owned(conn, identifier, principal.subject)
        current(row, body.revision)
        details = {
            **row["details"],
            "draft": body.draft,
            "summary": body.summary,
            "reviewed": body.reviewed,
        }
        new_review = body.reviewed and (
            not row["details"]["reviewed"] or body.summary != row["details"]["summary"]
        )
        if new_review:
            if not body.summary.strip():
                raise HTTPException(422, "A reviewed summary cannot be empty")
            count = conn.scalar(
                select(func.count())
                .select_from(case_reviews)
                .where(case_reviews.c.case_id == identifier)
            )
            if count >= 100:
                raise HTTPException(409, "The preview supports 100 review versions per case")
        row = update(conn, row, title=body.title.strip() or "Untitled case", details=details)
        if new_review:
            conn.execute(
                case_reviews.insert().values(
                    id=uuid.uuid4().hex,
                    case_id=identifier,
                    revision=row["revision"],
                    created_at=now(),
                    reviewer=principal.subject,
                    summary=body.summary,
                )
            )
        event(
            conn,
            "case.reviewed" if body.reviewed else "case.saved",
            {
                "actor": principal.subject,
                "case_id": identifier,
                "revision": row["revision"],
            },
        )
        return row


@router.patch("/{identifier}/status")
def change_status(
    identifier: str, body: CaseStatus, request: Request, principal=Depends(case_user)
):
    with request.app.state.store.engine.begin() as conn:
        row = owned(conn, identifier, principal.subject)
        if row["revision"] != body.revision:
            raise HTTPException(409, "This case changed; reopen it before changing its status")
        row = update(conn, row, status=body.status)
        event(
            conn,
            "case.status_changed",
            {"actor": principal.subject, "case_id": identifier, "status": body.status},
        )
        return row


def append_exchange(connection, row, prompt, answer, mode, truncated, warnings=None):
    current(owned(connection, row["id"], row["owner"]), row["revision"])
    details = {
        **row["details"],
        "draft": "",
        "messages": [
            *row["details"]["messages"],
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer},
        ],
    }
    if mode == "organize":
        details.update(summary=answer, reviewed=False)
    details["last_output_truncated"] = truncated
    details["quality_warnings"] = warnings or []
    return update(connection, row, details=details)
