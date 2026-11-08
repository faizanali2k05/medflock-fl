"""Validation selects candidates; the held-out test split never controls optimization."""

import hashlib
import json
import time
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from medflock.experiment import aggregate
from medflock.learning import partition
from medflock.protocol import Contribution, tensor_hash
from medflock.training.data import (
    TaskContract,
    fit_transform,
    read_dataset,
    split_indices,
    transform,
)
from medflock.training.models import BinaryModel, evaluate


class TrainingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    dataset_id: str = "default"
    family: Literal["logistic", "mlp"] = "logistic"
    hidden: int = Field(default=16, ge=4, le=128)
    clients: int = Field(default=3, ge=2, le=20)
    rounds: int = Field(default=60, ge=1, le=500)
    local_epochs: int = Field(default=5, ge=1, le=100)
    learning_rate: float = Field(default=0.15, gt=0, le=1)
    l2: float = Field(default=0.01, ge=0, le=1)
    seed: int = Field(default=42, ge=0, le=2147483647)
    partition: Literal["iid", "label_skew", "feature_skew"] = "iid"
    aggregation: Literal["fedavg", "median", "trimmed_mean"] = "fedavg"
    attack: Literal["none", "sign_flip"] = "none"
    defense: Literal["none", "clip"] = "none"
    clip_norm: float = Field(default=1, gt=0, le=100)
    patience: int = Field(default=12, ge=2, le=100)
    parent_model: str | None = None

    @model_validator(mode="after")
    def valid_population(self):
        if self.attack != "none" or self.defense != "none" or self.aggregation != "fedavg":
            if self.clients < 5:
                raise ValueError(
                    "Attack and robust-aggregation experiments need at least five clients"
                )
        return self


class RunCancelled(Exception):
    pass


def load_artifact(manifest, directory):
    filename = manifest["file"]
    if Path(filename).name != filename:
        raise ValueError("Invalid artifact path")
    contents = (directory / filename).read_bytes()
    if hashlib.sha256(contents).hexdigest() != manifest["sha256"]:
        raise ValueError("Artifact integrity check failed")
    with np.load(directory / filename, allow_pickle=False) as archive:
        weights = archive["weights"].copy()
    if not np.isfinite(weights).all():
        raise ValueError("Artifact contains non-finite weights")
    return weights


def train_run(
    config,
    contents,
    contract: TaskContract,
    output,
    run_id,
    emit,
    cancelled,
    parent=None,
    enabled=lambda node_id: True,
):
    values, labels, groups, profile = read_dataset(contents, contract)
    train_ids, val_ids, test_ids = split_indices(labels, groups, config.seed)
    state = fit_transform(values[train_ids])
    model = BinaryModel(len(contract.features), config.family, config.hidden)
    initial = model.initialize(config.seed)
    if parent:
        if parent.get("contract_hash") != contract.digest or parent.get("family") != config.family:
            raise ValueError("Warm-start model does not match the task and model family")
        if parent.get("hidden") != config.hidden:
            raise ValueError("Warm-start hidden dimension differs")
        initial = load_artifact(parent, output)
        state = parent["preprocessing"]
    if initial.shape != (model.size,):
        raise ValueError("Initial tensor shape does not match the model")
    x = transform(values, state)
    parts = partition(
        x[train_ids], labels[train_ids], config.clients, config.partition, config.seed
    )
    if any(len(part) < 2 for part in parts):
        raise ValueError("Each client needs at least two training examples")
    wire_hash = hashlib.sha256(
        json.dumps(
            {
                "task": contract.digest,
                "family": config.family,
                "hidden": config.hidden,
                "preprocessing": state,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    profile.update(
        train_count=len(train_ids), validation_count=len(val_ids), test_count=len(test_ids)
    )
    split_hash = hashlib.sha256(
        json.dumps([a.tolist() for a in [train_ids, val_ids, test_ids]]).encode()
    ).hexdigest()
    counts = [len(p) for p in parts]
    for index, part in enumerate(parts):
        emit(
            "node.assigned",
            {
                "node_id": f"simulated-{index + 1}",
                "count": len(part),
                "events": int(labels[train_ids[part]].sum()),
            },
        )

    def baseline(ids):
        weights, best, loss = initial.copy(), initial.copy(), float("inf")
        for _ in range(config.rounds):
            if cancelled():
                raise RunCancelled()
            weights = model.train(
                weights, x[ids], labels[ids], config.local_epochs, config.learning_rate, config.l2
            )
            candidate = evaluate(model, weights, x[val_ids], labels[val_ids])["brier"]
            if candidate < loss:
                best, loss = weights.copy(), candidate
        return evaluate(model, best, x[test_ids], labels[test_ids])

    centralized = baseline(train_ids)
    local_results = [baseline(train_ids[p]) for p in parts]
    emit("baselines.completed", {"approaches": config.clients + 1})
    weights, best = initial.copy(), initial.copy()
    best_loss, best_round, stale = float("inf"), 0, 0
    history = []
    for number in range(1, config.rounds + 1):
        if cancelled():
            raise RunCancelled()
        start = time.perf_counter()
        updates, active_counts = [], []
        base_hash = tensor_hash(weights)
        for index, part in enumerate(parts):
            node_id = f"simulated-{index + 1}"
            if not enabled(node_id):
                emit(
                    "contribution.skipped",
                    {"node_id": node_id, "round": number, "reason": "node_suspended"},
                )
                continue
            candidate = model.train(
                weights,
                x[train_ids[part]],
                labels[train_ids[part]],
                config.local_epochs,
                config.learning_rate,
                config.l2,
            )
            delta = candidate - weights
            if config.attack == "sign_flip" and index == 0:
                delta *= -10
            norm = float(np.linalg.norm(delta))
            clipped = config.defense == "clip" and norm > config.clip_norm
            if clipped:
                delta *= config.clip_norm / norm
            candidate = weights + delta
            envelope = Contribution(
                contract_hash=wire_hash,
                base_model_hash=base_hash,
                update_hash=tensor_hash(candidate),
                round_number=number,
                sample_count=len(part),
            )
            envelope.validate_for(
                candidate,
                contract_hash=wire_hash,
                base_model_hash=base_hash,
                round_number=number,
                expected_shape=(model.size,),
                expected_count=len(part),
            )
            updates.append(candidate)
            active_counts.append(counts[index])
            emit(
                "contribution.accepted",
                {
                    "node_id": node_id,
                    "round": number,
                    "count": len(part),
                    "norm": norm,
                    "clipped": clipped,
                    "envelope": envelope.model_dump(),
                },
            )
        required = (
            5
            if config.aggregation != "fedavg" or config.defense != "none" or config.attack != "none"
            else 2
        )
        if len(updates) < required:
            raise ValueError(f"Insufficient active contributors: need {required}")
        if config.aggregation == "median":
            weights = np.median(updates, axis=0)
        elif config.aggregation == "trimmed_mean":
            cut = max(1, len(updates) // 5)
            weights = np.sort(updates, axis=0)[cut:-cut].mean(axis=0)
        else:
            weights = aggregate(updates, active_counts, number)
        validation = evaluate(model, weights, x[val_ids], labels[val_ids])
        if validation["brier"] < best_loss - 1e-5:
            best, best_loss, best_round, stale = weights.copy(), validation["brier"], number, 0
        else:
            stale += 1
        detail = {
            "number": number,
            "contributors": len(updates),
            "validation": validation,
            "train_brier": evaluate(model, weights, x[train_ids], labels[train_ids])["brier"],
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
        }
        history.append(detail)
        emit("round.completed", detail)
        if stale >= config.patience:
            break
    output.mkdir(parents=True, exist_ok=True)
    filename = f"{run_id}.npz"
    temporary = output / f"{run_id}.pending.npz"
    np.savez(temporary, weights=best)
    temporary.replace(output / filename)
    manifest = {
        "id": run_id,
        "format_version": 2,
        "file": filename,
        "sha256": hashlib.sha256((output / filename).read_bytes()).hexdigest(),
        "contract": contract.model_dump(),
        "contract_hash": contract.digest,
        "wire_contract_hash": wire_hash,
        "preprocessing": state,
        "family": config.family,
        "hidden": config.hidden,
        "parameters": model.size,
        "parent_model": config.parent_model,
        "selected_round": best_round,
        "source_sha256": hashlib.sha256(contents).hexdigest(),
        "split_hash": split_hash,
        "clinical_status": "research_only",
    }
    result = {
        "run_id": run_id,
        "federation": "simulated_in_process",
        "config": config.model_dump(),
        "clinical_status": "research_only",
        "medication_status": "not_assessed",
        "contract_hash": contract.digest,
        "cohort": profile,
        "split_hash": split_hash,
        "centralized": centralized,
        "local_only": local_results,
        "fedavg": evaluate(model, best, x[test_ids], labels[test_ids]),
        "selected_round": best_round,
        "completed_rounds": len(history),
        "history": history,
        "partitions": [
            {"node": i + 1, "count": len(p), "events": int(labels[train_ids[p]].sum())}
            for i, p in enumerate(parts)
        ],
        "limitations": [
            "Public-data simulation; not independent hospital validation",
            "Preprocessing fitted on pooled training data for this benchmark",
            "Repeated test inspection is development, not external validation",
            "Warm-start scores may overlap a parent's earlier training population"
            if parent
            else "No warm-start used",
        ],
    }
    (output / f"{run_id}.manifest.json").write_text(json.dumps(manifest, indent=2))
    (output / f"{run_id}.json").write_text(json.dumps(result, indent=2))
    return result, manifest


def predict(manifest, features, output):
    contract = TaskContract.model_validate(manifest["contract"])
    if manifest["contract_hash"] != contract.digest:
        raise ValueError("Stored task contract is inconsistent")
    names = [feature.name for feature in contract.features]
    if set(features) != set(names):
        raise ValueError("Prediction fields must match the model's task contract")
    values = np.array(
        [[features[name] if features[name] is not None else np.nan for name in names]], dtype=float
    )
    if np.isinf(values).any():
        raise ValueError("Infinite inputs are not supported")
    for index, feature in enumerate(contract.features):
        value = values[0, index]
        if np.isnan(value):
            continue
        if feature.kind == "binary" and value not in [0, 1]:
            raise ValueError(f"{feature.name} must be 0 or 1")
        if feature.minimum is not None and value < feature.minimum:
            raise ValueError(f"{feature.name} is below the permitted range")
        if feature.maximum is not None and value > feature.maximum:
            raise ValueError(f"{feature.name} is above the permitted range")
    model = BinaryModel(len(names), manifest["family"], manifest["hidden"])
    weights = load_artifact(manifest, output)
    if weights.shape != (model.size,):
        raise ValueError("Artifact architecture mismatch")
    transformed = transform(values, manifest["preprocessing"])
    score = float(model.predict(weights, transformed)[0])
    return {
        "score": score,
        "model_id": manifest["id"],
        "clinical_status": "research_only",
        "medication_status": "not_assessed",
        "imputed_features": [names[i] for i in np.flatnonzero(np.isnan(values[0]))],
        "interpretation": "Uncalibrated experimental outcome score; no treatment inference",
    }
