"""Paired baselines share initialization, preprocessing, training rows and holdout rows."""

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Literal

import numpy as np
from flwr.app import ArrayRecord, MetricRecord, RecordDict
from flwr.serverapp.strategy.strategy_utils import aggregate_arrayrecords
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sklearn.model_selection import train_test_split

from medflock.learning import metrics, partition, train
from medflock.protocol import Contribution, tensor_hash
from medflock.store import contributions, event, nodes, rounds, snapshots
from medflock.task import CONTRACT_HASH, FEATURES, load_cohort, transform


class ExperimentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    clients: int = Field(default=3, ge=2, le=10)
    rounds: int = Field(default=20, ge=1, le=100)
    local_epochs: int = Field(default=5, ge=1, le=20)
    learning_rate: float = Field(default=0.1, gt=0, le=1)
    seed: int = Field(default=42, ge=0, le=2147483647)
    partition: Literal["iid", "label_skew", "feature_skew"] = "iid"
    attack: Literal["none", "sign_flip"] = "none"
    defense: Literal["none", "clip"] = "none"
    clip_norm: float = Field(default=0.1, gt=0, le=100)

    @model_validator(mode="after")
    def defense_cohort(self):
        if (self.attack != "none" or self.defense != "none") and self.clients < 5:
            raise ValueError("Defense experiments require at least five simulated clients")
        return self


def aggregate(updates, counts, round_number):
    records = []
    for weights, count in zip(updates, counts, strict=True):
        if count <= 0:
            raise ValueError("Contribution counts must be positive")
        records.append(
            RecordDict(
                {
                    "arrays": ArrayRecord([weights]),
                    "metrics": MetricRecord({"num-examples": int(count)}),
                }
            )
        )
    if not records:
        raise ValueError("No contributions received")
    arrays = aggregate_arrayrecords(records, "num-examples")
    return arrays.to_numpy_ndarrays()[0]


def validate_update(update, expected_shape):
    if update.shape != expected_shape or not np.isfinite(update).all():
        raise ValueError("Invalid contribution shape or non-finite tensors")


def run_experiment(config: ExperimentConfig, dataset: Path, output: Path, run_id, store=None):
    frame, cohort = load_cohort(dataset)
    x, y = transform(frame), frame.target.to_numpy()
    train_ids, test_ids = train_test_split(
        np.arange(len(y)),
        test_size=0.25,
        random_state=config.seed,
        stratify=y,
    )
    parts = partition(x[train_ids], y[train_ids], config.clients, config.partition, config.seed)
    if any(len(part) == 0 for part in parts):
        raise ValueError("Empty client partition")
    weights = np.zeros(len(FEATURES) + 1)
    centralized = train(
        weights,
        x[train_ids],
        y[train_ids],
        config.rounds * config.local_epochs,
        config.learning_rate,
    )
    local_results = []
    for part in parts:
        local = train(
            weights,
            x[train_ids[part]],
            y[train_ids[part]],
            config.rounds * config.local_epochs,
            config.learning_rate,
        )
        local_results.append(metrics(local, x[test_ids], y[test_ids]))
    cohort["train_count"], cohort["test_count"] = len(train_ids), len(test_ids)
    counts = [len(part) for part in parts]
    split = {
        "train": frame.row_id.iloc[train_ids].tolist(),
        "test": frame.row_id.iloc[test_ids].tolist(),
    }
    split_hash = hashlib.sha256(json.dumps(split, sort_keys=True).encode()).hexdigest()
    if store:
        with store.engine.begin() as conn:
            if not conn.execute(
                snapshots.select().where(snapshots.c.id == cohort["source_sha256"])
            ).first():
                conn.execute(snapshots.insert().values(id=cohort["source_sha256"], details=cohort))
            for index in range(config.clients):
                node_id = f"simulated-{index + 1}"
                if not conn.execute(nodes.select().where(nodes.c.id == node_id)).first():
                    conn.execute(nodes.insert().values(id=node_id, kind="simulated"))
    history = []
    for number in range(1, config.rounds + 1):
        base_hash = tensor_hash(weights)
        updates, records = [], []
        for index, part in enumerate(parts):
            candidate = train(
                weights,
                x[train_ids[part]],
                y[train_ids[part]],
                config.local_epochs,
                config.learning_rate,
            )
            delta = candidate - weights
            if config.attack == "sign_flip" and index == 0:
                delta = -10 * delta
            norm = float(np.linalg.norm(delta))
            clipped = config.defense == "clip" and norm > config.clip_norm
            if clipped:
                delta *= config.clip_norm / norm
            update = weights + delta
            validate_update(update, weights.shape)
            envelope = Contribution(
                contract_hash=CONTRACT_HASH,
                base_model_hash=base_hash,
                update_hash=tensor_hash(update),
                round_number=number,
                sample_count=len(part),
            )
            envelope.validate_for(
                update,
                contract_hash=CONTRACT_HASH,
                base_model_hash=base_hash,
                round_number=number,
                expected_shape=weights.shape,
                expected_count=len(part),
            )
            updates.append(update)
            records.append(
                {
                    "count": len(part),
                    "update_norm": norm,
                    "clipped": clipped,
                    "envelope": envelope.model_dump(),
                }
            )
        weights = aggregate(updates, counts, number)
        detail = {
            "number": number,
            "contributors": len(parts),
            "train_brier": metrics(weights, x[train_ids], y[train_ids])["brier"],
        }
        history.append(detail)
        if store:
            with store.engine.begin() as conn:
                conn.execute(
                    rounds.insert().values(
                        id=uuid.uuid4().hex, run_id=run_id, number=number, details=detail
                    )
                )
                for index, record in enumerate(records):
                    conn.execute(
                        contributions.insert().values(
                            id=uuid.uuid4().hex,
                            run_id=run_id,
                            round_number=number,
                            node_id=f"simulated-{index + 1}",
                            details=record,
                        )
                    )
                event(conn, "round.completed", {"run_id": run_id, "number": number})
    result = {
        "run_id": run_id,
        "federation": "simulated_in_process",
        "engine": "Flower 1.39.0 FedAvg array-record aggregation utility",
        "clinical_status": "research_only",
        "medication_status": "not_assessed",
        "contract_hash": CONTRACT_HASH,
        "cohort": cohort,
        "split_hash": split_hash,
        "config": config.model_dump(),
        "centralized": metrics(centralized, x[test_ids], y[test_ids]),
        "local_only": local_results,
        "fedavg": metrics(weights, x[test_ids], y[test_ids]),
        "partitions": [
            {"node": i + 1, "count": len(p), "events": int(y[train_ids[p]].sum())}
            for i, p in enumerate(parts)
        ],
        "history": history,
        "limitations": [
            "Repeated holdout inspection makes this a development benchmark",
            "Early-censoring exclusions may bias estimates",
            "No confidence interval or external clinical validation",
            "Local baselines use the same pooled holdout, not site-specific test sets",
            "Sign-flip experiment is one synthetic attacker, not poisoning detection",
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    model_path = output / f"{run_id}.npz"
    temporary = output / f"{run_id}.pending.npz"
    np.savez(temporary, weights=weights)
    os.replace(temporary, model_path)
    manifest = {
        "id": run_id,
        "contract_hash": CONTRACT_HASH,
        "sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "file": model_path.name,
        "source_sha256": cohort["source_sha256"],
        "split_hash": split_hash,
        "clinical_status": "research_only",
    }
    (output / f"{run_id}.json").write_text(json.dumps(result, indent=2))
    (output / f"{run_id}.manifest.json").write_text(json.dumps(manifest, indent=2))
    return result, manifest
