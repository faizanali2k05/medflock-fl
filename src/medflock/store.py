"""Single-worker transactions make retries durable without distributed orchestration."""

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    JSON,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.exc import IntegrityError

metadata = MetaData()
cases = Table(
    "care_cases",
    metadata,
    Column("id", String, primary_key=True),
    Column("owner", String, nullable=False, index=True),
    Column("title", String, nullable=False),
    Column("status", String, nullable=False),
    Column("revision", Integer, nullable=False),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
    Column("details", JSON, nullable=False),
)
case_reviews = Table(
    "case_reviews",
    metadata,
    Column("id", String, primary_key=True),
    Column("case_id", String, nullable=False, index=True),
    Column("revision", Integer, nullable=False),
    Column("created_at", String, nullable=False),
    Column("reviewer", String, nullable=False),
    Column("summary", String, nullable=False),
    UniqueConstraint("case_id", "revision"),
)
nodes = Table("nodes", metadata, Column("id", String, primary_key=True), Column("kind", String))
snapshots = Table(
    "snapshots",
    metadata,
    Column("id", String, primary_key=True),
    Column("details", JSON),
)
runs = Table(
    "runs",
    metadata,
    Column("id", String, primary_key=True),
    Column("request_key", String, unique=True),
    Column("request_hash", String),
    Column("status", String),
    Column("created_at", String),
    Column("config", JSON),
    Column("result", JSON),
    Column("error", String),
)
rounds = Table(
    "rounds",
    metadata,
    Column("id", String, primary_key=True),
    Column("run_id", String),
    Column("number", Integer),
    Column("details", JSON),
    UniqueConstraint("run_id", "number"),
)
contributions = Table(
    "contributions",
    metadata,
    Column("id", String, primary_key=True),
    Column("run_id", String),
    Column("round_number", Integer),
    Column("node_id", String),
    Column("details", JSON),
    UniqueConstraint("run_id", "round_number", "node_id"),
)
models = Table(
    "model_versions",
    metadata,
    Column("id", String, primary_key=True),
    Column("run_id", String),
    Column("status", String),
    Column("manifest", JSON),
)
approvals = Table(
    "approvals",
    metadata,
    Column("id", String, primary_key=True),
    Column("model_id", String),
    Column("details", JSON),
)
events = Table(
    "audit_events",
    metadata,
    Column("id", String, primary_key=True),
    Column("created_at", String),
    Column("kind", String),
    Column("details", JSON),
)


def now():
    return datetime.now(timezone.utc).isoformat()


stream = Table(
    "event_stream",
    metadata,
    Column("sequence", Integer, primary_key=True, autoincrement=True),
    Column("event_id", String, unique=True, nullable=False),
    Column("created_at", String),
    Column("kind", String),
    Column("details", JSON),
)
datasets = Table(
    "datasets",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String),
    Column("created_at", String),
    Column("path", String),
    Column("sha256", String),
    Column("contract", JSON),
    Column("profile", JSON),
    Column("provenance", JSON),
)
fleet = Table(
    "node_registry",
    metadata,
    Column("id", String, primary_key=True),
    Column("label", String),
    Column("status", String),
    Column("created_at", String),
    Column("kind", String),
    Column("last_seen", String),
    Column("details", JSON),
)
schema_versions = Table(
    "schema_versions",
    metadata,
    Column("version", Integer, primary_key=True),
    Column("applied_at", String),
)


def event(connection, kind, details):
    if connection.dialect.name == "postgresql":
        from sqlalchemy import text

        connection.execute(text("SELECT pg_advisory_xact_lock(794203)"))
    event_id, timestamp = uuid.uuid4().hex, now()
    connection.execute(
        events.insert().values(
            id=event_id,
            created_at=timestamp,
            kind=kind,
            details=details,
        )
    )
    connection.execute(
        stream.insert().values(
            event_id=event_id,
            created_at=timestamp,
            kind=kind,
            details=details,
        )
    )


def migrate(engine):
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            from sqlalchemy import text

            connection.execute(text("SELECT pg_advisory_xact_lock(794201)"))
        metadata.create_all(connection)
        for version in [1, 2, 3]:
            if not connection.execute(
                select(schema_versions).where(schema_versions.c.version == version)
            ).first():
                connection.execute(
                    schema_versions.insert().values(version=version, applied_at=now())
                )


class Store:
    def __init__(self, url=None):
        Path("runtime").mkdir(exist_ok=True)
        url = url or os.getenv("MEDFLOCK_DATABASE_URL", "sqlite:///runtime/medflock.db")
        options = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, connect_args=options)
        migrate(self.engine)

    def get(self, table, identifier):
        with self.engine.connect() as conn:
            row = conn.execute(select(table).where(table.c.id == identifier)).mappings().first()
        return dict(row) if row else None

    def activity(self, after=0, limit=100):
        with self.engine.connect() as conn:
            query = select(stream).where(stream.c.sequence > after).order_by(stream.c.sequence)
            return [dict(row) for row in conn.execute(query.limit(min(limit, 200))).mappings()]

    def cancel(self, run_id):
        with self.engine.begin() as conn:
            changed = conn.execute(
                runs.update()
                .where((runs.c.id == run_id) & runs.c.status.in_(["queued", "running"]))
                .values(status="cancelled")
            )
            if changed.rowcount:
                event(conn, "run.cancelled", {"run_id": run_id})
        return bool(changed.rowcount)

    def create_run(self, key, config):
        digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
        row = dict(
            id=uuid.uuid4().hex,
            request_key=key,
            request_hash=digest,
            status="queued",
            created_at=now(),
            config=config,
            result=None,
            error=None,
        )
        try:
            with self.engine.begin() as conn:
                if os.getenv("MEDFLOCK_ENV") == "production":
                    if conn.dialect.name == "postgresql":
                        from sqlalchemy import text

                        conn.execute(text("SELECT pg_advisory_xact_lock(794204)"))
                    previous = (
                        conn.execute(select(runs).where(runs.c.request_key == key))
                        .mappings()
                        .first()
                    )
                    if previous:
                        if previous["request_hash"] != digest:
                            raise ValueError(
                                "Idempotency key already belongs to different settings"
                            )
                        return dict(previous), False
                    pending = conn.execute(
                        select(runs.c.id).where(runs.c.status.in_(["queued", "running"]))
                    ).all()
                    if len(pending) >= 3:
                        raise ValueError("Training queue is full; wait for current jobs")
                conn.execute(runs.insert().values(**row))
                event(conn, "run.queued", {"run_id": row["id"], "config": config})
            return row, True
        except IntegrityError:
            with self.engine.connect() as conn:
                previous = dict(
                    conn.execute(select(runs).where(runs.c.request_key == key)).mappings().one()
                )
            if previous["request_hash"] != digest:
                raise ValueError("Idempotency key already belongs to different settings")
            return previous, False

    def list(self, table, limit=100):
        with self.engine.connect() as conn:
            query = select(table)
            if "created_at" in table.c:
                query = query.order_by(table.c.created_at.desc())
            return [dict(row) for row in conn.execute(query.limit(limit)).mappings()]

    def recover(self):
        with self.engine.begin() as conn:
            stale = (
                conn.execute(select(runs.c.id).where(runs.c.status.in_(["queued", "running"])))
                .scalars()
                .all()
            )
            for run_id in stale:
                conn.execute(
                    runs.update()
                    .where(runs.c.id == run_id)
                    .values(status="aborted", error="Worker restarted; submit a new run")
                )
                event(conn, "run.aborted", {"run_id": run_id, "reason": "restart"})

    def claim(self, run_id):
        with self.engine.begin() as conn:
            changed = conn.execute(
                runs.update()
                .where((runs.c.id == run_id) & (runs.c.status == "queued"))
                .values(status="running")
            )
            return changed.rowcount == 1

    def fail(self, run_id, reason):
        with self.engine.begin() as conn:
            changed = conn.execute(
                runs.update()
                .where((runs.c.id == run_id) & (runs.c.status == "running"))
                .values(status="failed", error=reason)
            )
            if not changed.rowcount:
                return False
            event(conn, "run.failed", {"run_id": run_id, "reason": reason})

    def finish(self, run_id, result, manifest):
        with self.engine.begin() as conn:
            changed = conn.execute(
                runs.update()
                .where((runs.c.id == run_id) & (runs.c.status == "running"))
                .values(status="completed", result=result)
            )
            if not changed.rowcount:
                return False
            conn.execute(
                models.insert().values(
                    id=run_id, run_id=run_id, status="research_candidate", manifest=manifest
                )
            )
            event(conn, "model.candidate", {"model_id": run_id, "sha256": manifest["sha256"]})
