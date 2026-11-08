# Workspace redesign

Implemented against `Frontend_Only_Agent_Prompt.md`, 24 October 2026. MedFlock remains the product name. The linked tldraw board could not be retrieved in this environment; the written brief and actual repository contracts govern this implementation. No backend route, authentication rule, model instruction or deployment setting was changed for the frontend redesign. Hybrid-training changes were separately authorized.

## Roles and routes

| Role | Landing | Available work |
| --- | --- | --- |
| Clinician | `#/cases` | Owner-scoped synthetic cases, account, help |
| Hospital | `#/institution` | Setup/readiness guidance, own cases, account, help |
| Client | `#/institution` | Assigned node setup, account, help; no clinician inference |
| Administrator | `#/admin/hospitals` | Manual admission decisions, users, clients, corpora, datasets, inference controls, audit; own cases and research |
| Researcher | `#/research/overview` | Experiments, datasets, fleet, models, tabular model lab, GraphQL explorer, own cases, model-evolution placeholder |
| Viewer | `#/research/overview` | Research inspection; mutation controls blocked; server permissions remain authoritative |

Hash routes preserve refresh/deep links without requiring server rewrites. Research subroutes are `overview`, `experiments`, `datasets`, `fleet`, `models`, `model-lab`, `api-explorer`. Admin subroutes are `hospitals`, `users`, `clients`, `corpora`, `datasets`, `assistant`, `audit`. Common routes are `#/account`, `#/help`; applicants use `#/apply`. Unknown or unauthorized routes show a recovery link, never another role's tools. Backend authorization is still required for every request, including raw GraphQL operations.

## Clinician journey

My cases provides active/archived filters, title search, revision/date context and a clear new-case action. Intake uses natural text with explicit synthetic attestation. The user can organize facts or ask directly. Fact review separates provided messages, extracted text, user edits and saved review versions. Saving reviewed facts never replaces the user's follow-up question. Discussion preserves the saved conversation; draft review labels generated answers as unreviewed and exposes continuation only for a truncated response.

Case persistence stays revision-bound and owner-scoped through existing APIs. Archive/restore asks for confirmation. Archived cases disable edits. The prompt is saved before streaming. Interrupted text remains visible as an unsaved partial response, with reload-before-retry guidance. A failed case switch clears the previous case instead of showing stale content. A revision conflict retains edits for copying/reconciliation; it is not automatically retried with a newer revision.

Unsaved changes guard navigation and tab closure. Same-account reauthentication keeps the mounted case in memory, hidden and inert while locked. A different account remounts the workspace. No patient text, passwords or bearer tokens are newly stored in browser storage. Reloading/closing the tab can still lose unsaved text; the UI does not claim crash recovery.

## Hospital and administrator journeys

Application explains authority verification, local compute and raw-data boundaries. A successful response provides a copyable application reference. No email or status notification is invented. Administrators see pending decisions first and must supply a verification reference and confirm the access decision.

Institution setup identifies the next action and separates assigned access, recorded identity binding, policy eligibility, unknown connectivity, local dataset preparation and unavailable contribution history. Approved access is not presented as a working Flower runner. Installation and local mapping controls stay visibly disabled until supported contracts exist. Existing public-key binding and participation controls remain available to administrators; private keys do not belong in these forms.

## Research and visual system

The previous experiment tools are embedded in the shared shell. Tabular simulation, inference, corpus preparation and medical-model weight training remain distinct. The federation animation stays in research. Model Evolution explains the absence of comparable evaluation artifacts; no fabricated metrics or quality gains are displayed.

`redesign.css`, imported through `workspace.css`, replaces the previous visual system with navy navigation, blue primary actions, pale blue surfaces, larger readable headings and responsive task layouts. The case landing page introduces Describe → Check → Discuss before the searchable library. Each case stage explains its next action, and intake includes optional first-time guidance. `research.css` scopes retained research visuals. Reusable headers, alerts, loading states, status pills and a native-button stepper establish consistent semantics. Labels and words accompany statuses; color alone never establishes readiness. Native details expose technical information, native confirmation handles destructive decisions, and focus outlines/skip navigation remain available. Reduced motion removes decorative CSS motion, while the existing globe observes the system preference.

## Before and after

| Previous view | Updated view |
| --- | --- |
| Monolithic portal and separate research shell | Shared role-aware shell and URL navigation |
| Dense saved-case dropdown | Searchable case library with active/archive filtering |
| All case controls in one long form | Intake → fact review → discussion → draft review |
| Review action overwrote the prompt | Reviewed summary and user question stay separate |
| Hospital registry fields without a setup path | Next action, readiness checklist and explicit unavailable steps |
| Research navigation mostly exposed through admin | Direct researcher landing with existing tools preserved |
| Medical-model comparison absent | Honest empty evolution page and documented required contracts |

Unsupported capabilities and required backend contracts are listed in [backend-dependencies.md](backend-dependencies.md); verification and limits are recorded in [VERIFICATION.md](VERIFICATION.md).

## Second design iteration

Following owner feedback, the earlier green workspace styling was replaced completely. Login, navigation, case landing, workflow instructions, cards, forms, hospital setup and research surfaces share the new system. Navigation now uses task names such as Hospital requests, Manage workspace and Learning network. The original federation sphere and event-driven contribution pulses remain intact; no simulated events were added.

## Continuous conversation

Discussion and draft review now share one scrollable conversation and a persistent follow-up composer. Saved conversations reopen directly in chat. Streams and pending user text appear in the thread, with interrupted text explicitly unsaved. Auto-scroll follows new text only while the reader is near the bottom; Latest messages restores following. Enter sends and Shift+Enter adds a line. Full saved history is the default context; reviewed-summary context remains opt-in. Case facts remain separately accessible.

## Chat controls, routes and preferences

Chat uses the viewport with a bottom composer and internal message scrolling. Context help, safety notice, case settings and runtime diagnostics are above it; the workspace footer is hidden on case routes. The in-field arrow fades when the typing bar loses focus and is disabled for empty/busy/unavailable requests. Preferences expose display name, preset profile icon and light/dark/device appearance from the profile menu on every signed-in page. Preferences are saved per account with session/CSRF checks. No password is stored in preferences.

Routes now use the browser pathname with server-side workspace fallbacks. Legacy hash bookmarks migrate to clean paths; unknown API or private-file paths never receive the SPA fallback. The shared password field has a reveal/hide control. Password changes still require the current password and revoke existing sessions.

Notifications poll every 15 seconds in an active, unlocked workspace. Server-side filtering selects own events, explicitly applicable node events and permitted research/admin lifecycle activity, returning only IDs, safe titles, timestamps and read flags. Raw audit payloads are not copied into the inbox. Read markers are account-owned. This is a bounded recent-activity inbox, not push delivery or an unlimited audit archive.
