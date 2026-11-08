"""Reproduce the predeclared three-seed comparison without tuning on held-out metrics."""

import json
from pathlib import Path

from medflock.training.data import default_contract
from medflock.training.engine import TrainingConfig, train_run


def main():
    rows = []
    for family in ["logistic", "mlp"]:
        for seed in [17, 42, 73]:
            result, _ = train_run(
                TrainingConfig(family=family, seed=seed, rounds=60),
                Path("data/heart_failure.csv").read_bytes(),
                default_contract(),
                Path("artifacts/benchmark-v2"),
                f"{family}-{seed}",
                lambda *_: None,
                lambda: False,
            )
            rows.append(
                {
                    key: result[key]
                    for key in [
                        "config",
                        "cohort",
                        "centralized",
                        "local_only",
                        "fedavg",
                        "selected_round",
                        "split_hash",
                        "limitations",
                    ]
                }
            )
            print(family, seed, result["fedavg"]["auroc"])
    Path("docs/evidence/benchmark-v2.json").write_text(
        json.dumps({"pipeline": 2, "federation": "simulated_in_process", "runs": rows}, indent=2)
    )


if __name__ == "__main__":
    main()
