# API workflows

REST documentation is generated at `/docs`. GraphQL accepts POST JSON at `/graphql`; add `Authorization: Bearer <token>` when authentication is required. The console stores the entered token only in session storage. Avoid putting credentials into query text or URLs.

```graphql
query Dashboard {
  datasets { id name profile contract }
  runs(limit: 20) { id status config error }
  nodes { id status lastSeen details }
  models { id status manifest }
  activityCursor
}
```

```graphql
mutation Start($config: JSON!, $key: String!) {
  startRun(config: $config, requestKey: $key) { id status }
}
```

Example variables: `{"config":{"dataset_id":"default","family":"logistic","clients":3,"rounds":60,"partition":"iid"},"key":"unique-request-0001"}`. Retry with the same key and same configuration to receive the original run. Reusing a key for a different configuration fails.

```graphql
query Activity($after: Int!) {
  activity(after: $after, limit: 200) { sequence kind createdAt details }
}
mutation Cancel($id: String!) { cancelRun(id: $id) }
mutation Suspend($id: String!) { setNodeStatus(id: $id, status: "suspended") { id status } }
mutation Activate($id: String!, $reason: String!) {
  activateModel(id: $id, reason: $reason) { id status }
}
mutation Predict($id: String!, $features: JSON!) {
  predict(modelId: $id, features: $features)
}
```

On first connection, use `activityCursor` as the starting position. Poll `activity` and advance only to the final returned sequence. Continue paging if 200 records are returned. Sequence cursors avoid dropping events between polls; event IDs support deduplication. Events contain training metadata, not uploaded patient rows.

CSV upload uses multipart `POST /api/datasets` with `file`, `name`, `contract` (JSON string), `source` and `permission`. Query `defaultContract` for a starting contract. Change the contract ID/version when task meaning changes. `GET /api/runs/{id}/export` exports completed metrics. Prediction requires precisely the model's declared feature keys, with null values permitted for explicit imputation.

See `src/medflock/graphql.py` for the schema and `src/medflock/service.py` for shared operations. Authentication and authorization apply to both transports. GraphQL errors are returned in the standard `errors` field; callers must check it even when HTTP status is 200.


### Account photo

`GET /api/workspace/profile` includes nullable `photo_version` alongside preferences. This read-only version must be omitted from `PUT /api/workspace/profile`.

- `POST /api/workspace/profile/photo`: multipart `file`; JPEG, PNG or WebP; returns `photo_version`. Invalid images return 422 and files over 2 MiB return 413. Dimensions are capped at 16 megapixels before decoding.
- `GET /api/workspace/profile/photo`: owner-only normalized JPEG; 404 if absent, 401 without a session. Responses are non-cacheable and use `nosniff`.
- `DELETE /api/workspace/profile/photo`: removes the current account's photo; returns a null version.

Mutations require the signed-in account's CSRF token. These endpoints do not accept another user's ID or a filesystem path.
