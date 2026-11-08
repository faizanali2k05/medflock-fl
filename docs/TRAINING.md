# Training and dataset contracts

The version-2 pipeline lives in `src/medflock/training`. `data.py` owns contracts and preprocessing, `models.py` owns numerical model operations, and `engine.py` owns experiment execution and artifact compatibility. Transport and persistence are outside those modules.

## Import and splitting

Register a CSV with an explicit task contract, source and permission declaration. Imports are capped at 20 MiB and 200,000 rows. Binary targets need at least ten examples per class. Exact duplicate rows are removed. Time-horizon tasks exclude patients censored before the horizon rather than assigning them a negative outcome. Missing feature values are imputed using training medians; missing targets are rejected. Features must declare units. Patient identifiers can be used as a grouping column, but cannot also be features.

Each seeded split contains approximately 60% training, 20% validation and 20% test data. Grouped splitting keeps a patient's records together and rejects splits missing a class. Imputation, means and scales are fitted only on training records. This research benchmark pools training statistics; that is not a privacy-preserving preprocessing protocol for hospitals.

## Optimization and comparisons

Logistic regression and a tanh MLP share a flat tensor interface. Both use regularized gradient descent. FedAvg weights contributions by sample count. Centralized and local-only baselines use the same split, initialization and maximum optimization budget, selecting checkpoints using validation Brier. Federated training uses validation Brier with early stopping. Test metrics never select checkpoints.

IID, label-skew and first-feature-skew partitions are explicitly simulated. Median and trimmed-mean aggregation, sign-flip attacks and clipping require at least five configured clients; fewer active contributors abort those rounds. These are stress tests, not Byzantine-tolerance guarantees. Clipping is not differential privacy. The server can inspect updates; secure aggregation is not active.

## Adding data and continuing models

A snapshot ID combines the CSV digest with the task-contract digest. Artifacts record the source digest, split digest, parent model, model dimensions, preprocessing and selected round. Contributions validate task/preprocessing/architecture compatibility, base-model hash, round, shape, sample count and finite tensor values.

A compatible warm start loads a checksummed parent and retains its preprocessing. Keep an external cohort that has never been used by any ancestor when evaluating continued models. Merely changing a seed does not create an independent evaluation population. Incompatible tasks must start a new model; existing releases remain identifiable by their manifests.

Images, ECG signals, multiclass outcomes and language models need dedicated task/model adapters and evaluation. They are not accepted as arbitrary CSV substitutes. A future LLM distillation pipeline also needs licensed teacher outputs, a selected student, hardware sizing and a separate clinical review set. No distilled or clinically reviewed model is claimed by this release.

## Research interpretation

The UCI cohort is small and retrospective. A single split is not sufficient evidence for clinical adoption. Repeat predeclared seeds, inspect subgroup counts and calibration, and reserve external validation before evaluating deployment readiness. Do not tune against published test results. Observed prescriptions are not safe treatment labels; this release returns `medication_status: not_assessed`.

## Flower node-local execution

`python scripts/flower_spike.py --dataset data/heart_failure.csv` prepares explicit label-skew partitions, then launches three real SuperNodes and a SuperLink on loopback. Each ClientApp loads only its assigned bundle, verifies the task/preprocessing digest and data checksum, trains locally and replies with weights plus a sample count. The ServerApp reads the shared specification rather than patient rows and saves the aggregated weights.

Bundles are under ignored `runtime/node-bundles`; raw records are not put into the Flower application bundle. Preparation itself uses pooled public training statistics and data on this machine. This is a multi-process transport integration test, not a hospital privacy guarantee. It uses plaintext loopback only, is separate from dashboard orchestration, and must gain TLS/node enrollment before use across machines. Without `--dataset`, the original synthetic transport test remains available.
