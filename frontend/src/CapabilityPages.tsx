import { EmptyState, PageHeader, StatusPill } from "./components/ui";

export function EvolutionLab() {
  return (
    <main className="portal-main">
      <PageHeader
        eyebrow="MODEL DEVELOPMENT"
        title="Model evolution"
        description="Evidence before a new model becomes the next model."
      />
      <div className="clinical-banner">
        <StatusPill>Not connected to training</StatusPill>
        <span>
          Corpus upload, tabular experiments and pretrained model inference are
          separate capabilities.
        </span>
      </div>
      <EmptyState title="No comparable evaluations available">
        This workspace has no API for verified original-versus-adapted MedGemma
        evaluations. No medical weight-training result is presented here.
      </EmptyState>
      <section className="card">
        <h2>What a comparison will need</h2>
        <ol className="readiness-list">
          <li>
            <strong>Identifiable candidates</strong>
            <p>
              Original checkpoint, adapter or full-weight checkpoint, and
              immutable versions.
            </p>
          </li>
          <li>
            <strong>Shared evaluation</strong>
            <p>
              The same held-out cases, evidence, inference settings and
              evaluation protocol.
            </p>
          </li>
          <li>
            <strong>Clinical review</strong>
            <p>
              Useful discussion, unsupported recommendations, missed facts and
              medication errors assessed alongside measured performance.
            </p>
          </li>
        </ol>
        <p>
          Comparison data and training controls require backend integration.
          There is no training action on this page.
        </p>
      </section>
    </main>
  );
}
export function Help() {
  return (
    <main className="portal-main">
      <PageHeader
        eyebrow="WORKSPACE GUIDE"
        title="Know what has completed"
        description="A draft, a connected runner and a validated model are different things."
      />
      <div className="case-grid">
        {[
          [
            "Care professionals",
            "Open My cases, create a synthetic case, describe it naturally, review the extracted facts, then discuss and save. Your review acknowledges your edited summary; it does not validate the model.",
          ],
          [
            "Hospital partners",
            "Institution approval enables access. Runner identity binding, live connectivity, local dataset validation and accepted training contributions are separate conditions. Keep patient records on hospital-controlled systems.",
          ],
          [
            "Researchers",
            "Research workspace preserves tabular experiments and their measured results. These simulations are not hospital federation or MedGemma distillation.",
          ],
          [
            "If a request fails",
            "Your prompt is saved before generation. Reopen the saved case before retrying an interrupted request, to avoid duplicating a response that may have completed. Unsaved edits remain in the current page; copy them before reloading.",
          ],
          [
            "Treatment and evidence",
            "The current model produces unvalidated discussion. Guideline retrieval, medication safety checking and authorized prescription orders are not available. Never interpret formatting or a saved review as clinical approval.",
          ],
          [
            "Patient access",
            "A patient-facing education or treatment service is not enabled in this beta. Contact the administrator for account or institution access issues.",
          ],
        ].map(([title, text]) => (
          <section className="card" key={title}>
            <h2>{title}</h2>
            <p>{text}</p>
          </section>
        ))}
      </div>
    </main>
  );
}
