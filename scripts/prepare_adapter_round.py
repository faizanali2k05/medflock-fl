"""Export only adapter tensors and compatibility metadata for a reviewed local runner."""

import argparse
import json
from pathlib import Path

import numpy as np

from medflock.adapter_federation import arrays_from_adapter, load_runner

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-config", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError("Use a fresh coordinator bundle directory")
    _, model, _, digest, layout = load_runner(args.local_config)
    args.output.mkdir(parents=True, exist_ok=True)
    np.savez(
        args.output / "initial-adapter.npz",
        **{f"tensor-{i:04d}": value for i, value in enumerate(arrays_from_adapter(model))},
    )
    (args.output / "server.json").write_text(
        json.dumps({"family": "causal-lora", "digest": digest, "layout": layout}, indent=2),
        encoding="utf-8",
    )
    print("Exported adapter weights and contract only; local corpus is not in the bundle.")
