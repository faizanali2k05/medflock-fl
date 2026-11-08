import { useEffect, useState } from "react";
import { HospitalApplications, TransportBinding } from "./Hospitals";
import { rest, gql, DASHBOARD } from "./api";
import type { User } from "./workspaceApi";
import MedGemma from "./ModelRuntime";
export default function Admin({
  tab,
  setTab,
}: {
  tab: string;
  setTab: (value: string) => void;
}) {
  const [users, setUsers] = useState<User[]>([]),
    [data, setData] = useState<any>({ nodes: [], datasets: [], models: [] }),
    [corpora, setCorpora] = useState<any[]>([]),
    [logs, setLogs] = useState<any[]>([]),
    [message, setMessage] = useState(""),
    [preview, setPreview] = useState(""),
    [busy, setBusy] = useState(false);
  async function refresh() {
    const [u, d, c, l] = await Promise.all([
      rest("/api/admin/users"),
      gql(DASHBOARD),
      rest("/api/admin/corpora"),
      rest("/api/audit"),
    ]);
    setUsers(u);
    setData(d);
    setCorpora(c);
    setLogs(l);
  }
  useEffect(() => {
    refresh().catch((e) => setMessage(e.message));
  }, []);
  async function action(fn: () => Promise<any>) {
    setBusy(true);
    setMessage("");
    try {
      await fn();
      await refresh();
      setMessage("Saved.");
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="portal-main">
      <div className="page-heading">
        <div>
          <div className="eyebrow">ADMINISTRATION</div>
          <h1>{tab === "Hospitals" ? "Decisions & exceptions" : tab}</h1>
          <p>
            Manage access, research data and node participation. Host services
            are outside these controls.
          </p>
        </div>
        <button onClick={() => refresh().catch((e) => setMessage(e.message))}>
          Refresh
        </button>
      </div>
      <div className="admin-tabs">
        {[
          "Hospitals",
          "Users",
          "Clients",
          "Corpora",
          "Datasets",
          "Assistant",
          "Audit",
        ].map((t) => (
          <button
            className={tab === t ? "" : "secondary"}
            aria-current={tab === t ? "page" : undefined}
            key={t}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>
      {message && (
        <p role="status" className="notice">
          {message}
        </p>
      )}
      {tab === "Hospitals" && <HospitalApplications />}
      {tab === "Users" && (
        <>
          <form
            className="card form-grid"
            onSubmit={(e) => {
              e.preventDefault();
              const form = e.currentTarget;
              const body: any = Object.fromEntries(new FormData(form));
              if (!body.node_id) body.node_id = null;
              action(async () => {
                await rest("/api/admin/users", "POST", body);
                form.reset();
              });
            }}
          >
            <h2>Create account</h2>
            <label>
              Username
              <input name="username" required pattern="[A-Za-z0-9_.-]{3,64}" />
            </label>
            <label>
              Initial password
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
              Role
              <select name="role">
                <option value="clinician">
                  Care professional — case workspace (preview)
                </option>
                <option value="viewer">Viewer — read-only research</option>
                <option value="researcher">
                  Researcher — experiments and prompts
                </option>
                <option value="client">Client — assigned node only</option>
                <option value="admin">
                  Admin — account and workspace controls
                </option>
              </select>
            </label>
            <label>
              Assigned node (client role)
              <select name="node_id">
                <option value="">None</option>
                {data.nodes
                  .filter((n: any) => n.status !== "removed")
                  .map((n: any) => (
                    <option key={n.id}>{n.id}</option>
                  ))}
              </select>
            </label>
            <button disabled={busy}>Create user</button>
          </form>
          <div className="card table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Role</th>
                  <th>Node</th>
                  <th>Status</th>
                  <th>Sessions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>{u.username}</td>
                    <td>{u.role}</td>
                    <td>{u.node_id || "—"}</td>
                    <td>
                      <button
                        disabled={busy}
                        onClick={() =>
                          action(() =>
                            rest("/api/admin/users/" + u.id, "PATCH", {
                              enabled: !u.enabled,
                            }),
                          )
                        }
                      >
                        {u.enabled ? "Disable" : "Enable"}
                      </button>
                    </td>
                    <td>
                      <button
                        onClick={() =>
                          action(() =>
                            rest(
                              "/api/admin/users/" + u.id + "/sessions",
                              "DELETE",
                            ),
                          )
                        }
                      >
                        Revoke sessions
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {tab === "Clients" && (
        <>
          <TransportBinding nodes={data.nodes} />
          <form
            className="card form-grid"
            onSubmit={(e) => {
              e.preventDefault();
              const f = e.currentTarget;
              const body = Object.fromEntries(new FormData(f));
              action(async () => {
                await rest("/api/admin/nodes", "POST", body);
                f.reset();
              });
            }}
          >
            <h2>Register a client</h2>
            <label>
              Node ID
              <input name="id" pattern="[A-Za-z0-9-]{1,64}" required />
            </label>
            <label>
              Label
              <input name="label" maxLength={120} required />
            </label>
            <button disabled={busy}>Register suspended node</button>
            <p>
              Registration does not launch a worker. Authenticated Flower
              transport enrollment remains separate.
            </p>
          </form>
          <div className="card table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Node</th>
                  <th>Kind</th>
                  <th>Status</th>
                  <th>Access</th>
                </tr>
              </thead>
              <tbody>
                {data.nodes.map((n: any) => (
                  <tr key={n.id}>
                    <td>{n.id}</td>
                    <td>{n.kind}</td>
                    <td>
                      {n.status}
                      {n.details?.suspended_until && (
                        <small>
                          {" "}
                          until{" "}
                          {new Date(n.details.suspended_until).toLocaleString()}
                        </small>
                      )}
                    </td>
                    <td>
                      <select
                        aria-label={`Policy for ${n.id}`}
                        disabled={busy || n.status === "removed"}
                        value={n.status}
                        onChange={(e) =>
                          action(() =>
                            rest(`/api/admin/nodes/${n.id}/policy`, "PATCH", {
                              status: e.target.value,
                            }),
                          )
                        }
                      >
                        <option value="active">Allow participation</option>
                        <option value="paused">Pause training</option>
                        <option value="restricted">
                          Restrict to read-only
                        </option>
                        <option value="suspended">Suspend indefinitely</option>
                        {n.status === "removed" && (
                          <option value="removed">Revoked</option>
                        )}
                      </select>
                      <button
                        disabled={busy || n.status === "removed"}
                        onClick={() =>
                          action(() =>
                            rest(`/api/admin/nodes/${n.id}/policy`, "PATCH", {
                              status: "suspended",
                              duration_minutes: 60,
                            }),
                          )
                        }
                      >
                        Suspend for 1 hour
                      </button>
                      <button
                        disabled={n.status === "removed"}
                        onClick={() => {
                          if (
                            confirm(
                              "Revoke this node and its assigned accounts?",
                            )
                          )
                            action(() =>
                              rest("/api/admin/nodes/" + n.id, "DELETE"),
                            );
                        }}
                      >
                        Remove access
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {tab === "Corpora" && (
        <>
          <section className="card">
            <h2>Teacher corpora</h2>
            <p>
              Upload versioned JSONL or import the bundled 300-case draft set.
              Uploading is not clinical approval and does not start paid
              training.
            </p>
            <button
              disabled={busy}
              onClick={() =>
                action(() => rest("/api/admin/corpora/import-bundled", "POST"))
              }
            >
              Import bundled corpus
            </button>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                action(() => rest("/api/admin/corpora", "POST", f));
              }}
            >
              <label>
                JSONL file (up to 5 MiB)
                <input name="file" type="file" accept=".jsonl" required />
              </label>
              <button disabled={busy}>Upload corpus</button>
            </form>
          </section>
          <section className="card">
            <table>
              <thead>
                <tr>
                  <th>Version</th>
                  <th>Cases</th>
                  <th>Status</th>
                  <th>Inspect</th>
                </tr>
              </thead>
              <tbody>
                {corpora.map((c) => (
                  <tr key={c.sha256}>
                    <td>{c.sha256.slice(0, 12)}</td>
                    <td>{c.cases}</td>
                    <td>{c.status}</td>
                    <td>
                      <button
                        onClick={async () => {
                          try {
                            setPreview(
                              JSON.stringify(
                                await rest("/api/admin/corpora/" + c.sha256),
                                null,
                                2,
                              ),
                            );
                          } catch (e) {
                            setMessage((e as Error).message);
                          }
                        }}
                      >
                        Preview
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {preview && <pre className="response">{preview}</pre>}
          </section>
        </>
      )}
      {tab === "Datasets" && (
        <section className="card">
          <h2>Dataset registry</h2>
          <p>
            Use Model operations → Datasets to upload a CSV and its task
            contract. Removal is blocked when experiments reference a dataset;
            artifacts are retained.
          </p>
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Version</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {data.datasets.map((d: any) => (
                <tr key={d.id}>
                  <td>{d.name}</td>
                  <td>{d.sha256.slice(0, 12)}</td>
                  <td>
                    <button
                      onClick={() => {
                        if (
                          confirm(
                            "Remove this unreferenced dataset from the registry?",
                          )
                        )
                          action(() =>
                            rest("/api/admin/datasets/" + d.id, "DELETE"),
                          );
                      }}
                    >
                      Deregister
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
      {tab === "Assistant" && <MedGemma role="admin" administration />}
      {tab === "Audit" && (
        <section className="card">
          <h2>Application audit — latest 100 events</h2>
          <p>
            Account actions, experiments and inference timing are recorded.
            Prompts, passwords and raw patient data are excluded. Host-wide logs
            are not exposed.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Event</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id}>
                    <td>{l.created_at}</td>
                    <td>{l.kind}</td>
                    <td>
                      <pre>{JSON.stringify(l.details, null, 2)}</pre>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}
