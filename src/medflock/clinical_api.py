"""Clinical evidence and human review remain separate from research model activation."""

import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from medflock.security import authenticate
from medflock.store import approvals, event, models, snapshots
from medflock.validation import evaluate_cohort

router = APIRouter(prefix="/api/validation", tags=["Clinical evidence"])


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: str = Field(pattern=r"^(request_changes|reject|accept_for_pilot_review)$")
    professional_registration: str = Field(min_length=4, max_length=120)
    evidence_reference: str = Field(min_length=8, max_length=500)
    findings: str = Field(min_length=20, max_length=5000)


@router.post("/evaluate", status_code=201)
async def evaluate(
    request: Request,
    file: UploadFile = File(),
    plan: str = Form(),
    model_id: str = Form(),
    principal=Depends(authenticate),
):
    principal.require("operator")
    model = request.app.state.store.get(models, model_id)
    if not model:
        raise HTTPException(404, "Model not found")
    configuration = json.loads(plan)
    if configuration.get("model_sha256") != model["manifest"]["sha256"]:
        raise ValueError("Evaluation plan does not identify this model artifact")
    if configuration.get("task_id") != model["manifest"].get("contract", {}).get("id"):
        raise ValueError("Evaluation task does not match the model contract")
    contents = await file.read(10 * 1024**2 + 1)
    if len(contents) > 10 * 1024**2:
        raise HTTPException(413, "Evaluation CSV exceeds 10 MiB")
    report = await run_in_threadpool(evaluate_cohort, contents, configuration)
    identifier = "validation_" + report["report_hash"]
    report["model_id"] = model_id
    store = request.app.state.store
    with store.engine.begin() as connection:
        if not connection.execute(select(snapshots).where(snapshots.c.id == identifier)).first():
            connection.execute(snapshots.insert().values(id=identifier, details=report))
            event(
                connection,
                "validation.evaluated",
                {
                    "report_hash": report["report_hash"],
                    "model_id": model_id,
                    "actor": principal.subject,
                },
            )
    return report


@router.get("/reports")
def reports(request: Request, principal=Depends(authenticate)):
    principal.require()
    with request.app.state.store.engine.connect() as connection:
        return list(
            connection.execute(
                select(snapshots.c.details).where(snapshots.c.id.like("validation_%")).limit(100)
            ).scalars()
        )


@router.post("/reviews", status_code=201)
def review(request: Request, body: Review, principal=Depends(authenticate)):
    principal.require("clinician")
    record = request.app.state.store.get(snapshots, "validation_" + body.report_hash)
    if not record:
        raise HTTPException(404, "Validation report not found")
    identifier = uuid.uuid4().hex
    details = {
        **body.model_dump(),
        "reviewer_subject": principal.subject,
        "clinical_release_authorized": False,
    }
    with request.app.state.store.engine.begin() as connection:
        connection.execute(
            approvals.insert().values(
                id=identifier, model_id=record["details"]["model_id"], details=details
            )
        )
        event(
            connection,
            "validation.reviewed",
            {
                "review_id": identifier,
                "report_hash": body.report_hash,
                "actor": principal.subject,
                "decision": body.decision,
            },
        )
    return {"id": identifier, **details}
