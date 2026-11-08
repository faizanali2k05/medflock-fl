# Case workspace

## Internal-testing update — 23 October 2026

The workspace streams draft text over an authenticated, CSRF-protected endpoint.
Provider reasoning channels are not displayed. A successful final answer is saved
only after completion and revision checks; partial text is labelled as an incomplete
draft if generation fails. The regular JSON endpoint remains available to API clients.
Hourly inference quotas and the four-exchange cap are removed. One inference at a
time still protects the shared runtime. Actual context capacity is checked using
the runtime tokenizer; saved history is not silently shortened.

The active instructions are visible under runtime details. Organize mode uses a
bounded output grammar with presentation, history, medications/allergies, vital
signs, examination, ECG, laboratory and timing sections. This prevents runaway
lists but does not ensure clinical correctness. A limited source-consistency check
flags suspicious unit changes without rewriting them. Administrators can configure
32–4,096 output tokens and a 30–900 second response deadline. The proxy deadline is
930 seconds. Truncated drafts expose a continuation action rather than telling the
user to abandon the case.

The model now uses four threads and an 8,192-token context. Its CPU quota is removed,
with lower CPU scheduling weight on contention; its memory ceiling is 8 GiB.
API, worker, database and proxy caps remain unchanged. Removing all service limits
was rejected by automatic approval review on this shared host. The previous model
configuration is retained on the VPS for rollback.

The exact MF-CARD-001 development case is stored in tests/fixtures/cardiology. It
has been used for prompt tuning and is not an independent held-out evaluation.
The grouped-format runtime probe completed in 116.48 seconds with 499 output tokens
and a normal stop. Its required medication, ECG and troponin anchors were retained.
Some clarifying questions repeated supplied facts: clinical usefulness is not
established by transport success or anchor checks. Use scripts/check_case_runtime.py
to measure streamed first-draft latency and repeat these limited regression checks.

The primary product workflow is case discussion, not dataset evaluation. After
sign-in, a care professional opens the case workspace, describes a synthetic
case in ordinary language, and asks MedGemma to organize it. The assistant drafts
stated facts, missing information and clarifying questions. The user edits that
understanding, explicitly selects it for follow-up, and sends the next question.
A reviewed draft can be exported as text. Exported drafts retain the preview
label; user review does not constitute clinical validation of the model.

Case chat uses the private MedGemma runtime and supports bounded follow-up
context. There is no exchange-count cap or hourly inference quota. Requests are
checked against the running model's actual token capacity, including the chat
template and reserved output. Nothing is silently dropped. When history no longer
fits, the user can edit and save a reviewed summary and explicitly select it as
context for a request. This replaces earlier discussion for that request only;
the saved history remains intact. Drafts and summaries accept 20,000 characters,
subject to the model's token capacity when sent. Saved synthetic cases persist in the project database and can be reopened after
sign-out. Save draft persists edits; sending saves the prompt before inference
and appends a successful exchange transactionally. Unsaved edits remain in browser
memory, with a navigation warning. Only synthetic cases are enabled while clinical
evaluation remains incomplete; this is not an approved patient record system.

Care-professional accounts use the `clinician` role, which permits case chat
and read access but not training, user administration or infrastructure changes.
Administrators create these accounts under Administration → Users. Model
controls are under Administration → Assistant. Model operations, datasets and
simulations are administrative tools rather than the clinical landing page.

Model Lab remains a separate tabular prediction diagnostic. Its input contract
is fixed by the trained model; arbitrary narrative fields cannot be added to it
at inference time. Case extraction currently produces an editable narrative,
not a validated automatic mapping into that model. No predicted risk or
prescription is silently inferred from an incomplete narrative.

Saved cases have owner-only access, including for administrators. Review versions
retain the exact edited summary and timestamp. Revision checks reject stale edits
and late inference results after another tab changes a case. Archive makes a case
read-only and restore enables editing again; archive does not erase records. The
preview allows 200 cases per account and 100 review versions per case. Titles,
case text and summaries are excluded from shared audit events. Database operators
can still access database contents; encryption at rest is not claimed.

Further product work includes clinician assignment and authorized sharing,
source-grounded treatment discussion, validated extraction with
unit and contradiction checks, and a controlled route from approved datasets
and reviewed corpora to evaluated model releases. Uploading more data alone
does not automatically improve or release the model.

## Verification — 22 October 2026

Application release `fbdc66e09b80f8eacc755c222653a719c1803ec5` is deployed with
schema version 3. The migration adds case and review tables; existing tables are
not replaced. A database backup and prior deployment environment were retained
under the root-only deployment backup directory before updating the API and worker.

Backend and frontend CI checks passed. Tests cover owner isolation (including
administrator denial for another user's case), CSRF, stale edits, archived writes,
saved conversation integrity, timeout preservation and a conflicting edit during
inference. Browser checks covered saving, archive/restore, review recording, page
reload and reopening the saved draft and review history.

Public HTTPS verification created one clearly labelled synthetic deployment-check
case, saved its draft, recorded a real MedGemma exchange, saved a review, signed out
and reopened the case, then archived it. Anonymous case access returned 401; stale
and archived edits returned 409. The archived test case remains available to its
owning administrator for inspection. No real patient data was used.

The model response took 102.94 seconds and was not truncated. Runtime timing logs
reported approximately 97.6 seconds of prompt evaluation and 1.6 seconds of token
generation. This does not establish a reliable latency target or prove the cause
of the slow prompt evaluation. Memory-loading settings were left unchanged rather
than risk exceeding the model's allocation on the shared host.

All 42 unrelated container IDs from the pre-update snapshot remained running.
MedFlock's combined configured limits remained two CPU cores and 6016 MiB RAM;
the model runtime and database were not restarted. Temporary registry credentials
were removed after the update. This verifies container continuity, not the internal
functionality of other hosted applications.


## Deployed streaming verification — 23 October 2026

Application image `68cb73fdea29a571fa71c1c03f37f20bce770ff6` is deployed.
The public HTTPS streaming regression returned first draft text in 2.875 seconds
and completed in 76.24 seconds with 460 output tokens, a normal stop and all
required fixture anchors present. This was a warm-runtime measurement. A separate
Firefox run of the same case completed in 99.7 seconds with 470 tokens. Live draft
text was observed while generation was running; the editable summary was populated,
saved, reloaded and archived under a synthetic browser-regression title.

CI collected 64 backend tests: 57 passed, seven optional tests skipped, no failures.
Both frontend tests, the frontend build and container packaging passed. Deployed
client-policy checks covered active, paused, restricted and timed-suspended states,
client denial of administrator routes, and HTTP 401 after account/session revocation.
The temporary test node was revoked. All 42 unrelated running container IDs were
unchanged. Final memory-pressure averages were zero over 10 and 60 seconds;
7.3 GiB of host memory was available. No MedFlock OOM kill was observed.

No MedGemma weight training occurred in this release. Clinical review, improved
question relevance and authenticated hospital training transport remain unfinished.


## Compact case controls and profile photos

The case title is the single collapsed control heading above the conversation. It contains the runtime status, exact request instructions, context selection, case facts, save/reload/archive controls, and research limitations. The typing bar remains at the bottom of the conversation; these controls no longer occupy separate rows above it. Existing repetitive model drafts are preserved in the transcript but collapsed, and continuation is unavailable for a detected repetitive last answer. This is presentation and recovery behavior, not evidence of improved model weights or clinical validation.

Profile & preferences accepts a JPEG, PNG, or WebP photo up to 2 MiB and 16 megapixels. The server decodes the image, applies orientation, crops to 256 × 256, and writes a new JPEG without source metadata. The small normalized photo is stored in the account's existing profile snapshot; no public upload directory or arbitrary image URL is used. Its authenticated endpoint always returns the current session owner's image. Upload and removal require the existing session and CSRF checks, including hospital/client roles. Profile photos appear in the shared top bar across workspaces. Initials or the selected symbol remain the fallback.

The light and dark themes use graphite surfaces and neutral typography throughout the workspace and learning network. Accepted contribution events launch a labelled projectile toward the sphere, with a short trail and arrival ring. Each SVG animation starts when its event mounts rather than at the sphere's original start time. Only new accepted events animate; a bounded queue shows up to four arrivals per batch. Reduced-motion mode reports the latest source without animation. These labels describe transport events, not clinical validation or real-hospital participation.
