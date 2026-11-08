import { useEffect, useState } from "react";
import { rest } from "./api";
import PasswordInput from "./components/PasswordInput";
import {
  defaults,
  loadPreferences,
  applyTheme,
  type Preferences,
} from "./preferences";
export default function Account() {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [profile, setProfile] = useState<Preferences>(defaults),
    [profileReady, setProfileReady] = useState(false);
  useEffect(() => {
    loadPreferences()
      .then((p) => {
        setProfile(p);
        setProfileReady(true);
      })
      .catch(() =>
        setMessage("Could not load your preferences. Refresh to retry."),
      );
  }, []);
  return (
    <main className="portal-main">
      <h1>Profile & preferences</h1>
      <p role="status">{message}</p>
      <form
        className="card"
        onSubmit={async (e) => {
          e.preventDefault();
          if (busy || !profileReady) return;
          setBusy(true);
          try {
            const { photo_version: _photo, ...preferences } = profile;
            await rest("/api/workspace/profile", "PUT", preferences);
            applyTheme(profile.theme);
            window.dispatchEvent(new Event("medflock-profile"));
            setMessage("Preferences saved.");
          } catch (e) {
            setMessage((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <h2>Make this workspace yours</h2>
        <label>
          Display name
          <input
            value={profile.display_name}
            maxLength={80}
            onChange={(e) =>
              setProfile({ ...profile, display_name: e.target.value })
            }
          />
        </label>
        <label>
          Fallback icon
          <select
            value={profile.avatar}
            onChange={(e) =>
              setProfile({
                ...profile,
                avatar: e.target.value as Preferences["avatar"],
              })
            }
          >
            {["initials", "leaf", "sun", "moon", "star"].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <div className="profile-photo-editor">
          <span className="user-avatar profile-photo-preview">
            {profile.photo_version ? (
              <img
                src={`/api/workspace/profile/photo?v=${profile.photo_version}`}
                alt="Your profile"
              />
            ) : (
              profile.display_name.slice(0, 2).toUpperCase() || "ME"
            )}
          </span>
          <label>
            Profile photo
            <input
              type="file"
              aria-label="Profile photo"
              accept="image/jpeg,image/png,image/webp"
              disabled={busy || !profileReady}
              onChange={async (e) => {
                const input = e.currentTarget;
                const file = input.files?.[0];
                if (!file) return;
                if (file.size > 2 * 1024 * 1024) {
                  setMessage("Choose an image smaller than 2 MiB.");
                  input.value = "";
                  return;
                }
                setBusy(true);
                try {
                  const form = new FormData();
                  form.append("file", file);
                  const result = await rest(
                    "/api/workspace/profile/photo",
                    "POST",
                    form,
                  );
                  setProfile((p) => ({
                    ...p,
                    photo_version: result.photo_version,
                  }));
                  window.dispatchEvent(new Event("medflock-profile"));
                  setMessage("Profile photo updated.");
                } catch (error) {
                  setMessage((error as Error).message);
                } finally {
                  setBusy(false);
                  input.value = "";
                }
              }}
            />
            <small>JPEG, PNG or WebP · up to 2 MiB · cropped to a square</small>
          </label>
          {profile.photo_version && (
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await rest("/api/workspace/profile/photo", "DELETE");
                  setProfile((p) => ({ ...p, photo_version: null }));
                  window.dispatchEvent(new Event("medflock-profile"));
                  setMessage("Profile photo removed.");
                } catch (error) {
                  setMessage((error as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              Remove photo
            </button>
          )}
        </div>
        <label>
          Appearance
          <select
            value={profile.theme}
            onChange={(e) =>
              setProfile({
                ...profile,
                theme: e.target.value as Preferences["theme"],
              })
            }
          >
            <option value="system">Use device setting</option>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </label>
        <button disabled={busy || !profileReady}>Save preferences</button>
      </form>
      <h2>Account security</h2>
      <form
        className="card"
        onSubmit={async (e) => {
          e.preventDefault();
          if (busy) return;
          setBusy(true);
          setMessage("");
          const body = Object.fromEntries(new FormData(e.currentTarget));
          try {
            await rest("/api/auth/password", "POST", body);
            window.location.reload();
          } catch (e) {
            setMessage((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Current password
          <PasswordInput
            name="current_password"
            type="password"
            autoComplete="current-password"
            required
          />
        </label>
        <label>
          New password
          <PasswordInput
            name="new_password"
            type="password"
            autoComplete="new-password"
            minLength={12}
            maxLength={128}
            required
          />
        </label>
        <p>
          Enter your current password to authorize this change. Changing your
          password revokes every session.
        </p>
        <button disabled={busy}>
          {busy ? "Changing password…" : "Change password"}
        </button>
      </form>
    </main>
  );
}
