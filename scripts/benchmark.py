"""Save aggregate evidence only; patient rows and weights stay in ignored local artifacts."""

import json
from pathlib import Path

from medflock.experiment import ExperimentConfig, run_experiment

scenarios = [
    ("iid-3", dict(clients=3)),
    ("label-5", dict(clients=5, partition="label_skew")),
    ("attack-5", dict(clients=5, partition="label_skew", attack="sign_flip")),
    ("clipped-5", dict(clients=5, partition="label_skew", attack="sign_flip", defense="clip")),
    ("age-10", dict(clients=10, partition="feature_skew")),
]
results = []
for name, options in scenarios:
    for seed in [17, 42, 81]:
        result, _ = run_experiment(
            ExperimentConfig(seed=seed, **options),
            Path("data/heart_failure.csv"),
            Path("artifacts"),
            f"benchmark-{name}-{seed}",
        )
        result.pop("history")
        results.append(result)
        print(name, seed, round(result["fedavg"]["auroc"], 4))
destination = Path("docs/evidence/benchmark.json")
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(results, indent=2), encoding="utf-8")
