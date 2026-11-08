# Working on MedFlock

Use focused branches and commits that describe a concrete behavior change. Explain non-obvious reasoning in short comments; avoid narrating the code.

Before pushing, run Python lint, formatting and tests, then frontend tests and the production build. Run the Flower transport check when changing Message API integration. Update task-contract versions when data meaning changes. Never silently reinterpret existing weights.

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
npm --prefix frontend test
npm --prefix frontend run build
```

Push matching branches to GitHub `origin` and GitLab `gitlab`. Check CI before updating the default branch. Use pull/merge requests for reviewed changes; do not force-push shared history. Do not commit data, weights, credentials, `.env`, databases or runtime logs.

The React console lives in `frontend/src`; its compiled output is packaged with Python and built by Docker/CI. GraphQL and REST share application services. Training must remain independent of HTTP transports. Production uses an external worker; the embedded worker is a local-development convenience.
