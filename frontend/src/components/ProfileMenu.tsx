import { useEffect, useState } from "react";
import { rest } from "../api";
import { navigate } from "../navigation";
import type { User } from "../workspaceApi";
import { loadPreferences, defaults, avatarSymbols } from "../preferences";
export default function ProfileMenu({
  user,
  logout,
}: {
  user: User;
  logout: () => void;
}) {
  const [profile, setProfile] = useState(defaults),
    [items, setItems] = useState<
      { id: string; title: string; created_at: string; read: boolean }[]
    >([]),
    [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    const load = () =>
      loadPreferences()
        .then((p) => {
          if (alive) setProfile(p);
        })
        .catch(() => {});
    load();
    window.addEventListener("medflock-profile", load);
    const media = window.matchMedia?.("(prefers-color-scheme: dark)");
    media?.addEventListener?.("change", load);
    return () => {
      alive = false;
      window.removeEventListener("medflock-profile", load);
      media?.removeEventListener?.("change", load);
    };
  }, [user.id]);
  useEffect(() => {
    let alive = true;
    const refresh = async () => {
      if (document.hidden || document.querySelector("[inert]")) return;
      try {
        const result = await rest("/api/workspace/notifications");
        if (alive) {
          setItems(Array.isArray(result.items) ? result.items : []);
          setError("");
        }
      } catch {
        if (alive) setError("Notifications could not be refreshed.");
      }
    };
    refresh();
    const timer = setInterval(refresh, 15000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [user.id]);
  const count = items.filter((i) => !i.read).length;
  return (
    <div className="topbar-tools">
      <details className="notification-menu">
        <summary
          aria-label={`Notifications${count ? `, ${count} unread` : ""}`}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M5 17h14l-2-3V9a5 5 0 0 0-10 0v5l-2 3Zm5 3h4" />
          </svg>
          {count > 0 && <b className="notification-count">{count}</b>}
        </summary>
        <div className="notification-panel">
          <h2>Notifications</h2>
          {error && <p role="status">{error}</p>}
          {!items.length && !error && <p>No activity for your account yet.</p>}
          {!!count && (
            <button
              className="secondary"
              onClick={async () => {
                try {
                  await rest("/api/workspace/notifications/read", "POST", {
                    ids: items.filter((i) => !i.read).map((i) => i.id),
                  });
                  setItems(items.map((i) => ({ ...i, read: true })));
                } catch {
                  setError("Could not mark notifications as read.");
                }
              }}
            >
              Mark all as read
            </button>
          )}
          <ul>
            {items.map((i) => (
              <li key={i.id} className={i.read ? "" : "unread"}>
                <strong>{i.title}</strong>
                <time>{new Date(i.created_at).toLocaleString()}</time>
              </li>
            ))}
          </ul>
          <small>
            Updates every 15 seconds while this workspace is active.
          </small>
        </div>
      </details>
      <details className="profile-menu">
        <summary aria-label="Profile and preferences">
          <span className="user-avatar" aria-hidden="true">
            {profile.photo_version ? (
              <img
                src={`/api/workspace/profile/photo?v=${profile.photo_version}`}
                alt=""
              />
            ) : profile.avatar === "initials" ? (
              (profile.display_name || user.username).slice(0, 2).toUpperCase()
            ) : (
              avatarSymbols[profile.avatar]
            )}
          </span>
          <span>{profile.display_name || user.username}</span>
        </summary>
        <div className="profile-panel">
          <strong>{user.username}</strong>
          <small>{user.role}</small>
          <button className="secondary" onClick={() => navigate("/account")}>
            Profile & preferences
          </button>
          <button className="secondary" onClick={logout}>
            Sign out
          </button>
        </div>
      </details>
    </div>
  );
}
