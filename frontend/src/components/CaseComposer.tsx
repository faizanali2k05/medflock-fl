import type { CaseSession } from "../useCaseSession";

export default function CaseComposer({
  session: s,
  ready,
}: {
  session: CaseSession;
  ready: boolean;
}) {
  if (s.stage >= 2)
    return (
      <form className="chat-composer" onSubmit={s.submit}>
        {!s.confirmed && (
          <label className="check-label">
            <input
              type="checkbox"
              required
              checked={s.confirmed}
              onChange={(e) => s.setConfirmed(e.target.checked)}
            />
            This is a synthetic case with no real patient information.
          </label>
        )}
        <div className="typing-bar">
          <label className="sr-only" htmlFor="chat-message">
            Your message
          </label>
          <textarea
            id="chat-message"
            rows={3}
            value={s.prompt}
            required
            maxLength={20000}
            disabled={s.busy || s.archived}
            placeholder={
              ready
                ? "Reply to MedGemma…"
                : "Runtime unavailable. You can still write and save a draft above."
            }
            onChange={(e) => s.editPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (
                e.key === "Enter" &&
                !e.shiftKey &&
                !e.nativeEvent.isComposing
              ) {
                e.preventDefault();
                if (
                  !s.busy &&
                  !s.archived &&
                  ready &&
                  s.confirmed &&
                  s.prompt.trim()
                )
                  e.currentTarget.form?.requestSubmit();
              }
            }}
          />
          <button
            className="send-arrow"
            aria-label="Send message"
            disabled={
              s.busy || s.archived || !ready || !s.confirmed || !s.prompt.trim()
            }
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 19V5m-6 6 6-6 6 6" />
            </svg>
          </button>
        </div>
      </form>
    );
  return (
    <section
      className={`card case-composer ${s.stage >= 2 ? "chat-composer" : ""}`}
    >
      <div className="section-heading composer-intro">
        <div>
          <div className="eyebrow">
            {s.stage === 0 ? "PROVIDED INFORMATION" : "YOUR FOLLOW-UP"}
          </div>
          <h2>
            {s.stage === 0 ? "Describe the case" : "Continue the discussion"}
          </h2>
        </div>
      </div>
      <p>
        {s.stage === 0
          ? "Write naturally. Include the timeline, medicines, allergies and available results with their units. Unknown information can stay unknown."
          : "Ask a focused question or add new information. Your original messages remain in the saved conversation."}
      </p>
      {s.stage === 0 && (
        <details className="intake-help">
          <summary>First time? Here is what to include</summary>
          <ul>
            <li>What happened, and when did it start?</li>
            <li>Relevant history, medicines and allergies.</li>
            <li>Examination findings and results, with units.</li>
            <li>The question you want to explore.</li>
          </ul>
          <p>
            You do not need every detail. Leave unknown information unknown.
          </p>
        </details>
      )}
      <form onSubmit={s.submit}>
        {s.stage === 0 && (
          <label>
            What would you like to do?
            <select
              value={s.mode}
              disabled={s.busy || s.archived}
              onChange={(e) => s.setMode(e.target.value)}
            >
              <option value="organize">Organize the facts for my review</option>
              <option value="chat">Discuss a question directly</option>
            </select>
          </label>
        )}
        <label>
          {s.stage === 0 ? "Case description" : "Your message"}
          <textarea
            rows={s.stage === 0 ? 10 : 3}
            onKeyDown={(e) => {
              if (
                s.stage >= 2 &&
                e.key === "Enter" &&
                !e.shiftKey &&
                !e.nativeEvent.isComposing
              ) {
                e.preventDefault();
                if (
                  !s.busy &&
                  !s.archived &&
                  ready &&
                  s.prompt.trim() &&
                  s.confirmed
                )
                  e.currentTarget.form?.requestSubmit();
              }
            }}
            value={s.prompt}
            required
            maxLength={20000}
            disabled={s.busy || s.archived}
            onChange={(e) => s.editPrompt(e.target.value)}
            placeholder="Describe a fictional case. Keep values, units and timing explicit; do not include real identifiers."
          />
        </label>
        <label className="check-label">
          <input
            type="checkbox"
            checked={s.confirmed}
            required
            disabled={s.busy || s.archived}
            onChange={(e) => s.setConfirmed(e.target.checked)}
          />
          This is a synthetic case with no real patient information.
        </label>
        {s.reviewed && (
          <label className="check-label">
            <input
              type="checkbox"
              checked={s.useSummary}
              disabled={s.busy}
              onChange={(e) => s.setUseSummary(e.target.checked)}
            />
            Use my reviewed summary instead of earlier discussion for this
            request. Verify it includes every relevant correction; saved history
            is retained.
          </label>
        )}
        <div className="button-row composer-actions">
          <button
            aria-label={s.stage >= 2 ? "Send message" : undefined}
            className={s.stage >= 2 ? "send-arrow" : undefined}
            disabled={
              s.busy || s.archived || !ready || !s.prompt.trim() || !s.confirmed
            }
          >
            {s.stage >= 2 ? (
              <span aria-hidden="true">{s.busy ? "…" : "↑"}</span>
            ) : s.busy ? (
              `Working · ${s.elapsed}s`
            ) : s.stage === 0 && s.mode === "organize" ? (
              "Organize case →"
            ) : (
              "Send question →"
            )}
          </button>
          <button
            type="button"
            className="secondary"
            disabled={s.busy || s.archived || !s.confirmed}
            onClick={s.saveDraft}
          >
            Save without sending
          </button>
        </div>
        {!ready && (
          <p role="status">
            Inference is unavailable or disabled. You can still save a draft.
            Check Technical details for runtime status.
          </p>
        )}
      </form>
    </section>
  );
}
