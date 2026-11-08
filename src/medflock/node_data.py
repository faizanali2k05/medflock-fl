"""Prepared node bundles keep training records local while sharing a fixed model contract."""

import hashlib
import json
from pathlib import Path

import numpy as np

from medflock.learning import partition
from medflock.training.data import (
    default_contract,
    fit_transform,
    read_dataset,
    split_indices,
    transform,
)


def prepare(contents, directory, clients=3, seed=42, mode="label_skew"):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    contract = default_contract()
    values, labels, groups, _ = read_dataset(contents, contract)
    train_ids, _, _ = split_indices(labels, groups, seed)
    preprocessing = fit_transform(values[train_ids])
    values = transform(values[train_ids], preprocessing)
    labels = labels[train_ids]
    specification = {
        "contract": contract.model_dump(),
        "preprocessing": preprocessing,
        "features": values.shape[1],
        "family": "logistic",
    }
    digest = hashlib.sha256(json.dumps(specification, sort_keys=True).encode()).hexdigest()
    specification["digest"] = digest
    for index, indices in enumerate(partition(values, labels, clients, mode, seed)):
        node = directory / f"node-{index}"
        node.mkdir(exist_ok=True)
        np.savez(node / "training.npz", values=values[indices], labels=labels[indices])
        manifest = dict(
            specification,
            data_sha256=hashlib.sha256((node / "training.npz").read_bytes()).hexdigest(),
        )
        (node / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (directory / "server.json").write_text(json.dumps(specification, indent=2))
    return specification


def load_node(directory, expected_digest):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    specification = {
        key: manifest[key] for key in ["contract", "preprocessing", "features", "family"]
    }
    digest = hashlib.sha256(json.dumps(specification, sort_keys=True).encode()).hexdigest()
    if digest != expected_digest or manifest["digest"] != digest:
        raise ValueError("Node preprocessing/task contract does not match the coordinator")
    if (
        hashlib.sha256((directory / "training.npz").read_bytes()).hexdigest()
        != manifest["data_sha256"]
    ):
        raise ValueError("Node data checksum mismatch")
    with np.load(directory / "training.npz", allow_pickle=False) as archive:
        values, labels = archive["values"].copy(), archive["labels"].copy()
    if values.ndim != 2 or values.shape[1] != manifest["features"] or len(values) != len(labels):
        raise ValueError("Node data shape mismatch")
    if not np.isfinite(values).all() or not np.isin(labels, [0, 1]).all() or not len(labels):
        raise ValueError("Node training data is invalid")
    return values, labels
