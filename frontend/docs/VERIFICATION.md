# Verification record — 24 October 2026

This record covers the frontend redesign and separately authorized hybrid trainer. No VPS deployment, hospital installation, real clinical evaluation or MedGemma weight training was performed.

## Executed checks

| Check | Result |
| --- | --- |
| `npm ci` in frontend | Clean install succeeded; 137 packages audited, no reported vulnerabilities. One transitive whatwg-encoding deprecation warning. |
| `npm test` | 17 tests passed across API replay, case workflows, sessions/hospital decisions and accessibility. |
| `npm run build` | TypeScript and Vite production build passed; 48 modules. |
| `.venv/Scripts/ruff.exe check .` | Passed. |
| `.venv/Scripts/ruff.exe format --check .` | 70 Python files already formatted. |
| `.venv/Scripts/python.exe -m pytest -q` | 80 passed. Five existing dependency/PEFT warnings, no failures. |
| Hybrid tests | Tiny GPT-2/Gemma 3 full/LoRA checkpoints; Gemma 3 gradient checkpointing and adapter-to-full escalation; base/student held-out losses; integrity, revision and cross-stage split guards. CUDA/QLoRA execution was not available. |

The DOM tests cover new case → organization → fact review → discussion → persisted response, preserving the user question, stale-revision recovery, duplicate saves, interrupted streams, archived read-only state, failed case switching, role-route boundaries, cancelled navigation, rejected login, same-account session recovery, honest bound-node readiness, confirmation before application decisions, keyboard skip navigation and reduced-motion globe behavior. These use explicit synthetic API fixtures, not clinical output assertions.

## Firefox and visual checks

Used an isolated headless Firefox profile and localhost Vite server. Authentication/data responses were replaced only in browser memory with synthetic fixtures; no live accounts, hospital records or model requests were used. The browser's outer-window minimum was 500px, so exact 375px checks used a same-origin 375-CSS-pixel iframe. The measured child `innerWidth` was verified rather than assuming the requested window size.

Checked 36 layout combinations: 375/768/1280/1440px across case library, new case, institution setup, admin admission queue, admin users, research overview, research datasets, research experiments and model evolution. In these fixtures `documentElement.scrollWidth === innerWidth` throughout. Visually inspected login, desktop case library, tablet/mobile intake, mobile hospital setup, desktop admin queue and research overview. Fixed research-hero heading contrast found during inspection. Long populated tables, arbitrary data and all browser/OS combinations are not exhaustively certified by these checks.

Keyboard Tab in Firefox reached a research action with a visible outline. DOM tests exercise the skip link using Enter. Main navigation uses real links; forms use labels/native controls; errors and notices use alert/status semantics; workflow state uses `aria-current`. Tested reduced-motion globe suppression with a mocked matching system preference and reviewed the CSS reduction rule. A full assistive-technology session with NVDA/JAWS/VoiceOver was not performed.

Calculated contrast ratios for principal token pairs: primary/white 7.60, body/background 12.23, muted/white 6.01, warning 6.45, error 6.43, research-hero heading 8.33. These checks are not a blanket WCAG certification of every retained research chart and populated state.

## Role-by-role acceptance script

Run this against a separate authorized integration environment before deployment; use fictional information only.

1. **Clinician:** sign in; open My cases; create a synthetic case; save; organize it; correct extracted facts and save the review. Confirm the follow-up remains user-authored. Discuss, inspect generated labels, reload, navigate back/forward, archive and restore. Simulate a stale revision and dropped stream; confirm unsaved text remains recoverable and partial text is not shown as a successful saved answer.
2. **Session:** expire the cookie while editing; confirm the workspace becomes hidden/inert and same-account login restores the draft. Log in as a different fixture account and verify the previous case is absent. Test rejected login and sign-out. A tab reload deliberately does not preserve unsaved private text.
3. **Hospital applicant:** submit a fictional authorized application; retain/copy its returned reference; verify the UI explains manual validation and does not promise email or live connectivity. Duplicate/rejected submissions must show the server error without implying approval.
4. **Hospital/client:** open Institution setup; inspect policy, binding, connection, mapping and participation separately. A bound identity must still show unknown connectivity. Confirm there is no central patient dataset upload or fabricated successful round. Client role must not expose clinician inference.
5. **Administrator:** inspect pending applications; cancel a proposed decision; then confirm a fixture decision with a real test verification reference. Review the assigned node and existing user/participation/corpus/dataset/runtime/audit controls. Administrator case access remains owner-scoped.
6. **Researcher/viewer:** open every research subroute and refresh a deep link. Run an authorized synthetic tabular experiment, import permitted test CSV, inspect results and activate a research candidate with the appropriate role. Viewers must not run mutations; the API must reject unauthorized GraphQL requests regardless of UI controls. Evolution must remain empty until measured medical-model artifacts are supplied.
7. **Accessibility/layout:** repeat the supported journeys at all four widths with keyboard only, reduced motion and a screen reader. Check long names, populated tables, focus return, labels and announcements. Record any issue with route, role and viewport.

## Known limits and integration dependencies

The local browser checks did not connect the redesigned frontend to the deployed VPS or execute real MedGemma inference. Existing Python endpoint tests passed, but a deployed end-to-end check remains necessary before release. Live hospital connectivity, local mapper/runner installation, hospital-specific history, evidence retrieval, treatment validation and comparable MedGemma evaluations need the contracts listed in [backend-dependencies.md](backend-dependencies.md). The UI exposes their absence instead of simulating success.

The design board was inaccessible; no claim of visual equivalence is made. Native browser confirmation is used rather than an additional dialog library. Viewers still see the GraphQL explorer; server-side authorization is authoritative. The frontend brief explicitly excludes deployment and backend changes; the shared VPS was not touched.

## Second design iteration checks

After replacing the visual system, all 17 frontend tests and the TypeScript/Vite production build passed again. Firefox fixture checks covered 20 combinations: case library, intake, institution setup, admin users and research overview at 375/768/1280/1440 CSS pixels. No document overflow was measured. Visually inspected desktop login/library/network and mobile intake. These checks use isolated synthetic fixtures, not deployed accounts. FederationGlobe.tsx and its event logic were unchanged. Earlier palette contrast measurements describe the previous design and should not be treated as certification of the replacement palette.

## Composer and preference update

19 frontend tests passed, including clean-URL migration/back navigation and password visibility. Backend account/preference/notification tests cover all six roles, CSRF, cross-account preference isolation, foreign read markers, safe notification payloads, current-password verification, clean deep links and private/unknown URL rejection. Browser fixtures checked chat at 375/768/1280/1440px in both light and dark appearance: no document horizontal overflow; the composer was the last chat element, 13–17px above the viewport edge; the footer was hidden. Layout checks use synthetic fixtures, not medical-response validation.

Runtime response controls detect repeated sentences/bullets during streaming and reject looping outputs before saving a completed answer. Continuation explicitly targets unfinished content and refuses already complete replies. These are runtime safeguards, not weight fine-tuning. Training evidence and remaining clinical/hardware gates are in `docs/FEDERATED_ADAPTER_VERIFICATION.md`.
