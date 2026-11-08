import { useEffect, useRef, useState } from "react";
import App from "./App";
import PasswordInput from "./components/PasswordInput";
import Admin from "./Admin";
import Account from "./Account";
import CaseLibrary from "./CaseLibrary";
import ModelRuntime from "./ModelRuntime";
import { HospitalApplication, HospitalWorkspace } from "./Hospitals";
import { EvolutionLab, Help } from "./CapabilityPages";
import WorkspaceShell from "./components/WorkspaceShell";
import { Alert, EmptyState, Loading } from "./components/ui";
import { rest, setCsrf } from "./api";
import { workspaceApi, type User } from "./workspaceApi";
import {
  adminPages,
  allowedRoute,
  canLeave,
  landing,
  navigate,
  researchPages,
  segment,
  useRoute,
} from "./navigation";

export default function Portal() {
  const [user, setUser] = useState<User | null>(null),
    [ready, setReady] = useState(false);
  const [locked, setLocked] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const knownUser = useRef<User | null>(null);
  const path = useRoute();
  function accept(value: { user: User; csrf: string }) {
    const sameUser = knownUser.current?.id === value.user.id;
    knownUser.current = value.user;
    setUser(value.user);
    setCsrf(value.csrf);
    setLocked(false);
    if ((!sameUser && !allowedRoute(path, value.user.role)) || path === "/")
      navigate(landing(value.user.role), true, false);
  }
  useEffect(() => {
    let mounted = true;
    workspaceApi
      .session()
      .then((value) => {
        if (mounted) accept(value);
      })
      .catch(() => {})
      .finally(() => {
        if (mounted) setReady(true);
      });
    const expired = () => {
      if (knownUser.current) {
        setLocked(true);
        setError(
          "Your session expired. Sign in again to continue. Unsaved case text stays in this tab while you sign in to the same account.",
        );
      }
      setCsrf("");
    };
    window.addEventListener("medflock-expired", expired);
    return () => {
      mounted = false;
      window.removeEventListener("medflock-expired", expired);
    };
  }, []);
  async function login(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      accept(
        await rest(
          "/api/auth/login",
          "POST",
          Object.fromEntries(new FormData(e.currentTarget)),
        ),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function logout() {
    if (!canLeave()) return;
    try {
      await rest("/api/auth/logout", "POST");
      knownUser.current = null;
      setUser(null);
      setCsrf("");
      setError("");
      navigate("/", true, false);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  if (!ready)
    return (
      <main>
        <Loading label="Checking your session" />
      </main>
    );
  if (!user && path === "/apply")
    return <HospitalApplication close={() => navigate("/")} />;
  const loginView = (
    <div className="login-screen">
      <section className="login-story">
        <div className="workspace-brand">
          <span className="brand-symbol">m</span>medflock
        </div>
        <span className="eyebrow">A CONNECTED APPROACH TO CARE</span>
        <h1>
          More understanding.
          <br />
          One case at a time.
        </h1>
        <p>
          Your space to organize complex cases, ask better questions and learn
          together.
        </p>
        <div className="login-principles">
          <div>
            <strong>01</strong>
            <span>Describe naturally</span>
          </div>
          <div>
            <strong>02</strong>
            <span>Review the facts</span>
          </div>
          <div>
            <strong>03</strong>
            <span>Discuss with context</span>
          </div>
        </div>
        <small>
          Research beta · Synthetic cases only · Clinical review required
        </small>
      </section>
      <form className="login-card" onSubmit={login}>
        <div className="eyebrow">YOUR SECURE WORKSPACE</div>
        <h2>{locked ? "Continue your session" : "Welcome back"}</h2>
        <p>Sign in to the workspace assigned to your role.</p>
        <label>
          Username
          <input
            name="username"
            autoComplete="username"
            required
            maxLength={64}
          />
        </label>
        <label>
          Password
          <PasswordInput
            name="password"
            type="password"
            autoComplete="current-password"
            required
            maxLength={128}
          />
        </label>
        {error && <Alert error>{error}</Alert>}
        <button disabled={busy}>{busy ? "Signing in…" : "Sign in →"}</button>
        {!locked && (
          <button
            type="button"
            className="secondary"
            onClick={() => navigate("/apply")}
          >
            Request hospital access
          </button>
        )}
        <small>
          Sessions expire after 30 minutes idle or 8 hours total. For account
          recovery, contact your administrator.
        </small>
      </form>
    </div>
  );
  return (
    <>
      {(!user || locked) && loginView}
      {user && (
        <div hidden={locked} inert={locked} key={user.id}>
          <WorkspaceShell user={user} path={path} logout={logout}>
            {error && !locked && <Alert error>{error}</Alert>}
            {!allowedRoute(path, user.role) ? (
              <main>
                <EmptyState
                  title="This page is not in your workspace"
                  action={
                    <button onClick={() => navigate(landing(user.role))}>
                      Open my workspace
                    </button>
                  }
                >
                  Use the navigation for the tools available to your account.
                  Access is always checked by the server.
                </EmptyState>
              </main>
            ) : path === "/cases" ? (
              <CaseLibrary />
            ) : path.startsWith("/cases/") ? (
              <ModelRuntime role={user.role} caseId={path.split("/")[2]} />
            ) : path === "/institution" ? (
              <HospitalWorkspace />
            ) : path.startsWith("/admin/") ? (
              <Admin
                tab={adminPages.find((p) => path === `/admin/${segment(p)}`)!}
                setTab={(p) => navigate(`/admin/${segment(p)}`)}
              />
            ) : path.startsWith("/research/") ? (
              <App
                page={
                  researchPages.find((p) => path === `/research/${segment(p)}`)!
                }
                setPage={(p) => navigate(`/research/${segment(p)}`)}
                paused={locked}
                readOnly={user.role === "viewer"}
              />
            ) : path === "/evolution" ? (
              <EvolutionLab />
            ) : path === "/account" ? (
              <Account />
            ) : (
              <Help />
            )}
          </WorkspaceShell>
        </div>
      )}
    </>
  );
}
