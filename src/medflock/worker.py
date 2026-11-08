"""One database-scoped leader claims durable jobs; API replicas do not own training threads."""

import logging
import threading
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock
from sqlalchemy import select, text

from medflock.config import Settings
from medflock.node_policy import training_allowed
from medflock.service import Workbench
from medflock.store import Store, datasets, event, fleet, models, runs
from medflock.training.data import TaskContract
from medflock.training.engine import RunCancelled, TrainingConfig, train_run

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self, service):
        self.service = service
        self.stop = threading.Event()

    @contextmanager
    def leadership(self):
        engine = self.service.store.engine
        if engine.dialect.name == "postgresql":
            with engine.connect() as connection:
                acquired = connection.execute(text("SELECT pg_try_advisory_lock(794202)")).scalar()
                if not acquired:
                    raise RuntimeError("Another training worker holds the database lease")
                try:
                    yield
                finally:
                    connection.execute(text("SELECT pg_advisory_unlock(794202)"))
        else:
            lock_path = Path(engine.url.database).resolve().with_suffix(".worker.lock")
            with FileLock(str(lock_path), timeout=1):
                yield

    def recover(self):
        with self.service.store.engine.begin() as connection:
            interrupted = (
                connection.execute(select(runs.c.id).where(runs.c.status == "running"))
                .scalars()
                .all()
            )
            for identifier in interrupted:
                connection.execute(
                    runs.update()
                    .where(runs.c.id == identifier)
                    .values(status="aborted", error="Worker interrupted; retry as a new run")
                )
                event(connection, "run.aborted", {"run_id": identifier})

    def run(self):
        with self.leadership():
            self.recover()
            while not self.stop.is_set():
                with self.service.store.engine.connect() as connection:
                    row = (
                        connection.execute(
                            select(runs)
                            .where(runs.c.status == "queued")
                            .order_by(runs.c.created_at)
                            .limit(1)
                        )
                        .mappings()
                        .first()
                    )
                if row and self.service.store.claim(row["id"]):
                    self.execute(dict(row))
                else:
                    self.stop.wait(0.2)

    def execute(self, row):
        store = self.service.store
        identifier = row["id"]

        def cancelled():
            return self.stop.is_set() or store.get(runs, identifier)["status"] == "cancelled"

        def enabled(node_id):
            node = store.get(fleet, node_id)
            return training_allowed(node)

        try:
            config = TrainingConfig.model_validate(row["config"])
            dataset = store.get(datasets, config.dataset_id)
            contents = Path(dataset["path"]).read_bytes()
            import hashlib

            if hashlib.sha256(contents).hexdigest() != dataset["sha256"]:
                raise ValueError("Dataset snapshot has changed since registration")
            parent = store.get(models, config.parent_model) if config.parent_model else None
            result, manifest = train_run(
                config,
                contents,
                TaskContract.model_validate(dataset["contract"]),
                self.service.artifacts,
                identifier,
                lambda kind, detail: self.service.record(identifier, kind, detail),
                cancelled,
                parent=parent["manifest"] if parent else None,
                enabled=enabled,
            )
            if cancelled():
                raise RunCancelled()
            store.finish(identifier, result, manifest)
        except RunCancelled:
            store.cancel(identifier)
        except (ValueError, OSError) as error:
            logger.warning("Run %s failed: %s", identifier, type(error).__name__)
            store.fail(
                identifier,
                str(error)[:400]
                if isinstance(error, ValueError)
                else "Dataset or artifact unavailable; inspect local storage",
            )
        except Exception:
            logger.exception("Unexpected failure in run %s", identifier)
            store.fail(identifier, "Unexpected worker error; inspect operator logs")


def main():
    settings = Settings.load()
    store = Store(settings.database_url)
    worker = Worker(Workbench(store, settings.dataset, settings.artifacts))
    import signal

    signal.signal(signal.SIGTERM, lambda *_: worker.stop.set())
    signal.signal(signal.SIGINT, lambda *_: worker.stop.set())
    try:
        worker.run()
    finally:
        store.engine.dispose()


if __name__ == "__main__":
    main()
