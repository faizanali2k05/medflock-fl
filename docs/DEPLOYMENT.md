# Deployment and recovery

## Local configuration

Run `python scripts/configure.py` once. It creates `.env` with generated credentials and leaves an existing file unchanged. Shell environment variables take precedence. Keep `.env` private and back it up through your secret-management process.

| Setting | Purpose |
| --- | --- |
| MEDFLOCK_ENV | development or production |
| MEDFLOCK_DATABASE_URL | SQLAlchemy SQLite or PostgreSQL URL |
| MEDFLOCK_DATASET | optional default CSV path |
| MEDFLOCK_ARTIFACTS | writable snapshot and artifact directory |
| MEDFLOCK_EMBEDDED_WORKER | true only for local development |
| MEDFLOCK_AUTH_REQUIRED | production requires true |
| MEDFLOCK_API_KEY | operator bearer key, at least 32 characters in production |
| MEDFLOCK_ALLOWED_HOSTS | comma-separated explicit HTTP hostnames |
| MEDFLOCK_OIDC_ISSUER | optional Keycloak issuer URL |
| MEDFLOCK_OIDC_AUDIENCE | expected audience, default medflock |
| POSTGRES_PASSWORD | local Compose database password |

OIDC requires RS256 tokens with `exp`, `sub`, the configured issuer/audience and a `researcher` or `operator` realm role. An operator may register data, manage nodes and activate research candidates. The fallback API key is a shared operator identity, not per-person audit attribution. Use a TLS reverse proxy for any non-loopback access.

## Docker Compose

`docker compose up --build -d` runs API, worker and PostgreSQL. The image builds the React console, installs locked Python dependencies and runs as UID 10001. Application containers use a read-only filesystem, dropped capabilities and writable volumes only for artifacts/runtime. API health checks query database readiness. The worker exits on fatal leadership failure and is restarted by Compose. Training failures are stored on the individual run.

Stop an existing process on port 8088 or set `MEDFLOCK_PORT` to another port. `docker compose down` retains volumes. Do not use `down -v` unless you intend to erase the database and artifacts. The local PostgreSQL account owns the database and is a bootstrap superuser; use a restricted managed-database role for a shared deployment.

## Kubernetes

The manifests intentionally run one API container and one worker container in a single pod, with a shared ReadWriteOnce volume and a Recreate rollout. They are a deployable single-instance beta topology, not a highly available service. PostgreSQL is external. Do not scale this deployment above one replica.

1. Create the namespace with `kubectl apply -f deploy/kubernetes/namespace.yaml`.
2. Create `medflock-config` in that namespace from a private environment file. Include a PostgreSQL URL, `MEDFLOCK_API_KEY` or OIDC settings, `MEDFLOCK_ALLOWED_HOSTS=localhost,<your-hostname>`, and `MEDFLOCK_ARTIFACTS=/app/artifacts`. Do not commit the file. Import datasets through the API; a default file is optional.
3. Create the `registry-credentials` image-pull secret for the private GitLab registry.
4. Set `newTag` in `kustomization.yaml` to the tested commit SHA, then run `kubectl apply -k deploy/kubernetes`.
5. Check `kubectl -n medflock rollout status deployment/medflock`. For local access, use `kubectl -n medflock port-forward service/medflock 8088:8088`.

For external access supply your own ingress/TLS and network policy matching your ingress controller, database and OIDC endpoints. Restrict database access to the application namespace. The supplied manifests do not assume a cloud storage class or publish an unconfigured ingress.

## CI and release

GitHub checks Python lint/tests, frontend tests/build, wheel packaging and Docker build. GitLab does the same verification, publishes a commit-tagged image with rootless BuildKit on the default branch, and exposes a manual staging deployment only when `KUBE_CONTEXT` is configured. Protect the staging environment and configure GitLab Agent access before enabling that job. Deployment updates both containers to the same immutable commit tag and waits for rollout.

## Recovery and data integrity

Queued jobs survive restarts. A worker holds a PostgreSQL advisory lock or SQLite file lock. Interrupted running jobs become aborted; submit a new run rather than pretending a partial round was resumed. Cancellation prevents late completion from publishing a candidate. This is single-worker coordination, not a partition-tolerant distributed scheduler.

Schema versions 1 and 2 are additive table creation, serialized with a PostgreSQL migration lock. Existing data is retained. Future column/data transformations require explicit migrations; `create_all` does not perform them. Back up PostgreSQL and the artifact volume together while writes are stopped, and test restoring both to an isolated environment. A database restore without matching artifacts causes checksum/file failures. Rollback requires a compatible database schema and the previous image digest; do not erase new data to make an old binary start.

Liveness is `/health/live`; readiness is `/health/ready`. Request logs contain request ID, route, status and duration, not patient features or credentials. The application does not store prediction payloads. Place rate limiting and request-size enforcement at the external proxy, especially for chunked uploads and GraphQL alias-heavy requests.
