import type { CaseSession } from "../useCaseSession";
import { EmptyState, StatusPill } from "./ui";

export default function FactReview({ session: s }: { session: CaseSession }) {
  if (!s.summary)
    return (
      <EmptyState
        title="No extracted facts yet"
        action={
          <button onClick={() => s.setStage(0)}>Return to case intake</button>
        }
      >
        Choose Organize case after describing the case. You can also discuss a
        question directly without creating a summary.
      </EmptyState>
    );
  return (
    <section className="card">
      <div className="section-heading">
        <h2>Confirm the understanding</h2>
        <StatusPill tone={s.reviewed ? "good" : "warning"}>
          {s.reviewed ? "User-reviewed draft" : "AI-extracted · unreviewed"}
        </StatusPill>
      </div>
      <p>
        Compare with your original description. Correct contradictions, preserve
        unknowns and verify values and units. Saving a review does not establish
        clinical validation or an approved medical record.
      </p>
      <details>
        <summary>Original provided information</summary>
        {s.messages
          .filter((m) => m.role === "user")
          .map((m, i) => (
            <p className="preserve-text" key={i}>
              {m.content}
            </p>
          ))}
      </details>
      <label>
        Editable case understanding
        <textarea
          rows={12}
          value={s.summary}
          maxLength={20000}
          disabled={s.busy || s.archived}
          onChange={(e) => s.editSummary(e.target.value)}
        />
      </label>
      <div className="button-row">
        <button
          disabled={s.busy || s.archived || !s.summary.trim() || !s.confirmed}
          onClick={s.saveReview}
        >
          Save reviewed facts & discuss →
        </button>
        <button
          className="secondary"
          disabled={
            !s.reviewed || s.busy || s.summary !== s.active?.details.summary
          }
          onClick={() => {
            const url = URL.createObjectURL(
              new Blob(
                [
                  `MedFlock · Synthetic case\nUser-reviewed draft, not a validated clinical record.\n\n${s.summary}`,
                ],
                { type: "text/plain;charset=utf-8" },
              ),
            );
            const a = document.createElement("a");
            a.href = url;
            a.download = "medflock-case-draft.txt";
            a.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
          }}
        >
          Export reviewed draft
        </button>
      </div>
      {!!s.reviews.length && (
        <details>
          <summary>Saved review versions ({s.reviews.length})</summary>
          {s.reviews.map((r) => (
            <article key={r.id}>
              <h3>
                Revision {r.revision} ·{" "}
                {new Date(r.created_at).toLocaleString()}
              </h3>
              <p className="preserve-text">{r.summary}</p>
            </article>
          ))}
        </details>
      )}
    </section>
  );
}
