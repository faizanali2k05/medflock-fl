import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  ACTIVATE,
  ACTIVITY,
  CANCEL,
  DASHBOARD,
  DETAIL,
  NODE_STATUS,
  PREDICT,
  START,
  authHeaders,
  gql,
  mergeActivity,
  type Activity,
  type Dashboard,
  type Dataset,
  type Model,
  type Run,
} from "./api";
const FederationGlobe = lazy(() => import("./components/FederationGlobe"));

type Page =
  | "Overview"
  | "Experiments"
  | "Datasets"
  | "Fleet"
  | "Models"
  | "Model lab"
  | "API explorer";
const empty: Dashboard = {
  runs: [],
  datasets: [],
  models: [],
  nodes: [],
  activityCursor: 0,
};
const defaults = {
  dataset_id: "default",
  family: "logistic",
  clients: 3,
  rounds: 60,
  local_epochs: 5,
  learning_rate: 0.15,
  l2: 0.01,
  seed: 42,
  partition: "iid",
  aggregation: "fedavg",
  attack: "none",
  defense: "none",
  clip_norm: 1,
  patience: 12,
};
const format = (value: number | null | undefined) =>
  value == null ? "—" : value.toFixed(3);
function download(name: string, content: string) {
  const link = document.createElement("a"),
    url = URL.createObjectURL(
      new Blob([content], { type: "application/json" }),
    );
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

export default function App({
  page,
  setPage,
  paused = false,
  readOnly = false,
}: {
  page: Page;
  setPage: (page: Page) => void;
  paused?: boolean;
  readOnly?: boolean;
}) {
  const [data, setData] = useState<Dashboard>(empty);
  const [events, setEvents] = useState<Activity[]>([]),
    [error, setError] = useState(""),
    [connected, setConnected] = useState(false);
  const [selected, setSelected] = useState<string | null>(null),
    [detail, setDetail] = useState<Run | null>(null),
    [busy, setBusy] = useState(false);
  const cursor = useRef<number | null>(null),
    refreshing = useRef(false);
  const refresh = useCallback(async () => {
    if (refreshing.current) return;
    refreshing.current = true;
    try {
      const state = await gql<Dashboard>(DASHBOARD);
      setData(state);
      setConnected(true);
      if (cursor.current === null) cursor.current = state.activityCursor;
      const batch = await gql<{ activity: Activity[] }>(ACTIVITY, {
        after: cursor.current,
      });
      if (batch.activity.length) {
        cursor.current = batch.activity.at(-1)!.sequence;
        setEvents((previous) => mergeActivity(previous, batch.activity, 500));
      }
    } catch (e) {
      setConnected(false);
      setError((e as Error).message);
    } finally {
      refreshing.current = false;
    }
  }, []);
  useEffect(() => {
    if (paused) return;
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, [refresh, paused]);
  useEffect(() => {
    if (!selected) return;
    let disposed = false;
    gql<{ run: Run }>(DETAIL, { id: selected })
      .then((value) => {
        if (!disposed) setDetail(value.run);
      })
      .catch((e) => setError(e.message));
    return () => {
      disposed = true;
    };
  }, [selected, data.runs]);
  async function action(operation: () => Promise<unknown>) {
    if (readOnly) {
      setError("Your account has read-only research access.");
      return;
    }
    setError("");
    setBusy(true);
    try {
      await operation();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function start(config: Record<string, unknown>) {
    await action(async () => {
      const result = await gql(START, { config, key: crypto.randomUUID() });
      setSelected(result.startRun.id);
      setPage("Experiments");
    });
  }
  const completed = data.runs.filter(
    (run) => run.status === "completed",
  ).length;
  const current = data.runs.find((run) => run.status === "running");
  return (
    <div className="research-workspace">
      <main>
        <p className="research-connection" role="status">
          {connected
            ? "Research API connected"
            : "Research API unavailable or connecting"}{" "}
          · Tabular simulations
        </p>

        <div className="page-heading">
          <div>
            <div className="eyebrow">FEDERATED LEARNING PLATFORM</div>
            <h1>
              {page === "Overview"
                ? "A shared model. A visible process."
                : page}
            </h1>
            <p>
              {
                {
                  Overview:
                    "Follow contributions, explore experiments, and test model candidates.",
                  Experiments:
                    "Configure training, inspect validation, and compare the same held-out split.",
                  Datasets:
                    "Register versioned research data and declare what each column means.",
                  Fleet:
                    "Inspect simulated clients and control participation in upcoming rounds.",
                  Models:
                    "Compare model candidates and choose a research version to activate.",
                  "Model lab":
                    "Test a candidate with a synthetic case or your own permitted research inputs.",
                  "API explorer":
                    "Run field-specific GraphQL queries and inspect the live response.",
                  Access: "Configure access for this browser session.",
                }[page]
              }
            </p>
          </div>
          {page === "Overview" && (
            <button
              disabled={readOnly || busy || !data.datasets.length}
              onClick={() => start(defaults)}
            >
              ＋ New experiment
            </button>
          )}
        </div>
        {error && (
          <div className="error" role="alert">
            <span>{error}</span>
            <button className="quiet" onClick={() => setError("")}>
              Dismiss
            </button>
          </div>
        )}
        {page === "Overview" && (
          <>
            <section className="hero">
              <div className="hero-copy">
                <span className="dark-pill">
                  <i className="dot" /> LIVE FEDERATION ACTIVITY
                </span>
                <h2>
                  Watch updates
                  <br />
                  become a model.
                </h2>
                <p>
                  Every arriving pulse represents an accepted weight
                  contribution recorded by the training worker.
                </p>
                <div className="hero-stats">
                  <div>
                    <strong>{data.nodes.length}</strong>
                    <span>Registered clients</span>
                  </div>
                  <div>
                    <strong>{data.models.length}</strong>
                    <span>Model versions</span>
                  </div>
                  <div>
                    <strong>{current ? "Training" : "Idle"}</strong>
                    <span>Recorded run activity</span>
                  </div>
                </div>
                <span className="hero-note">
                  Current experiments use simulated partitions of research data.
                </span>
              </div>
              <Suspense fallback={<div>Loading federation view...</div>}>
                <FederationGlobe
                  events={events}
                  nodes={data.nodes.length}
                  completed={completed}
                />
              </Suspense>
            </section>
            <div className="stats-grid">
              <Stat
                label="Available datasets"
                value={data.datasets.length}
                hint="Versioned, schema-checked sources"
              />
              <Stat
                label="Completed experiments"
                value={completed}
                hint="With reproducible split metadata"
              />
              <Stat
                label="Active experiments"
                value={
                  data.runs.filter((r) =>
                    ["queued", "running"].includes(r.status),
                  ).length
                }
                hint="Durable queue and cancellation"
              />
              <Stat
                label="Current model"
                value={
                  data.models.some((m) => m.status === "active_research")
                    ? "Activated"
                    : "Unselected"
                }
                hint="Research activation only"
              />
            </div>
            <div className="two-col">
              <section className="card">
                <Section
                  title="Recent experiments"
                  action={
                    <button
                      className="quiet"
                      onClick={() => setPage("Experiments")}
                    >
                      View all ↗
                    </button>
                  }
                />
                <RunList
                  runs={data.runs.slice(0, 5)}
                  select={(id) => {
                    setSelected(id);
                    setPage("Experiments");
                  }}
                />
              </section>
              <section className="card">
                <Section
                  title="Live activity"
                  action={
                    <span className="pill">
                      EVENT CURSOR {cursor.current ?? 0}
                    </span>
                  }
                />
                <ActivityFeed events={events} />
              </section>
            </div>
          </>
        )}
        {page === "Experiments" && (
          <>
            <div className="training-grid">
              <section className="card">
                <Section title="Training configuration" />
                <TrainingForm
                  datasets={data.datasets}
                  models={data.models}
                  busy={busy || readOnly}
                  onStart={start}
                />
              </section>
              <section className="card">
                <Section
                  title="Experiment detail"
                  action={
                    detail && ["queued", "running"].includes(detail.status) ? (
                      <button
                        className="danger"
                        onClick={() =>
                          action(() => gql(CANCEL, { id: detail.id }))
                        }
                      >
                        Cancel run
                      </button>
                    ) : null
                  }
                />
                {detail ? (
                  <RunDetail run={detail} />
                ) : (
                  <Empty
                    title="Choose an experiment"
                    text="Start a training job or select one from history to inspect its result."
                  />
                )}
              </section>
            </div>
            <section className="card">
              <Section title="Experiment history" />
              <RunList runs={data.runs} select={setSelected} />
            </section>
          </>
        )}
        {page === "Datasets" && (
          <DatasetsView
            datasets={data.datasets}
            readOnly={readOnly}
            onImported={refresh}
            onError={setError}
          />
        )}
        {page === "Fleet" && (
          <>
            <section className="card">
              <Section
                title="Client registry"
                action={<span className="pill">SIMULATED CLIENTS</span>}
              />
              {data.nodes.length ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Client</th>
                        <th>Status</th>
                        <th>Last contribution</th>
                        <th>Sample count</th>
                        <th>Update norm</th>
                        <th>Participation</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.nodes.map((node) => (
                        <tr key={node.id}>
                          <td>
                            <strong>{node.label}</strong>
                            <small>{node.id}</small>
                          </td>
                          <td>
                            <Status status={node.status} />
                          </td>
                          <td>
                            {node.lastSeen
                              ? new Date(node.lastSeen).toLocaleTimeString()
                              : "Awaiting update"}
                          </td>
                          <td>{node.details?.count ?? "—"}</td>
                          <td>{format(node.details?.norm)}</td>
                          <td>
                            <button
                              className="secondary"
                              onClick={() =>
                                action(() =>
                                  gql(NODE_STATUS, {
                                    id: node.id,
                                    status:
                                      node.status === "active"
                                        ? "suspended"
                                        : "active",
                                  }),
                                )
                              }
                            >
                              {node.status === "active" ? "Suspend" : "Resume"}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Empty
                  title="No clients assigned yet"
                  text="Start an experiment to register its simulated client partitions."
                />
              )}
              <p className="caption">
                Suspension is checked before each local update. A round fails if
                too few clients remain. These registry entries do not represent
                connected hospitals.
              </p>
            </section>
            <section className="card">
              <Section title="Contribution stream" />
              <ActivityFeed
                events={events.filter((event) =>
                  event.kind.startsWith("contribution"),
                )}
              />
            </section>
          </>
        )}
        {page === "Models" && (
          <ModelsView
            readOnly={readOnly}
            models={data.models}
            onActivate={(id, reason) =>
              action(() => gql(ACTIVATE, { id, reason }))
            }
            onInspect={(id) => {
              setSelected(id);
              setPage("Experiments");
            }}
          />
        )}
        {page === "Model lab" && (
          <Inference models={data.models} onError={setError} />
        )}
        {page === "API explorer" && <Explorer />}
      </main>
      <footer>
        MedFlock · Federated learning research · Experimental scores, not
        clinical decisions
      </footer>
    </div>
  );
}

function Section({
  title,
  action,
}: {
  title: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="section-heading">
      <h3>{title}</h3>
      {action}
    </div>
  );
}
function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number;
  hint: string;
}) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{hint}</small>
    </div>
  );
}
function Empty({ title, text }: { title: string; text: string }) {
  return (
    <div className="empty">
      <span>◇</span>
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
function Status({ status }: { status: string }) {
  return (
    <span className={`status ${status}`}>{status.replaceAll("_", " ")}</span>
  );
}
function RunList({
  runs,
  select,
}: {
  runs: Run[];
  select: (id: string) => void;
}) {
  return runs.length ? (
    <div className="run-list">
      {runs.map((run) => (
        <button className="run-row" key={run.id} onClick={() => select(run.id)}>
          <span className="run-icon">⌁</span>
          <div>
            <strong>
              {run.config.family ?? "Legacy logistic"} · {run.config.clients}{" "}
              clients
            </strong>
            <small>
              {run.config.partition.replaceAll("_", " ")} ·{" "}
              {new Date(run.createdAt).toLocaleString()}
            </small>
          </div>
          <Status status={run.status} />
          <span>↗</span>
        </button>
      ))}
    </div>
  ) : (
    <Empty
      title="Your first experiment starts here"
      text="Choose a dataset and training configuration to create a reproducible run."
    />
  );
}
function ActivityFeed({ events }: { events: Activity[] }) {
  return events.length ? (
    <div className="activity-feed">
      {events
        .slice(-30)
        .reverse()
        .map((event) => (
          <div className="activity-row" key={event.sequence}>
            <i
              className={
                event.kind.includes("failed") ? "event-dot failed" : "event-dot"
              }
            />
            <div>
              <strong>{event.kind.replaceAll(".", " · ")}</strong>
              <small>
                {event.details.node_id ??
                  event.details.run_id?.slice(0, 8) ??
                  "workspace"}
                {event.details.round ? ` · round ${event.details.round}` : ""}
                {event.details.clipped ? " · clipped" : ""}
              </small>
            </div>
            <time>{new Date(event.createdAt).toLocaleTimeString()}</time>
          </div>
        ))}
    </div>
  ) : (
    <Empty
      title="Listening for updates"
      text="New training contributions and workspace actions will appear here."
    />
  );
}

function TrainingForm({
  datasets,
  models,
  busy,
  onStart,
}: {
  datasets: Dataset[];
  models: Model[];
  busy: boolean;
  onStart: (config: any) => void;
}) {
  const [config, setConfig] = useState<Record<string, any>>(defaults);
  const set = (key: string, value: any) =>
    setConfig((previous) => ({ ...previous, [key]: value }));
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onStart(config);
      }}
    >
      <label>
        Dataset
        <select
          value={config.dataset_id}
          onChange={(e) => set("dataset_id", e.target.value)}
        >
          <option value="default">Default cardiology dataset</option>
          {datasets.map((dataset) => (
            <option key={dataset.id} value={dataset.id}>
              {dataset.name}
            </option>
          ))}
        </select>
      </label>
      <div className="form-grid">
        <label>
          Model family
          <select
            value={config.family}
            onChange={(e) => set("family", e.target.value)}
          >
            <option value="logistic">Logistic regression</option>
            <option value="mlp">Neural network · MLP</option>
          </select>
        </label>
        <label>
          Clients
          <input
            type="number"
            min="2"
            max="20"
            value={config.clients}
            onChange={(e) => set("clients", Number(e.target.value))}
          />
        </label>
        <label>
          Maximum rounds
          <input
            type="number"
            min="1"
            max="500"
            value={config.rounds}
            onChange={(e) => set("rounds", Number(e.target.value))}
          />
        </label>
        <label>
          Local epochs
          <input
            type="number"
            min="1"
            max="100"
            value={config.local_epochs}
            onChange={(e) => set("local_epochs", Number(e.target.value))}
          />
        </label>
        <label>
          Learning rate
          <input
            type="number"
            min=".001"
            max="1"
            step=".001"
            value={config.learning_rate}
            onChange={(e) => set("learning_rate", Number(e.target.value))}
          />
        </label>
        <label>
          Random seed
          <input
            type="number"
            min="0"
            value={config.seed}
            onChange={(e) => set("seed", Number(e.target.value))}
          />
        </label>
      </div>
      <label>
        Partition strategy
        <select
          value={config.partition}
          onChange={(e) => set("partition", e.target.value)}
        >
          <option value="iid">IID · random assignment</option>
          <option value="label_skew">Non-IID · outcome skew</option>
          <option value="feature_skew">Non-IID · first-feature skew</option>
        </select>
      </label>
      <label>
        Aggregation
        <select
          value={config.aggregation}
          onChange={(e) => set("aggregation", e.target.value)}
        >
          <option value="fedavg">Flower FedAvg</option>
          <option value="median">Coordinate median</option>
          <option value="trimmed_mean">Trimmed mean</option>
        </select>
      </label>
      <details>
        <summary>Stress testing & continuation</summary>
        <label>
          Attack
          <select
            value={config.attack}
            onChange={(e) => set("attack", e.target.value)}
          >
            <option value="none">No attacker</option>
            <option value="sign_flip">One sign-flipping client</option>
          </select>
        </label>
        <label>
          Defense
          <select
            value={config.defense}
            onChange={(e) => set("defense", e.target.value)}
          >
            <option value="none">No clipping</option>
            <option value="clip">Clip update norm</option>
          </select>
        </label>
        <label>
          Warm-start parent
          <select
            value={config.parent_model ?? ""}
            onChange={(e) => set("parent_model", e.target.value || null)}
          >
            <option value="">Train from initialization</option>
            {models
              .filter((model) => model.manifest.format_version === 2)
              .map((model) => (
                <option key={model.id} value={model.id}>
                  {model.manifest.family} · {model.id.slice(0, 10)}
                </option>
              ))}
          </select>
        </label>
        <p className="caption">
          Robust-aggregation and attack experiments require at least five
          clients. A parent must match the task and architecture; its
          preprocessing is retained.
        </p>
      </details>
      <button className="full" disabled={busy || !datasets.length}>
        {busy ? "Submitting…" : "Start training →"}
      </button>
      <p className="caption">
        60% train · 20% validation · 20% test. Validation selects the candidate.
        The test split is evaluated after training.
      </p>
    </form>
  );
}

function RunDetail({ run }: { run: Run }) {
  const result = run.result;
  if (!result)
    return (
      <div>
        <Status status={run.status} />
        <p>
          {run.error ??
            "The worker will publish the result when training completes. Contributions appear in the live activity view."}
        </p>
        <code>{run.id}</code>
      </div>
    );
  const history = result.history ?? [],
    values = history.map(
      (row: any) => row.validation?.brier ?? row.train_brier,
    );
  const low = Math.min(...values) * 0.9,
    high = Math.max(...values) * 1.1,
    range = Math.max(high - low, 0.01);
  return (
    <div>
      <div className="result-top">
        <Status status={run.status} />
        <button
          className="quiet"
          onClick={() =>
            download(`medflock-${run.id}.json`, JSON.stringify(result, null, 2))
          }
        >
          Export JSON ↓
        </button>
      </div>
      <div className="result-stats">
        <Stat
          label="Federated AUROC"
          value={format(result.fedavg?.auroc)}
          hint="Held-out test split"
        />
        <Stat
          label="Selected round"
          value={result.selected_round ?? history.length}
          hint="Minimum validation Brier"
        />
        <Stat
          label="Eligible records"
          value={result.cohort.eligible_rows}
          hint={`${result.cohort.test_count} test records`}
        />
      </div>
      <h4>Paired baseline comparison</h4>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Approach</th>
              <th>AUROC ↑</th>
              <th>Avg. precision ↑</th>
              <th>Brier ↓</th>
            </tr>
          </thead>
          <tbody>
            {[
              ["Centralized", result.centralized],
              ["Federated", result.fedavg],
              ...result.local_only.map((value: any, index: number) => [
                `Local ${index + 1}`,
                value,
              ]),
            ].map(([name, value]: any) => (
              <tr key={name}>
                <td>{name}</td>
                <td>{format(value.auroc)}</td>
                <td>{format(value.auprc)}</td>
                <td>{format(value.brier)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h4>Validation Brier by round</h4>
      <svg
        className="line-chart"
        viewBox="0 0 600 150"
        role="img"
        aria-label="Validation Brier by round"
      >
        <line x1="30" y1="120" x2="580" y2="120" stroke="var(--color-line)" />
        <polyline
          fill="none"
          stroke="var(--color-primary)"
          strokeWidth="3"
          points={values
            .map(
              (value: number, index: number) =>
                `${30 + (index / Math.max(1, values.length - 1)) * 550},${120 - ((value - low) / range) * 95}`,
            )
            .join(" ")}
        />
        <text x="30" y="145">
          Round 1
        </text>
        <text x="500" y="145">
          Round {history.length}
        </text>
        <text x="30" y="15">
          Range {low.toFixed(3)} – {high.toFixed(3)}
        </text>
      </svg>
      <p className="caption">{result.limitations?.join(". ")}.</p>
      <code className="fingerprint">
        Contract {result.contract_hash}
        <br />
        Split {result.split_hash}
      </code>
    </div>
  );
}

function DatasetsView({
  readOnly = false,
  datasets,
  onImported,
  onError,
}: {
  readOnly?: boolean;
  datasets: Dataset[];
  onImported: () => void;
  onError: (message: string) => void;
}) {
  const [contract, setContract] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    gql("{defaultContract}")
      .then((data) =>
        setContract(JSON.stringify(data.defaultContract, null, 2)),
      )
      .catch((e) => onError(e.message));
  }, []);
  async function upload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (readOnly || busy) return;
    setBusy(true);
    onError("");
    try {
      JSON.parse(contract);
      const form = new FormData(e.currentTarget);
      form.set("contract", contract);
      const response = await fetch("/api/datasets", {
        method: "POST",
        headers: authHeaders(),
        body: form,
      });
      const body = await response.json();
      if (!response.ok)
        throw Error(
          typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail),
        );
      onImported();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="two-col">
      <section className="card">
        <Section title="Dataset registry" />
        {datasets.map((dataset) => (
          <article className="dataset-card" key={dataset.id}>
            <span className="dataset-icon">▤</span>
            <h4>{dataset.name}</h4>
            <div className="mini-stats">
              <span>
                <b>{dataset.profile.eligible_rows}</b> records
              </span>
              <span>
                <b>{dataset.profile.features}</b> features
              </span>
              <span>
                <b>{dataset.profile.missing_values}</b> missing
              </span>
            </div>
            <p>
              {dataset.provenance.source} · {dataset.provenance.permission}
            </p>
            <code>{dataset.sha256.slice(0, 24)}…</code>
            <details>
              <summary>Inspect contract</summary>
              <pre>{JSON.stringify(dataset.contract, null, 2)}</pre>
            </details>
          </article>
        ))}
      </section>
      <section className="card">
        <Section title="Import research CSV" />
        <p className="caption">
          Declare source permission and feature semantics. New tasks can use a
          binary label or a follow-up horizon. This upload path stores the
          research dataset on the coordinator.
        </p>
        <form onSubmit={upload}>
          <label>
            Dataset name
            <input
              name="name"
              required
              maxLength={120}
              placeholder="Cardiology cohort · revision 2"
            />
          </label>
          <label>
            CSV file
            <input name="file" type="file" accept=".csv" required />
          </label>
          <div className="form-grid">
            <label>
              Source
              <input
                name="source"
                required
                placeholder="Repository DOI or collection"
              />
            </label>
            <label>
              Permission
              <input
                name="permission"
                required
                placeholder="License or approved research scope"
              />
            </label>
          </div>
          <label>
            Task contract
            <textarea
              className="code-input"
              value={contract}
              onChange={(e) => setContract(e.target.value)}
              rows={15}
              spellCheck={false}
            />
          </label>
          <p className="caption">
            Keep the same task ID/version and feature meanings for compatible
            data revisions. Set group_column when patient IDs exist to keep each
            patient in one split.
          </p>
          <button disabled={busy || readOnly}>
            {busy ? "Validating…" : "Validate & register dataset"}
          </button>
        </form>
      </section>
    </div>
  );
}

function ModelsView({
  readOnly = false,
  models,
  onActivate,
  onInspect,
}: {
  readOnly?: boolean;
  models: Model[];
  onActivate: (id: string, reason: string) => void;
  onInspect: (id: string) => void;
}) {
  const [candidate, setCandidate] = useState<string | null>(null),
    [reason, setReason] = useState("");
  return (
    <section className="card">
      <Section title="Model versions" />
      {models.length ? (
        <div className="model-grid">
          {models.map((model) => (
            <article className="model-card" key={model.id}>
              <div className="result-top">
                <span className="model-icon">⬡</span>
                <Status status={model.status} />
              </div>
              <h3>{model.manifest.family ?? "Legacy logistic"}</h3>
              <p>
                {model.manifest.contract?.id ?? "heart-failure-90d"}
                <br />
                <code>{model.id.slice(0, 16)}</code>
              </p>
              <div className="mini-stats">
                <span>
                  Round <b>{model.manifest.selected_round ?? "—"}</b>
                </span>
                <span>
                  <b>{model.manifest.parameters ?? 12}</b> parameters
                </span>
              </div>
              <small>
                Parent:{" "}
                {model.manifest.parent_model?.slice(0, 12) ??
                  "Fresh initialization"}
              </small>
              <div className="button-row">
                <button
                  className="secondary"
                  onClick={() => onInspect(model.runId)}
                >
                  View evaluation
                </button>
                {model.manifest.format_version === 2 && (
                  <button
                    className="quiet"
                    disabled={readOnly}
                    onClick={() => setCandidate(model.id)}
                  >
                    Activate
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <Empty
          title="No candidates yet"
          text="A completed training run registers a checksummed model artifact here."
        />
      )}
      {candidate && (
        <form
          className="activation"
          onSubmit={(e) => {
            e.preventDefault();
            onActivate(candidate, reason);
            setCandidate(null);
          }}
        >
          <h4>Activate for research use</h4>
          <p>
            This changes the active research candidate. It does not create a
            clinical approval.
          </p>
          <label>
            Reason
            <textarea
              required
              minLength={8}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Record the evidence behind this selection"
            />
          </label>
          <div className="button-row">
            <button>Confirm activation</button>
            <button
              type="button"
              className="secondary"
              onClick={() => setCandidate(null)}
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

function Inference({
  models,
  onError,
}: {
  models: Model[];
  onError: (message: string) => void;
}) {
  const available = models.filter(
      (model) => model.manifest.format_version === 2,
    ),
    [id, setId] = useState(""),
    [values, setValues] = useState<Record<string, string>>({}),
    [result, setResult] = useState<any>(null),
    [busy, setBusy] = useState(false);
  const model =
    available.find((model) => model.id === id) ??
    available.find((model) => model.status === "active_research") ??
    available[0];
  const features = model?.manifest.contract.features ?? [];
  const synthetic: Record<string, number> = {
    age: 60,
    anaemia: 0,
    creatinine_phosphokinase: 180,
    diabetes: 0,
    ejection_fraction: 38,
    high_blood_pressure: 1,
    platelets: 250000,
    serum_creatinine: 1.1,
    serum_sodium: 138,
    sex: 1,
    smoking: 0,
  };
  if (!model)
    return (
      <section className="card">
        <Empty
          title="Train a candidate first"
          text="The model lab builds its input form from the selected model's saved feature contract."
        />
      </section>
    );
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    onError("");
    try {
      const inputs = Object.fromEntries(
        features.map((feature: any) => [
          feature.name,
          values[feature.name]?.trim() ? Number(values[feature.name]) : null,
        ]),
      );
      const response = await gql(PREDICT, { id: model.id, features: inputs });
      setResult(response.predict);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="two-col">
      <section className="card">
        <Section title="Tabular prediction inputs" />
        <p>
          For a case in your own words, open Case workspace in the top bar.
          MedGemma can organize facts and ask follow-up questions. This separate
          prediction model requires the features it was trained on; review
          extracted values before entering them here.
        </p>
        <label>
          Model version
          <select
            value={model.id}
            onChange={(e) => {
              setId(e.target.value);
              setValues({});
              setResult(null);
            }}
          >
            {available.map((candidate) => (
              <option key={candidate.id} value={candidate.id}>
                {candidate.manifest.family} · {candidate.id.slice(0, 10)}
              </option>
            ))}
          </select>
        </label>
        <button
          className="secondary"
          onClick={() =>
            setValues(
              Object.fromEntries(
                features.map((feature: any) => [
                  feature.name,
                  String(
                    synthetic[feature.name] ??
                      (feature.kind === "binary" ? 0 : (feature.minimum ?? 1)),
                  ),
                ]),
              ),
            )
          }
        >
          Load synthetic example
        </button>
        <form onSubmit={submit}>
          <div className="form-grid">
            {features.map((feature: any) => (
              <label key={feature.name}>
                {feature.name.replaceAll("_", " ")}
                <input
                  type="number"
                  step="any"
                  value={values[feature.name] ?? ""}
                  onChange={(e) =>
                    setValues((previous) => ({
                      ...previous,
                      [feature.name]: e.target.value,
                    }))
                  }
                  placeholder="Missing → training median"
                />
                <small>{feature.unit}</small>
              </label>
            ))}
          </div>
          <button disabled={busy}>
            {busy ? "Evaluating…" : "Evaluate case →"}
          </button>
        </form>
      </section>
      <section className="card">
        <Section title="Model output" />
        {result ? (
          <>
            <span className="pill">EXPERIMENTAL OUTPUT</span>
            <div className="score">
              {(result.score * 100).toFixed(1)}
              <span>/ 100</span>
            </div>
            <h3>Uncalibrated outcome score</h3>
            <p>{result.interpretation}</p>
            <div className="notice">
              This is not a validated individual clinical risk estimate.
              Medication:{" "}
              <strong>{result.medication_status.replaceAll("_", " ")}</strong>.
            </div>
            <p>
              Imputed fields:{" "}
              {result.imputed_features.length
                ? result.imputed_features.join(", ")
                : "None"}
            </p>
            <button
              className="secondary"
              onClick={() =>
                download(
                  "research-inference.json",
                  JSON.stringify(result, null, 2),
                )
              }
            >
              Export output
            </button>
          </>
        ) : (
          <Empty
            title="Inspect the model's behavior"
            text="Use the clearly synthetic example or enter permitted research values. Missing fields use the candidate's saved training medians."
          />
        )}
      </section>
    </div>
  );
}

function Explorer() {
  const [query, setQuery] = useState(
      "query {\n  nodes { id status lastSeen }\n  runs(limit: 5) { id status config }\n}",
    ),
    [output, setOutput] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <div className="two-col">
      <section className="card">
        <Section title="GraphQL operation" />
        <textarea
          rows={19}
          aria-label="GraphQL operation"
          className="code-input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          spellCheck={false}
        />
        <button
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              setOutput(JSON.stringify(await gql(query), null, 2));
            } catch (e) {
              setOutput((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          Execute query →
        </button>
        <p className="caption">
          Queries: runs, datasets, nodes, models, activity. Mutations: startRun,
          cancelRun, setNodeStatus, activateModel, predict. Operator permissions
          apply to administrative actions.
        </p>
      </section>
      <section className="card">
        <Section title="Response" />
        <pre className="response">
          {output || "Execute an operation to inspect its response."}
        </pre>
      </section>
    </div>
  );
}
