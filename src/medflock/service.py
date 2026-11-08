"""Application operations are shared by GraphQL, REST and the independent queue worker."""

import hashlib
import json
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from medflock.store import contributions, datasets, event, fleet, models, now, rounds, runs
from medflock.training.data import TaskContract, default_contract, read_dataset
from medflock.training.engine import TrainingConfig, predict


class Workbench:
    def __init__(self, store, dataset, artifacts):
        self.store, self.dataset, self.artifacts = store, Path(dataset), Path(artifacts)

    def register_dataset(self, name, contents, contract, provenance):
        if len(contents) > 20 * 1024 * 1024:
            raise ValueError("CSV uploads are limited to 20 MiB")
        if not provenance.get("source") or not provenance.get("permission"):
            raise ValueError("Source and permission declarations are required")
        contract = TaskContract.model_validate(contract)
        _, _, _, profile = read_dataset(contents, contract)
        digest = hashlib.sha256(contents).hexdigest()
        identifier = hashlib.sha256((digest + contract.digest).encode()).hexdigest()[:24]
        existing = self.store.get(datasets, identifier)
        if existing:
            return existing
        directory = self.artifacts / "datasets"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{identifier}.csv"
        path.write_bytes(contents)
        record = dict(
            id=identifier,
            name=name[:120],
            created_at=now(),
            path=str(path.resolve()),
            sha256=digest,
            contract=contract.model_dump(),
            profile=profile,
            provenance=provenance,
        )
        try:
            with self.store.engine.begin() as connection:
                connection.execute(datasets.insert().values(**record))
                event(
                    connection,
                    "dataset.registered",
                    {
                        "dataset_id": identifier,
                        "name": name[:120],
                        "eligible_rows": profile["eligible_rows"],
                    },
                )
        except IntegrityError:
            existing = self.store.get(datasets, identifier)
            if existing is None:
                raise
            return existing
        return record

    def ensure_default(self):
        if not self.dataset.is_file():
            return None
        contents = self.dataset.read_bytes()
        known = hashlib.sha256(contents).hexdigest() == (
            "9c73cea7468ff5d517801ec050fe9993da5912fce4b56f296f8df3b38dd75912"
        )
        return self.register_dataset(
            "UCI heart failure - 90-day outcome" if known else "Configured research dataset",
            contents,
            default_contract().model_dump(),
            {
                "source": "UCI 519" if known else "operator-configured local file",
                "permission": "CC BY 4.0" if known else "operator responsible for permission",
                "scope": "research benchmark",
            },
        )

    def submit(self, config, key):
        config = TrainingConfig.model_validate(config)
        import os

        if os.getenv("MEDFLOCK_ENV") == "production" and (
            config.rounds > 100
            or config.local_epochs > 10
            or config.clients > 10
            or config.hidden > 32
        ):
            raise ValueError("Shared-host training limits: 100 rounds, 10 epochs/clients, width 32")
        if not 8 <= len(key) <= 128:
            raise ValueError("Idempotency key must contain 8–128 characters")
        if config.dataset_id == "default":
            dataset = self.ensure_default()
        else:
            dataset = self.store.get(datasets, config.dataset_id)
        if dataset is None:
            raise ValueError("Dataset not found; import a dataset first")
        config.dataset_id = dataset["id"]
        if config.parent_model and not self.store.get(models, config.parent_model):
            raise ValueError("Parent model not found")
        row, _ = self.store.create_run(key, config.model_dump())
        return row

    def register_node(self, identifier, label):
        if not identifier or len(identifier) > 64 or not identifier.replace("-", "").isalnum():
            raise ValueError("Node IDs must be alphanumeric with optional hyphens")
        record = dict(
            id=identifier,
            label=label[:120],
            status="active",
            created_at=now(),
            kind="simulated",
            last_seen=None,
            details={},
        )
        with self.store.engine.begin() as connection:
            if connection.execute(select(fleet).where(fleet.c.id == identifier)).first():
                raise ValueError("Node already exists")
            connection.execute(fleet.insert().values(**record))
            event(connection, "node.registered", {"node_id": identifier})
        return record

    def set_node_status(self, identifier, status, suspended_until=None, actor=None):
        if status not in {"active", "paused", "restricted", "suspended"}:
            raise ValueError("Unsupported node policy")
        node = self.store.get(fleet, identifier)
        if not node:
            raise ValueError("Node not found")
        if node["status"] == "removed":
            raise ValueError("Revoked nodes cannot be restored; register a new node identity")
        details = dict(node["details"])
        details.pop("suspended_until", None)
        details.pop("resume_status", None)
        if suspended_until:
            from medflock.node_policy import effective_status

            details["suspended_until"] = suspended_until
            previous = effective_status(node)
            details["resume_status"] = previous if previous != "suspended" else "paused"
        with self.store.engine.begin() as connection:
            changed = connection.execute(
                fleet.update()
                .where(fleet.c.id == identifier, fleet.c.status != "removed")
                .values(status=status, details=details)
            )
            if changed.rowcount != 1:
                raise ValueError("Node was revoked during the policy change")
            event(
                connection,
                "node.status_changed",
                {
                    "node_id": identifier,
                    "status": status,
                    "suspended_until": suspended_until,
                    "actor": actor,
                },
            )
        return self.store.get(fleet, identifier)

    def record(self, run_id, kind, detail):
        detail = {**detail, "run_id": run_id}
        with self.store.engine.begin() as connection:
            if kind == "node.assigned":
                node_id = detail["node_id"]
                if not connection.execute(select(fleet).where(fleet.c.id == node_id)).first():
                    connection.execute(
                        fleet.insert().values(
                            id=node_id,
                            label=node_id,
                            status="active",
                            created_at=now(),
                            kind="simulated",
                            details=detail,
                        )
                    )
            if kind == "contribution.accepted":
                connection.execute(
                    contributions.insert().values(
                        id=uuid.uuid4().hex,
                        run_id=run_id,
                        round_number=detail["round"],
                        node_id=detail["node_id"],
                        details=detail,
                    )
                )
                connection.execute(
                    fleet.update()
                    .where(fleet.c.id == detail["node_id"])
                    .values(last_seen=now(), details=detail)
                )
            if kind == "round.completed":
                connection.execute(
                    rounds.insert().values(
                        id=uuid.uuid4().hex, run_id=run_id, number=detail["number"], details=detail
                    )
                )
            event(connection, kind, detail)

    def promote(self, model_id, reason):
        candidate = self.store.get(models, model_id)
        if not candidate or candidate["manifest"].get("format_version") != 2:
            raise ValueError("A version-2 research candidate is required")
        if len(reason.strip()) < 8:
            raise ValueError("Record the reason for research activation")
        from medflock.training.engine import load_artifact

        load_artifact(candidate["manifest"], self.artifacts)
        with self.store.engine.begin() as connection:
            connection.execute(
                models.update()
                .where(models.c.status == "active_research")
                .values(status="research_candidate")
            )
            connection.execute(
                models.update().where(models.c.id == model_id).values(status="active_research")
            )
            event(
                connection,
                "model.activated",
                {"model_id": model_id, "reason": reason[:500], "clinical_approval": False},
            )
        return self.store.get(models, model_id)

    def predict(self, model_id, features):
        if not isinstance(features, dict):
            raise ValueError("Features must be a JSON object")
        model = self.store.get(models, model_id)
        if not model or model["manifest"].get("format_version") != 2:
            raise ValueError("Select a model trained with the current pipeline")
        return predict(model["manifest"], features, self.artifacts)

    def export(self, run_id):
        record = self.store.get(runs, run_id)
        if not record or not record["result"]:
            raise ValueError("Completed run not found")
        return json.dumps(record["result"], indent=2)
