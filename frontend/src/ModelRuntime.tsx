import { useEffect, useState } from "react";
import { rest } from "./api";
import CaseChat from "./CaseChat";
import { workspaceApi, type RuntimeStatus } from "./workspaceApi";
export default function MedGemma({
  role,
  administration = false,
  caseId = "new",
}: {
  role: string;
  administration?: boolean;
  caseId?: string;
}) {
  const [state, setState] = useState<RuntimeStatus | null>(null),
    [error, setError] = useState("");
  async function refresh() {
    setState(await workspaceApi.runtime());
  }
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, []);
  const runtimeDetails = (
    <details className="card">
      <summary>
        Technical details · MedGemma ·{" "}
        {state?.runtime_ready && state?.settings?.enabled
          ? "Available"
          : "Unavailable"}
      </summary>
      <p>
        {state?.settings?.enabled ? "Inference enabled" : "Inference disabled"}{" "}
        · One request at a time · No hourly inference quota
      </p>
      <button onClick={() => refresh().catch((e) => setError(e.message))}>
        Check runtime
      </button>
      <details>
        <summary>Instructions sent with each request</summary>
        <h3>Discuss case</h3>
        <p>{state?.instructions?.chat}</p>
        <h3>Organize case</h3>
        <p>{state?.instructions?.organize}</p>
      </details>
    </details>
  );
  return (
    <main className={`portal-main ${administration ? "" : "chat-page"}`}>
      {administration && (
        <>
          <div className="eyebrow">ADMINISTRATION</div>
          <h1>Assistant administration</h1>
        </>
      )}
      {error && <p className="error">{error}</p>}
      {administration && runtimeDetails}
      {!administration && (
        <CaseChat
          runtimeDetails={runtimeDetails}
          role={role}
          caseId={caseId}
          ready={!!state?.runtime_ready && !!state?.settings?.enabled}
        />
      )}
      {administration && role === "admin" && state && (
        <details className="card">
          <summary>Administrator · inference controls</summary>
          <form
            className="card form-grid"
            key={JSON.stringify(state.settings)}
            onSubmit={async (e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              try {
                await rest("/api/admin/llm/settings", "PUT", {
                  enabled: f.get("enabled") === "on",
                  max_tokens: Number(f.get("max_tokens")),
                  timeout_seconds: Number(f.get("timeout_seconds")),
                });
                await refresh();
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            <h2>Inference limits</h2>
            <label>
              <input
                type="checkbox"
                name="enabled"
                defaultChecked={state.settings.enabled}
              />{" "}
              Enable inference
            </label>
            <label>
              Maximum output tokens
              <input
                type="number"
                name="max_tokens"
                min={32}
                max={4096}
                defaultValue={state.settings.max_tokens}
              />
            </label>
            <label>
              Timeout seconds
              <input
                type="number"
                name="timeout_seconds"
                min={30}
                max={900}
                defaultValue={state.settings.timeout_seconds}
              />
            </label>
            <button>Save limits</button>
          </form>
        </details>
      )}
    </main>
  );
}
