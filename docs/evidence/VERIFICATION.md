# Version 0.2 verification

Verified locally on 16 October 2026 with Python 3.11 and the locked environment.

- The production frontend builds; activity ordering/deduplication tests pass. The frontend dependency audit reports zero vulnerabilities after upgrading Vitest to 5.0.5.
- 25 backend tests pass. They cover numerical MLP/logistic gradients, patient-disjoint splitting, training-only preprocessing, artifact corruption, incompatible warm starts, cancellation races, authenticated GraphQL, idempotent submissions and a second binary task using the same API/worker pipeline.
- Firefox exercised experiment submission through GraphQL, completed results and synthetic-case inference. The globe uses projected geometry and queued contribution pulses without a WebGL dependency.
- The Docker image builds. An isolated Compose project on port 8090 starts PostgreSQL, API and worker; readiness returns 200, anonymous GraphQL returns 401, and an authenticated job completes through the separate worker.
- The node-local Flower check completed three rounds, each with three results and zero failures; the final tensor norm was 0.04542555. BLAS threads are capped for the multi-process runner.
- `kubectl kustomize deploy/kubernetes` renders successfully. No remote cluster deployment or hospital network is claimed.

## Measured version-2 benchmark

`benchmark-v2.json` records logistic and MLP results at fixed seeds 17, 42 and 73, with 60 maximum rounds and validation-based selection. Reproduce with `python scripts/benchmark_v2.py` after preparing the public dataset.

| Family | Seed | Centralized test AUROC | Federated test AUROC |
| --- | --- | --- | --- |
| Logistic | 17 | 0.769 | 0.759 |
| Logistic | 42 | 0.707 | 0.697 |
| Logistic | 73 | 0.654 | 0.648 |
| MLP | 17 | 0.769 | 0.761 |
| MLP | 42 | 0.711 | 0.709 |
| MLP | 73 | 0.617 | 0.617 |

Each run uses the same split for its paired baselines. These are small public-data experiments, not confidence intervals, clinical validation or proof that an MLP improves performance. The old benchmark below uses a different pipeline/split and is retained as historical evidence, not a paired comparison.

---

# Verification record

Date: 15 October 2026. Local Windows Python 3.11.9, Flower 1.39.0.

## Executed

- Automated tests: 16 passed. Coverage includes censoring boundaries and excluded
  predictors, invalid datasets, deterministic/disjoint partitioning, weighted Flower
  aggregation, invalid updates, minimum defense-client counts, model corruption and
  contract rejection, stale-round/base-model/count rejection, idempotency conflicts,
  restart recovery and API execution.
- Ruff lint and formatting checks passed.
- Flower Deployment Engine: three separate SuperNode processes, three training rounds,
  three responses and zero failures each round. Final synthetic weight norm:
  `0.07161156`. Successful run ID: `1276433710718579854`.
- Fifteen public-data experiments: five scenarios × seeds 17, 42 and 81. Aggregate
  results are in [benchmark.json](benchmark.json). Each has 192 training and 64
  holdout records, and the same split across approaches within a seed.
- Browser: launched a run through the Firefox form, observed completion and real
  metrics, checked the displayed result and page layout without horizontal overflow.
- Python source distribution and wheel built, including the contract and web assets.
- Linux Docker image built and completed an API experiment against PostgreSQL 17.6
  through Compose. Dataset loading, run persistence, candidate registration and web
  resource serving passed. The temporary test stack and volumes were removed.
- Official UCI download matched the pinned CSV SHA-256 fingerprint.

Upstream deprecation warnings from Typer/Click and Starlette's httpx test adapter
remain visible. They do not fail the current suite. A dependency upgrade must rerun
the suite and the Flower spike, not just suppress those warnings.

## What these results establish

The numerical pipeline, metadata persistence and local transport integration run.
The current model is not clinically useful evidence: standard FedAvg AUROC is about
0.50–0.55 on the three IID development splits. The sign-flip test saturates predictions
and gives AUROC 0.5; clipping does not consistently restore the clean result.
No hyperparameter selection was conducted to improve these displayed holdout scores.

## Not established

Independent hospital federation, remote TLS/node-auth configuration, secure aggregation,
differential privacy, reliable poisoning detection, calibrated patient risk, external
clinical validity, approved treatment rules, retrieval quality, LLM distillation or
clinical reviewer approval. There is no measured clinical assistant latency target.

The Flower test used public APIs at the pinned release and plaintext **loopback**
connections. It must not be copied unchanged into a remote hospital deployment.
