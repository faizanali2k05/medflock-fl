"""Generate one private hospital node identity without displaying its key."""

import argparse
from pathlib import Path

from medflock.pki import node_identity

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _, public = node_identity(args.output)
    print(f"Generated identity. Send only {public} to the coordinator administrator.")
