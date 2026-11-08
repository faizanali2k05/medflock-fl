"""Import a reviewed local image/waveform manifest into the existing training registry."""

import argparse
import json
from pathlib import Path

from medflock.config import Settings
from medflock.modalities import adapt
from medflock.service import Workbench
from medflock.store import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    contents, contract, provenance = adapt(
        args.manifest.read_text(), args.root, json.loads(args.spec.read_text())
    )
    settings = Settings.load()
    store = Store(settings.database_url)
    try:
        snapshot = Workbench(store, settings.dataset, settings.artifacts).register_dataset(
            args.name, contents, contract.model_dump(), provenance
        )
        print(
            json.dumps(
                {
                    "id": snapshot["id"],
                    "profile": snapshot["profile"],
                    "contract": snapshot["contract"],
                },
                indent=2,
            )
        )
    finally:
        store.engine.dispose()


if __name__ == "__main__":
    main()
