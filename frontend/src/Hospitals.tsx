import { useEffect, useState } from "react";
import { rest, type Node } from "./api";
import {
  workspaceApi,
  type HospitalNode,
  type ApplicationRecord,
} from "./workspaceApi";
import { Alert, Loading, PageHeader, StatusPill } from "./components/ui";

export function HospitalWorkspace() {
  const [node, setNode] = useState<HospitalNode | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  async function refresh() {
    setLoading(true);
    setError("");
    try {
      setNode(await workspaceApi.node());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    refresh();
  }, []);
  return (
    <main className="portal-main">
      <PageHeader
        eyebrow="HOSPITAL PARTNER"
        title="Institution setup"
        description={
          node
            ? node.label
            : "Your route to shared learning, with patient records kept local."
        }
        action={
          <button className="secondary" disabled={loading} onClick={refresh}>
            Refresh status
          </button>
        }
      />
      {error && (
        <Alert error>
          {error} <button onClick={refresh}>Try again</button>
        </Alert>
      )}
      {loading && !node ? (
        <Loading label="Checking assigned institution" />
      ) : (
        node && (
          <>
            <section className="next-action">
              <div className="eyebrow">NEXT ACTION</div>
              <h2>
                {node.transport_binding
                  ? "Arrange a verified connection check"
                  : "Prepare your hospital-controlled runner"}
              </h2>
              <p>
                {node.transport_binding
                  ? "Your identity binding is recorded. The current portal cannot verify live connectivity. Ask your administrator to complete the authenticated runner check before any training round."
                  : "Choose a hospital-controlled computer and contact your administrator for the approved runner package and enrollment instructions. A VPS is not required."}
              </p>
              <button
                onClick={() =>
                  document
                    .getElementById("runner-setup")
                    ?.scrollIntoView({ behavior: "auto", block: "center" })
                }
              >
                View setup requirements
              </button>
            </section>
            <div className="hospital-fields">
              <section className="card">
                <div className="eyebrow">PARTICIPATION POLICY</div>
                <h2>{node.effective_status}</h2>
                <p>
                  {node.training_allowed
                    ? "Policy permits participation. This alone does not establish connectivity or data readiness."
                    : "Contributions are not currently eligible. Ask the administrator to review your participation policy."}
                </p>
                {node.details.suspended_until && (
                  <p>
                    Suspension expiry:{" "}
                    {new Date(node.details.suspended_until).toLocaleString()}
                  </p>
                )}
              </section>
              <section className="card">
                <div className="eyebrow">LIVE CONNECTION</div>
                <h2>Unknown</h2>
                <p>
                  The available API reports registry information, not a live
                  authenticated Flower connection.
                </p>
                <StatusPill tone="warning">Verification required</StatusPill>
              </section>
            </div>
            <section className="card">
              <h2>Setup checklist</h2>
              <ol className="readiness-list">
                <li>
                  <div className="section-heading">
                    <strong>1. Workspace access</strong>
                    <StatusPill tone="good">Assigned</StatusPill>
                  </div>
                  <p>
                    Your signed-in account is assigned to this institution's
                    node.
                  </p>
                </li>
                <li id="runner-setup">
                  <div className="section-heading">
                    <strong>2. Local runner and identity</strong>
                    <StatusPill
                      tone={node.transport_binding ? "good" : "warning"}
                    >
                      {node.transport_binding
                        ? "Binding recorded"
                        : "Needs action"}
                    </StatusPill>
                  </div>
                  <p>
                    Training runs on a hospital-controlled computer, not in this
                    browser. Keep the private key there. Only the public key and
                    its verified fingerprint go to the administrator.
                  </p>
                  <details>
                    <summary>Installation and enrollment requirements</summary>
                    <p>
                      The approved package must include the pinned Flower
                      runtime, trusted coordinator certificate, task contract
                      and resource settings. Your administrator registers the
                      public key and verifies the Flower-assigned node ID. This
                      portal does not install software or register keys
                      automatically.
                    </p>
                    {node.transport_binding && (
                      <p>
                        Recorded Flower identity:{" "}
                        {node.transport_binding.flower_node_id}
                      </p>
                    )}
                    <button disabled>
                      Automatic installer · not available
                    </button>
                  </details>
                </li>
                <li>
                  <div className="section-heading">
                    <strong>3. Local dataset mapping</strong>
                    <StatusPill tone="warning">Requires local setup</StatusPill>
                  </div>
                  <p>
                    Map columns, units, outcomes and patient grouping locally.
                    Raw records must not be uploaded here. No local validation
                    report is available through this API.
                  </p>
                  <details>
                    <summary>What must be reviewed locally?</summary>
                    <p>
                      Data permissions, identifiers, duplicate patients, outcome
                      definitions, units, missing values, patient-disjoint
                      splits and compatibility with the coordinator's approved
                      task contract. The existing local preparation script
                      produces checksummed bundles; guided local mapping is not
                      connected to this portal.
                    </p>
                    <button disabled>Open local mapper · not available</button>
                  </details>
                </li>
                <li>
                  <div className="section-heading">
                    <strong>4. Readiness and training</strong>
                    <StatusPill tone="warning">
                      Blocked pending verification
                    </StatusPill>
                  </div>
                  <p>
                    Identity, live connectivity, local snapshot validation and
                    participation policy all need to pass. Being eligible does
                    not mean a round has completed.
                  </p>
                </li>
                <li>
                  <div className="section-heading">
                    <strong>5. Contribution and model history</strong>
                    <StatusPill>Not available</StatusPill>
                  </div>
                  <p>
                    No hospital-specific round-history endpoint is connected.
                    Tabular research simulations are not evidence that your
                    institution contributed.
                  </p>
                </li>
              </ol>
            </section>
            <details className="card">
              <summary>Technical details</summary>
              <p>Assigned node: {node.id}</p>
              <p>Registry transport value: {node.transport}</p>
              {node.transport_binding && (
                <p className="preserve-text">
                  Public-key fingerprint:{" "}
                  {node.transport_binding.public_key_sha256}
                </p>
              )}
              <p>
                A heartbeat, if recorded, is not proof of a running Flower
                SuperNode.
              </p>
            </details>
          </>
        )
      )}
    </main>
  );
}

export function TransportBinding({ nodes }: { nodes: Node[] }) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <form
      className="card"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setMessage("");
        const { node_id, ...body } = Object.fromEntries(
          new FormData(e.currentTarget),
        );
        try {
          await rest(
            `/api/admin/nodes/${node_id}/transport-binding`,
            "POST",
            body,
          );
          setMessage(
            "Identity binding recorded. A successful authenticated round is still required to verify the connection.",
          );
        } catch (error) {
          setMessage((error as Error).message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <h2>Bind a verified Flower identity</h2>
      <p>
        First register the hospital's public key with the authenticated
        SuperLink and verify the assigned node ID. This form records that manual
        verification; it does not register a key or establish a connection.
        Never paste a private key.
      </p>
      <label>
        Hospital node
        <select name="node_id" required defaultValue="">
          <option value="" disabled>
            Select hospital
          </option>
          {nodes
            .filter(
              (n) => n.kind === "registered_external" && n.status !== "removed",
            )
            .map((n) => (
              <option key={n.id} value={n.id}>
                {n.label || n.id}
              </option>
            ))}
        </select>
      </label>
      <label>
        Flower-assigned node ID
        <input name="flower_node_id" pattern="[1-9][0-9]{0,19}" required />
      </label>
      <label>
        Registered public key SHA-256
        <input name="public_key_sha256" pattern="[a-f0-9]{64}" required />
      </label>
      <label>
        Verification record
        <input
          name="verification_reference"
          minLength={10}
          maxLength={500}
          required
        />
      </label>
      <button disabled={busy}>Record verified binding</button>
      {message && <p role="status">{message}</p>}
    </form>
  );
}

export function HospitalApplication({ close }: { close: () => void }) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [copyNotice, setCopyNotice] = useState("");
  return (
    <main className="hospital-admission">
      <aside>
        <div className="eyebrow">MEDFLOCK / HOSPITAL PARTNERS</div>
        <h1>
          Contribute learning.
          <br />
          Keep records local.
        </h1>
        <p>A shared model, built with participating care teams.</p>
        <ol>
          <li>Apply with your institution details.</li>
          <li>Complete manual identity and authority verification.</li>
          <li>Enroll a runner on a hospital-controlled computer.</li>
          <li>Validate local data before joining training.</li>
        </ol>
        <p>
          No hospital VPS is required. A compatible local computer is required
          for training. Approval grants workspace access; it does not
          automatically connect a runner.
        </p>
        <button className="secondary" onClick={close}>
          Back to sign in
        </button>
      </aside>
      <section className="panel">
        <h2>Request hospital access</h2>
        {submitted ? (
          <div role="status">
            <h3>Application received</h3>
            <p className="preserve-text">{message}</p>
            <button
              type="button"
              className="secondary"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(message);
                  setCopyNotice("Reference copied.");
                } catch {
                  setCopyNotice(
                    "Copy was unavailable. Select and copy the reference above.",
                  );
                }
              }}
            >
              Copy application reference
            </button>
            <p role="status">{copyNotice}</p>
            <p>
              Keep this reference and provide it when contacting the
              administrator. Automatic email notification is not available. An
              administrator must verify your institution and contact before
              enabling sign-in. No patient records should be sent with an
              application.
            </p>
          </div>
        ) : (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setMessage("");
              const data = Object.fromEntries(new FormData(e.currentTarget));
              try {
                const result = await rest(
                  "/api/hospital-applications",
                  "POST",
                  {
                    ...data,
                    authorized_representative: true,
                    local_data_acknowledgement: true,
                  },
                );
                setMessage(result.id);
                setSubmitted(true);
              } catch (error) {
                setMessage((error as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <div className="hospital-fields">
              {[
                ["organization", "Institution name", 160],
                ["location", "City and country", 160],
                ["contact_name", "Authorized contact", 120],
                ["contact_email", "Work email", 254],
                [
                  "registration_reference",
                  "Institution registration reference",
                  200,
                ],
                ["username", "Requested username", 64],
              ].map(([name, label, max]) => (
                <label key={name}>
                  {label}
                  <input
                    name={String(name)}
                    required
                    minLength={3}
                    maxLength={Number(max)}
                    type={name === "contact_email" ? "email" : "text"}
                    pattern={
                      name === "username" ? "[A-Za-z0-9_.-]{3,64}" : undefined
                    }
                  />
                </label>
              ))}
            </div>
            <label>
              Password
              <input
                name="password"
                type="password"
                autoComplete="new-password"
                minLength={12}
                maxLength={128}
                required
              />
            </label>
            <label>
              Intended use and available local training computer
              <textarea
                name="intended_use"
                minLength={20}
                maxLength={1500}
                required
                placeholder="Describe your team, intended task and local computing resources. Do not include patient information."
              />
            </label>
            <label>
              <input type="checkbox" required /> I am authorized to request
              participation for this institution.
            </label>
            <label>
              <input type="checkbox" required /> I understand that patient
              records must remain on the hospital-controlled runner.
            </label>
            {message && <p role="alert">{message}</p>}
            <button disabled={busy}>
              {busy ? "Submitting…" : "Submit for verification"}
            </button>
          </form>
        )}
      </section>
    </main>
  );
}

export function HospitalApplications() {
  const [rows, setRows] = useState<ApplicationRecord[]>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const refresh = () =>
    workspaceApi
      .applications()
      .then(setRows)
      .finally(() => setLoading(false));
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, []);
  return (
    <section className="panel">
      <h2>Hospital admission queue</h2>
      <p>
        Verify institutional registration, the contact's authority, intended use
        and data permissions outside this portal. Record the verification
        reference before approval. Runner authentication is a separate
        enrollment step.
      </p>
      {error && <p role="alert">{error}</p>}
      {loading ? (
        <Loading label="Loading admission decisions" />
      ) : (
        !error && !rows.length && <p>No applications awaiting a decision.</p>
      )}
      {!loading && (
        <p>
          {rows.filter((row) => row.status === "pending").length} pending
          verification ·{" "}
          {rows.filter((row) => row.status === "approved").length} approved ·{" "}
          {rows.filter((row) => row.status === "rejected").length} rejected
        </p>
      )}
      {[...rows]
        .sort(
          (a, b) =>
            Number(b.status === "pending") - Number(a.status === "pending"),
        )
        .map((row) => (
          <article className="hospital-request" key={row.id}>
            <div className="page-heading">
              <h3>{row.organization}</h3>
              <strong>{row.status}</strong>
            </div>
            <p>
              {row.location} · {row.contact_name} · {row.contact_email}
            </p>
            <p>Registration: {row.registration_reference}</p>
            <p>{row.intended_use}</p>
            <small>
              Application {row.id} · Account {row.username}
            </small>
            {row.status === "pending" && (
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  if (busy) return;
                  const data = Object.fromEntries(
                    new FormData(e.currentTarget),
                  );
                  if (
                    !window.confirm(
                      `Record ${data.decision} for ${row.organization}? This decision changes account access.`,
                    )
                  )
                    return;
                  setBusy(true);
                  setError("");
                  try {
                    await rest(
                      `/api/admin/hospital-applications/${row.id}/decision`,
                      "POST",
                      data,
                    );
                    await refresh();
                  } catch (err) {
                    setError((err as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <label>
                  Verification record reference
                  <input
                    name="verification_reference"
                    minLength={10}
                    maxLength={500}
                    required
                  />
                </label>
                <label>
                  Decision
                  <select name="decision">
                    <option value="rejected">Reject application</option>
                    <option value="approved">
                      Approve verified institution
                    </option>
                  </select>
                </label>
                <button disabled={busy}>Record decision</button>
              </form>
            )}
            {row.node_id && (
              <p>
                Assigned node: {row.node_id}. Awaiting secure runner enrollment.
              </p>
            )}
          </article>
        ))}
    </section>
  );
}
