import type { ReactNode } from "react";
import { useCaseSession } from "./useCaseSession";
import { navigate, canUseCases, type Role } from "./navigation";
import { Alert, Loading, StatusPill, WorkflowSteps } from "./components/ui";
import CaseComposer from "./components/CaseComposer";
import FactReview from "./components/FactReview";
import CaseDiscussion from "./components/CaseDiscussion";

export default function CaseChat({
  role,
  ready,
  caseId = "new",
  runtimeDetails,
}: {
  role: string;
  ready: boolean;
  caseId?: string;
  runtimeDetails?: ReactNode;
}) {
  const s = useCaseSession(caseId);
  if (!canUseCases(role as Role))
    return <Alert>Your account cannot create case discussions.</Alert>;
  if (s.loading) return <Loading label="Opening your saved case" />;
  if (caseId !== "new" && !s.active)
    return (
      <Alert error>
        {s.error || "The saved case is unavailable."}
        <div className="button-row">
          <button onClick={s.reload}>Retry opening case</button>
          <button className="secondary" onClick={() => navigate("/cases")}>
            Return to My cases
          </button>
        </div>
      </Alert>
    );
  return (
    <div className="case-workflow" data-chat-mode={s.stage >= 2}>
      <details className="case-menu">
        <summary>
          <h1 className="case-menu-title">
            {s.title || "Work through a case"}
          </h1>
          <span className="case-menu-status">
            MedGemma · {ready ? "Available" : "Unavailable"} · Case details
          </span>
        </summary>
        <div className="case-menu-panel">
          <p>
            Synthetic cases only · Unreviewed model output. Verify clinical
            claims independently; guideline retrieval and medication checks are
            not configured. Enter sends · Shift+Enter adds a line.
          </p>
          <p>
            Your full saved conversation is included by default. Using a
            reviewed summary is an explicit choice. Runtime capacity still
            applies.
          </p>
          {s.stage >= 2 && s.reviewed && (
            <label className="check-label">
              <input
                type="checkbox"
                checked={s.useSummary}
                disabled={s.busy}
                onChange={(e) => s.setUseSummary(e.target.checked)}
              />
              Use my reviewed summary instead of earlier discussion for this
              request. Saved history is retained.
            </label>
          )}
          {runtimeDetails}
          <div
            className={`workflow-intro ${s.stage >= 2 ? "conversation-intro" : ""}`}
          >
            <span className="eyebrow">STEP {s.stage + 1} OF 4</span>
            <h2>
              {
                [
                  "Let's understand the case.",
                  "Does this match your case?",
                  "What would you like to explore?",
                  "Take a moment to review.",
                ][s.stage]
              }
            </h2>
            <p>
              {
                [
                  "Start with what you know. You can add missing information as you go.",
                  "Check the facts and correct any mistakes before using the summary.",
                  "Ask a follow-up or add new details. Your conversation stays with this case.",
                  "Read the generated answer carefully. It needs independent clinical review.",
                ][s.stage]
              }
            </p>
          </div>
          <div className="case-toolbar">
            <button className="secondary" onClick={() => navigate("/cases")}>
              ← My cases
            </button>
            <StatusPill tone="warning">Synthetic research case</StatusPill>
            <span role="status">
              {s.active
                ? `Revision ${s.active.revision} · ${s.active.status}`
                : "New unsaved case"}
              {s.dirty ? " · Unsaved edits" : ""}
            </span>
            <div className="case-actions">
              <button
                className="secondary"
                disabled={s.busy || s.archived || !s.confirmed}
                onClick={s.saveDraft}
              >
                Save draft
              </button>
              {(s.active || caseId !== "new") && (
                <button
                  className="secondary"
                  disabled={s.busy}
                  onClick={s.reload}
                >
                  Reload saved version
                </button>
              )}
              {s.active && (
                <button
                  className="secondary"
                  disabled={s.busy}
                  onClick={s.changeStatus}
                >
                  {s.archived ? "Restore case" : "Archive case"}
                </button>
              )}
            </div>
          </div>
          <label className="case-title-label">
            Case title · no identifying information
            <input
              value={s.title}
              maxLength={120}
              required
              disabled={s.busy || s.archived}
              onChange={(e) => s.editTitle(e.target.value)}
            />
          </label>
          {s.stage >= 2 && (
            <button className="secondary" onClick={() => s.setStage(1)}>
              Review case facts
            </button>
          )}
        </div>
      </details>
      {s.archived && (
        <Alert>
          This case is read-only. Restore it to edit or continue the discussion.
        </Alert>
      )}
      {s.stage < 2 && (
        <WorkflowSteps
          steps={["Case intake", "Confirm facts", "Discuss", "Review draft"]}
          current={s.stage}
          onSelect={(index) => {
            if (!s.busy) s.setStage(index);
          }}
        />
      )}
      {s.error && (
        <Alert error>
          {s.error}
          <p>
            Your edits are still visible here. Reopen the saved version before
            retrying an interrupted request; copy unsaved edits first.
          </p>
        </Alert>
      )}
      {s.notice && <Alert>{s.notice}</Alert>}
      {!!s.active?.details.quality_warnings?.length && (
        <Alert error>
          <strong>Source consistency requires review</strong>
          {s.active.details.quality_warnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
          <p>
            This limited automated check does not establish clinical
            correctness.
          </p>
        </Alert>
      )}
      {s.busy && (
        <Alert>
          Working · {s.elapsed}s elapsed. CPU inference can take several
          minutes. Your prompt is saved before generation. Keep this page open;
          no completion time is estimated.
        </Alert>
      )}
      {s.liveDraft && s.stage < 2 && (
        <section className="card live-draft">
          <h2>
            {s.busy
              ? "Live unreviewed draft"
              : "Interrupted draft · not saved as an answer"}
          </h2>
          <p>
            Partial text may be incomplete or incorrect. Do not use it for care
            decisions.
          </p>
          <div className="preserve-text">{s.liveDraft}</div>
        </section>
      )}
      {s.stage === 0 && <CaseComposer session={s} ready={ready} />}
      {s.stage === 1 && <FactReview session={s} />}
      {(s.stage === 2 || s.stage === 3) && (
        <CaseDiscussion session={s} ready={ready} />
      )}
    </div>
  );
}
