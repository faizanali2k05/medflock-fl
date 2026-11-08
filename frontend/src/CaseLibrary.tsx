import { useEffect, useState } from "react";
import { workspaceApi, type CaseSummary } from "./workspaceApi";
import { navigate } from "./navigation";
import { Alert, EmptyState, Loading, StatusPill } from "./components/ui";

export default function CaseLibrary() {
  const [cases, setCases] = useState<CaseSummary[]>([]),
    [filter, setFilter] = useState("active"),
    [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  async function refresh() {
    setLoading(true);
    setError("");
    try {
      setCases(await workspaceApi.cases());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    refresh();
  }, []);
  const visible = cases.filter(
    (c) =>
      (filter === "all" || c.status === filter) &&
      c.title.toLowerCase().includes(search.toLowerCase()),
  );
  const newCase = (
    <button onClick={() => navigate("/cases/new")}>
      ＋ New synthetic case
    </button>
  );
  return (
    <main className="portal-main">
      <header className="care-welcome">
        <div>
          <span className="eyebrow">YOUR CARE WORKSPACE</span>
          <h1>
            Every case starts
            <br />
            with a conversation.
          </h1>
          <p>
            Bring the details. Review the understanding.
            <br />
            Explore the next question with MedGemma.
          </p>
          {newCase}
        </div>
        <div className="welcome-visual" aria-hidden="true">
          <div className="visual-orbit">
            <span>+</span>
          </div>
          <svg viewBox="0 0 360 120">
            <path d="M0 60H85L108 44L128 80L155 12L184 108L210 48L232 60H360" />
          </svg>
          <span className="visual-caption">INFORMATION → UNDERSTANDING</span>
        </div>
      </header>
      <section className="start-guide" aria-label="How to get started">
        <div>
          <span className="guide-number">1</span>
          <div>
            <h2>Describe</h2>
            <p>Write the case naturally, in your own words.</p>
          </div>
        </div>
        <div>
          <span className="guide-number">2</span>
          <div>
            <h2>Check</h2>
            <p>Correct the extracted facts before continuing.</p>
          </div>
        </div>
        <div>
          <span className="guide-number">3</span>
          <div>
            <h2>Discuss</h2>
            <p>Ask questions and review the model's draft.</p>
          </div>
        </div>
      </section>
      <div className="section-heading library-heading">
        <div>
          <span className="eyebrow">PICK UP WHERE YOU LEFT OFF</span>
          <h2>Your case library</h2>
        </div>
        <StatusPill tone="warning">Synthetic cases only</StatusPill>
      </div>
      <div className="library-tools">
        <div className="segmented" aria-label="Case status">
          {["active", "archived", "all"].map((value) => (
            <button
              key={value}
              aria-pressed={filter === value}
              onClick={() => setFilter(value)}
            >
              {value[0].toUpperCase() + value.slice(1)}
            </button>
          ))}
        </div>
        <label className="search-label">
          Find a case
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search your case titles"
          />
        </label>
      </div>
      {error ? (
        <Alert error>
          {error} <button onClick={refresh}>Try loading again</button>
        </Alert>
      ) : loading ? (
        <Loading label="Loading your cases" />
      ) : !visible.length ? (
        <EmptyState
          title={
            cases.length ? "No matching cases" : "Your first case belongs here"
          }
          action={cases.length ? undefined : newCase}
        >
          {cases.length
            ? "Change the status filter or search to find a saved case."
            : "Describe a synthetic case in your own words. Then review the extracted facts and continue the discussion."}
        </EmptyState>
      ) : (
        <div className="case-grid">
          {visible.map((c) => (
            <article className="case-card" key={c.id}>
              <div className="section-heading">
                <StatusPill>{c.status}</StatusPill>
                <small>Revision {c.revision}</small>
              </div>
              <h2>{c.title}</h2>
              <p>Synthetic research case</p>
              <time dateTime={c.updated_at}>
                Updated {new Date(c.updated_at).toLocaleString()}
              </time>
              <button
                className="secondary"
                onClick={() => navigate(`/cases/${c.id}`)}
              >
                {c.status === "archived"
                  ? "View archived case"
                  : "Continue case"}
                <span aria-hidden="true"> →</span>
              </button>
            </article>
          ))}
        </div>
      )}
    </main>
  );
}
