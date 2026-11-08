"""Transform a hospital-local CSV using an agreed specification; no records are uploaded."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from medflock.local_mapping import LocalMapping, map_local_csv
from medflock.training.data import TaskContract, read_dataset, split_indices, transform


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--specification", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--permission-reference", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--mapping", type=Path, help="Reviewed local column/unit mapping JSON")
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError("Use a new node dataset snapshot directory")
    specification = json.loads(args.specification.read_text())
    core = {key: specification[key] for key in ["contract", "preprocessing", "features", "family"]}
    expected = hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()
    if expected != specification["digest"] or specification["family"] != "logistic":
        raise ValueError("This node runtime requires a valid logistic specification")
    contract = TaskContract.model_validate(specification["contract"])
    if specification["features"] != len(contract.features):
        raise ValueError("Specification dimensions do not match the feature contract")
    contents = args.dataset.read_bytes()
    mapping = None
    if args.mapping:
        mapping = LocalMapping.model_validate_json(args.mapping.read_text(encoding="utf-8"))
        contents = map_local_csv(contents, contract, mapping)
    values, labels, groups, profile = read_dataset(contents, contract)
    split = split_indices(labels, groups, args.seed)
    values = transform(values, specification["preprocessing"])
    args.output.mkdir(parents=True, exist_ok=True)
    for name, indices in zip(["training", "validation", "test"], split):
        np.savez(args.output / f"{name}.npz", values=values[indices], labels=labels[indices])
    manifest = dict(
        specification,
        data_sha256=hashlib.sha256((args.output / "training.npz").read_bytes()).hexdigest(),
    )
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (args.output / "local-provenance.json").write_text(
        json.dumps(
            {
                "permission_reference": args.permission_reference,
                "source_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
                "profile": profile,
                "split_counts": [len(indices) for indices in split],
                "preprocessing": "fixed coordinator specification; not refitted locally",
                "mapping": mapping.model_dump() if mapping else None,
            },
            indent=2,
        )
    )
    print("Prepared local training/validation/test partitions; no data was sent to a server")


if __name__ == "__main__":
    main()
