import { useEffect, useRef, useState } from "react";
import type { CaseSession } from "../useCaseSession";
import CaseComposer from "./CaseComposer";
import ModelText, { hasRepetition } from "./ModelText";

export default function CaseDiscussion({
  session: s,
  ready,
}: {
  session: CaseSession;
  ready: boolean;
}) {
  const thread = useRef<HTMLDivElement>(null),
    pinned = useRef(true);
  const [away, setAway] = useState(false);
  function latest() {
    const element = thread.current;
    if (element) element.scrollTop = element.scrollHeight;
    pinned.current = true;
    setAway(false);
  }
  useEffect(() => {
    if (pinned.current) latest();
  }, [s.messages.length, s.liveDraft, s.busy]);
  return (
    <section className="chat-workspace" aria-label="Case chat">
      <div
        className="chat-thread"
        ref={thread}
        tabIndex={0}
        aria-label="Saved case conversation"
        onScroll={() => {
          const el = thread.current;
          if (el) {
            pinned.current =
              el.scrollHeight - el.scrollTop - el.clientHeight < 80;
            setAway(!pinned.current);
          }
        }}
      >
        {!s.messages.length && (
          <p className="chat-start">
            Ask your first question below. Add details and follow up in this
            same conversation.
          </p>
        )}
        {s.messages.map((m, i) => (
          <article className={`thread-message ${m.role}`} key={i}>
            <div className="message-avatar" aria-hidden="true">
              {m.role === "user" ? "Y" : "M"}
            </div>
            <div className="message-body">
              <strong>
                {m.role === "user" ? "You" : "MedGemma · unreviewed draft"}
              </strong>
              {m.role === "user" ? (
                <div className="preserve-text">{m.content}</div>
              ) : (
                <ModelText text={m.content} />
              )}
            </div>
          </article>
        ))}
        {s.busy && (
          <article className="thread-message user">
            <div className="message-avatar" aria-hidden="true">
              Y
            </div>
            <div className="message-body">
              <strong>You · sending</strong>
              <div className="preserve-text">{s.prompt}</div>
            </div>
          </article>
        )}
        {(s.busy || s.liveDraft) && (
          <article className="thread-message assistant">
            <div className="message-avatar" aria-hidden="true">
              M
            </div>
            <div className="message-body">
              <strong>
                {s.busy
                  ? "MedGemma · writing an unreviewed draft"
                  : "Interrupted draft · not saved as an answer"}
              </strong>
              <div className="preserve-text">
                {s.liveDraft || "Preparing a response…"}
              </div>
              <small role="status">
                {s.busy
                  ? `${s.elapsed}s elapsed`
                  : "Reload the saved case before retrying."}
              </small>
            </div>
          </article>
        )}
      </div>
      {away && (
        <button className="jump-latest secondary" onClick={latest}>
          ↓ Latest messages
        </button>
      )}
      {s.active?.details.last_output_truncated &&
        !hasRepetition(
          s.messages.filter((m) => m.role === "assistant").at(-1)?.content ||
            "",
        ) && (
          <div className="chat-truncated">
            <span>The previous answer is incomplete.</span>
            <button
              className="secondary"
              disabled={s.busy || s.archived}
              onClick={s.continueResponse}
            >
              Continue response
            </button>
          </div>
        )}
      {!s.archived && <CaseComposer session={s} ready={ready} />}
    </section>
  );
}
