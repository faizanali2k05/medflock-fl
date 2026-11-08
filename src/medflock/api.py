"""HTTP transport stays separate from training, persistence and GraphQL operations."""

import json
import logging
import threading
import time
import uuid
from contextlib import asynccontextmanager
from typing import Annotated

import jwt
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from medflock.accounts import quota
from medflock.accounts import router as account_router
from medflock.cases import router as case_router
from medflock.clinical_api import router as clinical_router
from medflock.config import Settings
from medflock.graphql import router
from medflock.hospitals import router as hospital_router
from medflock.security import authenticate
from medflock.service import Workbench
from medflock.store import Store, events, models, runs
from medflock.task import RESOURCES
from medflock.training.engine import TrainingConfig
from medflock.worker import Worker

logger = logging.getLogger(__name__)


def create_app(database_url=None, dataset=None, artifacts=None, settings=None):
    settings = settings or Settings.load()

    @asynccontextmanager
    async def lifespan(app):
        store = Store(database_url or settings.database_url)
        app.state.store = store
        app.state.settings = settings
        app.state.service = Workbench(
            store, dataset or settings.dataset, artifacts or settings.artifacts
        )
        app.state.service.ensure_default()
        if settings.issuer:
            app.state.jwks = jwt.PyJWKClient(
                settings.issuer.rstrip("/") + "/protocol/openid-connect/certs"
            )
        worker, thread = None, None
        if settings.embedded_worker:
            worker = Worker(app.state.service)
            thread = threading.Thread(target=worker.run, name="training-worker", daemon=True)
            thread.start()
        yield
        if worker:
            worker.stop.set()
            thread.join(timeout=60)
        store.engine.dispose()

    app = FastAPI(title="MedFlock API", version="0.2.0", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = uuid.uuid4().hex
        start = time.perf_counter()
        content_length = request.headers.get("content-length", "0")
        if not content_length.isdigit() or int(content_length) > 21 * 1024 * 1024:
            return JSONResponse(
                {"detail": "Request exceeds the 21 MiB transport limit"}, status_code=413
            )
        origin = request.headers.get("origin")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
            from urllib.parse import urlsplit

            if urlsplit(origin).netloc != request.headers.get("host"):
                return JSONResponse({"detail": "Cross-origin writes are disabled"}, status_code=403)
        try:
            if request.url.path.startswith(("/api/", "/graphql")):
                quota(
                    app.state.store,
                    "http:" + (request.client.host if request.client else "unknown"),
                    600,
                )
                if request.url.path == "/api/auth/login" or (
                    request.url.path == "/api/hospital-applications" and request.method == "POST"
                ):
                    quota(
                        app.state.store,
                        "login-ip:" + (request.client.host if request.client else "unknown"),
                        30,
                        300,
                    )
                else:
                    request.state.principal = authenticate(request)
                    if (
                        "client" in request.state.principal.roles
                        and not request.url.path.startswith(
                            ("/api/auth/", "/api/client/", "/api/workspace/")
                        )
                    ):
                        raise HTTPException(
                            403, "Client accounts can only access their assigned node"
                        )
                    if (
                        "hospital" in request.state.principal.roles
                        and not request.url.path.startswith(
                            (
                                "/api/auth/",
                                "/api/client/",
                                "/api/cases",
                                "/api/llm/",
                                "/api/workspace/",
                            )
                        )
                    ):
                        raise HTTPException(403, "Hospital accounts are scoped to their workspace")
                    quota(app.state.store, "account:" + request.state.principal.subject, 300)
            # Consume bounded bodies before endpoint parsing, including chunked requests.
            if request.method in {"POST", "PUT", "PATCH"}:
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > 21 * 1024 * 1024:
                        raise HTTPException(413, "Request body too large")
                request._body = bytes(body)
            response = await call_next(request)
        except HTTPException as error:
            return JSONResponse(
                {"detail": error.detail}, status_code=error.status_code, headers=error.headers
            )
        if request.url.path.startswith(("/api/", "/graphql")):
            response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-"
            "inline'; img-src 'self' data:; connect-src 'self'; frame-"
            "ancestors 'none'; base-uri 'self'; form-action 'self'"
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        logger.info(
            "request id=%s method=%s path=%s status=%s duration_ms=%.1f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - start) * 1000,
        )
        return response

    @app.exception_handler(ValueError)
    async def validation_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.get("/health/live")
    def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    def ready():
        with app.state.store.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ready", "schema": 3}

    @app.get("/api/status")
    def status(principal=Depends(authenticate)):
        principal.require()
        return {
            "name": "MedFlock",
            "version": "0.2.0",
            "clinical_review": "pending",
            "dataset_available": app.state.service.dataset.is_file(),
            "authentication": "required" if settings.auth_required else "local_development",
            "environment": settings.environment,
            "medication": "not_assessed",
            "embedded_worker": settings.embedded_worker,
        }

    @app.get("/api/runs", dependencies=[Depends(authenticate)])
    def list_runs():
        return app.state.store.list(runs)

    @app.post("/api/runs", status_code=202)
    def start_run(
        config: TrainingConfig,
        idempotency_key: Annotated[str, Header(min_length=8, max_length=128)],
        principal=Depends(authenticate),
    ):
        principal.require("researcher")
        quota(app.state.store, "training:" + principal.subject, 3, 3600)
        return app.state.service.submit(config.model_dump(), idempotency_key)

    @app.get("/api/runs/{run_id}", dependencies=[Depends(authenticate)])
    def get_run(run_id: str):
        row = app.state.store.get(runs, run_id)
        if not row:
            raise HTTPException(404, "Run not found")
        return row

    @app.get("/api/runs/{run_id}/export", dependencies=[Depends(authenticate)])
    def export(run_id: str):
        return Response(
            app.state.service.export(run_id),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="run-{run_id}.json"'},
        )

    @app.get("/api/models", dependencies=[Depends(authenticate)])
    def list_models():
        return app.state.store.list(models)

    @app.get("/api/audit", dependencies=[Depends(authenticate)])
    def audit(principal=Depends(authenticate)):
        principal.require("admin")
        return app.state.store.list(events)

    @app.post("/api/datasets", status_code=201)
    async def upload_dataset(
        file: UploadFile = File(),
        name: str = Form(),
        contract: str = Form(),
        source: str = Form(),
        permission: str = Form(),
        principal=Depends(authenticate),
    ):
        principal.require("operator")
        contents = await file.read(20 * 1024 * 1024 + 1)
        result = app.state.service.register_dataset(
            name, contents, json.loads(contract), {"source": source, "permission": permission}
        )
        return {key: value for key, value in result.items() if key != "path"}

    @app.post("/api/predict")
    def predict(body: dict, principal=Depends(authenticate)):
        principal.require()
        return app.state.service.predict(
            body.get("model_id"), body.get("features", body.get("patient", {}))
        )

    app.include_router(router(), prefix="/graphql")
    app.include_router(clinical_router)
    app.include_router(account_router)
    app.include_router(case_router)
    app.include_router(hospital_router)
    from medflock.management import router as management_router

    app.include_router(management_router)
    from medflock.workspace import router as workspace_router

    app.include_router(workspace_router)
    web = RESOURCES / "web"
    if (web / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=web / "assets"), name="assets")

    @app.get("/")
    def index():
        page = web / "index.html" if (web / "index.html").exists() else RESOURCES / "index.html"
        return FileResponse(page)

    @app.get("/{path:path}")
    def workspace_page(path: str):
        import re

        if not re.fullmatch(
            r"(?:cases(?:/[a-zA-Z0-9_-]+)?|institution|account|help|apply|evolution|"
            r"admin/(?:hospitals|users|clients|corpora|datasets|assistant|audit)|"
            r"research/(?:overview|experiments|datasets|fleet|models|model-lab|api-explorer))",
            path,
        ):
            raise HTTPException(404, "Not found")
        return index()

    return app


app = create_app()
