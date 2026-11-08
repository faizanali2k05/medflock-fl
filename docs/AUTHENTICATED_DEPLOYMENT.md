# Authenticated VPS research deployment

The deployed application uses the `medflock` Compose project under `/opt/medflock`. Its dedicated HTTPS proxy publishes port 18443; API diagnostics bind only loopback 18088. PostgreSQL and the inference runtime have no host port. The host's existing Nginx, projects, databases and credentials are not reused.

## Accounts and permissions

- Admin: create/disable accounts, revoke sessions, manage node registry, upload corpora/datasets, set inference limits, inspect application audit, run research workflows.
- Researcher: read research records, submit bounded tabular experiments and synthetic model prompts. No account or corpus administration.
- Viewer: read research records and model status; cannot start experiments or generate LLM output.
- Client: only its assigned node and registry heartbeat. This login does not replace Flower transport certificates or enroll a running hospital worker.

Passwords use salted scrypt. Sessions use random 256-bit tokens, stored as hashes, with HttpOnly/Secure/SameSite=Strict cookies, 30-minute idle expiry and 8-hour absolute expiry. Password changes and administrator revocation invalidate sessions. Mutations require a session-bound CSRF token and reject cross-origin writes. Login attempts, API requests and generation have independent limits. The proxy caps request rates, connections, body size and timeouts. Session-authenticated prompts are limited to one concurrent inference, 30 total requests/hour and the configured per-account quota. Request/audit logs exclude passwords, prompt contents and query strings. Role checks occur in the backend, not only the UI.

The initial administrator is created from standard input using `python -m medflock.bootstrap`. No default password exists in source or the image. Change the provided initial password from Account after first login. The account name is not a secret. Credential values are not documented here.

## TLS and secrets

Without a domain, the initial IP certificate is self-signed. Verify its fingerprint through the SSH channel before trusting it in the browser. Encryption alone does not establish server identity until that trust step. Do not disable certificate checking globally. A publicly trusted certificate and domain can replace it later without changing application accounts.

The server `.env` is required for Compose interpolation and lives only in the root-owned deployment directory with mode 0600. It is not mounted as web content or included in images/Git. The TLS private key is mode 0600 and only mounted into the dedicated proxy. Paths beginning with a dot are denied by the proxy; FastAPI serves only the explicit frontend assets, not the working directory. No Docker socket, host filesystem root or unrestricted command execution is exposed in the dashboard.

## Resource budget

Aggregate configured maximum: 2 CPU cores and 6016 MiB RAM (5.875 GiB), including inference. API 0.35 cores/512 MiB; worker 0.35/768 MiB; database 0.2/512 MiB; proxy 0.1/128 MiB; model 1/4096 MiB. Memory+swap limits equal memory limits. Thread pools, process counts and log sizes are bounded. These limits constrain MedFlock but do not guarantee zero I/O or network impact on neighbors; monitor the host and reduce/stop only this project if needed. Model download is throttled and performed at low CPU/I/O priority.

## Model and corpus boundary

The research inference candidate is an Unsloth Q4_K_M GGUF conversion of MedGemma 1.5 4B, repository revision `3855f948626b7ae42bccd082757f15078c53e758`, file SHA-256 `b31becdf4f39561800505514cce67681604fe449d04dd35c8c92fd7848c6d7bd`. Official gated model access was checked before acquisition. This third-party quantized conversion is not the official full-precision training checkpoint and requires its own output evaluation. Text-only inference is enabled; ECG interpretation is not claimed. Numerical prescription safety rules and clinical validation remain incomplete.

Corpus import stores an immutable content-hashed version and marks it unreviewed even if the uploaded file asserts approval. It does not start training. The bundled 300 drafts cover 60 families; they are not independently validated patient cases. Full-weight distillation and remote Flower LLM orchestration remain separate GPU/integration work.

## Updates and recovery

Publish commit-tagged images through the existing CI; build on CI, not on the shared VPS. Before update, validate Compose, record the current image digest and take a paired database/artifact backup. Use a deployment lock and apply `docker compose -p medflock ... up -d` only in this directory. Never use global prune, restart Docker, modify unrelated stacks or use `down -v`. Verify readiness, login, role restrictions, corpus metadata and inference after an update. If verification fails, stop only the failed MedFlock service and restore a compatible prior image; schema rollback requires a tested backup restore.

This release adds tables without altering existing ones. A complete backup restore drill and autonomous CI-to-host deployment are not yet claimed. Deployments remain controlled, with a clear image publication path. Protect downloaded backups off-host and verify hashes before destroying any rental instance.
