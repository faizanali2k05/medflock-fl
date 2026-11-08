"""Local entry points share the same experiment contract as the workbench."""

import argparse
import json
import os
import uuid
from pathlib import Path

from medflock.training.data import default_contract
from medflock.training.engine import TrainingConfig, train_run


def main():
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser(prog="medflock")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("experiment")
    run.add_argument("--dataset", type=Path, default=Path("data/heart_failure.csv"))
    run.add_argument("--output", type=Path, default=Path("artifacts"))
    run.add_argument("--clients", type=int, default=3)
    run.add_argument("--rounds", type=int, default=60)
    run.add_argument("--family", choices=["logistic", "mlp"], default="logistic")
    run.add_argument("--partition", choices=["iid", "label_skew", "feature_skew"], default="iid")
    run.add_argument("--attack", choices=["none", "sign_flip"], default="none")
    run.add_argument("--defense", choices=["none", "clip"], default="none")
    commands.add_parser("serve")
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        uvicorn.run(
            "medflock.api:app",
            host="127.0.0.1",
            port=int(os.getenv("MEDFLOCK_PORT", "8088")),
            workers=1,
        )
        return
    config = TrainingConfig(
        **{
            k: getattr(args, k)
            for k in ["clients", "rounds", "partition", "attack", "defense", "family"]
        }
    )
    result, _ = train_run(
        config,
        args.dataset.read_bytes(),
        default_contract(),
        args.output,
        uuid.uuid4().hex,
        lambda *_: None,
        lambda: False,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
