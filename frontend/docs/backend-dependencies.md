# UI contract inventory

The frontend uses existing endpoints only. Hospital approval, identity binding, live connectivity and successful training are different states.

| Journey | Existing contract | Missing behavior / truthful UI state |
| --- | --- | --- |
| Sign in and account | `/api/auth/me`, `login`, `logout`, `password`; session cookies and CSRF | No password recovery or application notification service. Contact administrator. |
| Case library | GET/POST `/api/cases`; GET/PUT `/{id}`; PATCH `/{id}/status` | No shared cases, medical record integration or approved clinical notes. Show owner-scoped synthetic drafts only. |
| Discuss/review | `/api/llm/status`, `/api/llm/generate-stream`; revision-bound saved reviews | No validated treatment or evidence retrieval contract. No invented citations or clinical confidence. |
| Cancel inference | No acknowledged cancellation contract | No misleading stop-training control. Disconnecting the browser does not prove server generation stopped; an authorized request ID, cancellation acknowledgement and final persistence status are needed. |
| Application | POST `/api/hospital-applications` | No public status lookup; provide copyable reference and manual-contact guidance. |
| Institution setup | GET `/api/client/node` | `transport_binding` records identity only; no live connection, dataset readiness, round progress or contribution-history API. Those steps remain blocked/unknown. |
| Manual admission | GET admin applications, POST application decision | External verification is manual; UI never implies it performed institutional verification. |
| Runner identity | POST admin node transport-binding | No key registration, runner installer, diagnostics or key rotation. No private-key field. |
| Research | Existing GraphQL dashboard, activity, experiments, models and prediction; REST dataset import | Tabular simulations, not MedGemma training. Backend still authorizes all operations. |
| Model evolution | None for comparable medical-model evaluation artifacts | Show “No comparable evaluations available.” Needs versioned base/student IDs, corpus/evaluation hashes, task metrics, safety slices and review status before charts can be shown. |
| Patient services | None | No patient assistant launched. |

Initial audit: Portal and App had separate shells; tab changes were not bookmarkable; researchers could not reach the research navigation; case selection was a dense dropdown; review replaced the user's prompt; hospital status mixed identity and connectivity; no adequate UI journey tests existed. Preserve server revisions, ownership, synthetic attestation and error recovery throughout the redesign.

Implemented workspace additions: `/api/workspace/profile`, `/api/workspace/notifications` and `/api/workspace/notifications/read` provide session-owned preferences and filtered recent activity. Clean workspace deep links are served by explicit SPA fallbacks. Notification delivery is polling; no Kafka broker or push notification service is implied.
