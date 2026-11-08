# MedFlock FL

MedFlock is a cardiology research workbench for comparing local, centralized and federated models. The console supports dataset registration, configurable training, live contribution activity, model activation and experimental predictions. It is a research beta, with clinical review pending and medication recommendations not assessed.

## Start locally

Use Python 3.11, Node 22 and uv 0.11.33. Run these commands from the repository root:

```powershell
python -m pip install uv==0.11.33
uv sync --locked --extra dev
uv run python scripts/configure.py
uv run python scripts/prepare_data.py
npm --prefix frontend ci
npm --prefix frontend run build
uv run medflock serve
```

Open http://127.0.0.1:8088. `configure.py` creates a private, ignored `.env`; existing credentials are preserved. The application loads this file automatically. Local development enables an embedded worker and permits unauthenticated loopback use. The Docker configuration requires authentication and runs the worker separately. Enter your local `MEDFLOCK_API_KEY` in the console's Access page when authentication is enabled. Never commit that value.

## Available workflows

- **Overview:** contribution-driven 3D animation and durable activity feed, backed by GraphQL polling with ordered event cursors.
- **Experiments:** logistic or small MLP models, seeded IID or explicit non-IID partitions, centralized/local/federated comparisons, validation selection, cancellation and result export.
- **Datasets:** CSV registration with a versioned task contract, source and permission declarations, units, feature bounds, binary coding, missing-value handling and optional patient-group splits.
- **Fleet:** inspect simulated contributors and suspend or resume participation between rounds.
- **Models:** inspect checksummed artifacts and activate a candidate for research use with a recorded reason.
- **Model lab:** contract-driven inputs, explicit imputation reporting and research prediction scores.
- **API explorer:** GraphQL queries and mutations; REST/OpenAPI at `/docs`, GraphQL at `/graphql`.

The animated globe and GraphQL workflow were inspired by the supplied `swarm-master` reference. MedFlock uses its own application services and training pipeline.

## Training and future data

A task contract defines the target, feature order, units, outcome horizon and patient grouping. A new compatible dataset creates a new snapshot without changing the application. Training fits imputation and scaling only on the training split; validation Brier selects a candidate, and the held-out split reports AUROC, average precision, Brier and log loss. The pooled baseline is a reference, not a guaranteed upper bound.

Compatible parents can initialize a new run. Parent weights and preprocessing are retained only when task and architecture match; incompatible warm starts are rejected. New features, labels or model families require a new contract or adapter, not silent tensor conversion. Warm-start results may overlap the parent's earlier population and cannot establish independent validation. See [training](docs/TRAINING.md).

Current dashboard experiments are **in-process simulated federation** over permitted research data. The separate Flower SuperLink/SuperNode transport test supports synthetic tensors or checksummed node-local dataset bundles. Neither demonstrates independent hospital training, secure aggregation or clinical validity.

## Deployment and verification

```powershell
docker compose up --build -d
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
npm --prefix frontend test
uv run python scripts/flower_spike.py --dataset data/heart_failure.csv
```

Compose publishes only loopback port 8088, with PostgreSQL and a separate worker. Kubernetes manifests are in `deploy/kubernetes`; GitLab jobs are split under `.gitlab/ci`; GitHub checks are under `.github/workflows`. Cluster secrets and registry access must be configured before deployment. See [deployment and recovery](docs/DEPLOYMENT.md), [API examples](docs/API.md), [verification evidence](docs/evidence/VERIFICATION.md) and [remaining integrations](docs/ROADMAP.md).

## Dataset attribution

Davide Chicco and Giuseppe Jurman, *Heart Failure Clinical Records*, UCI Machine Learning Repository, [DOI: 10.24432/C5Z89R](https://doi.org/10.24432/C5Z89R), CC BY 4.0. The default benchmark derives a 90-day label and excludes early censored records. The software's MIT license does not replace dataset or model licenses. Raw data, credentials, databases and trained weights remain outside Git.

Clinical preparation and remaining external gates: [readiness guide](docs/READINESS.md).

Cardiology teacher drafts, review workflow and GPU handoff: [training package](training/cardiology/README.md).
