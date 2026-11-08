"""Run a permissioned local sequence-distillation job from its immutable configuration."""

import argparse
import json
from pathlib import Path

from medflock.distillation import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(json.loads(arguments.config.read_text())), indent=2))
