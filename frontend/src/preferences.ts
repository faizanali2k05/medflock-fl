import { rest } from "./api";
export type Preferences = {
  display_name: string;
  avatar: "initials" | "leaf" | "sun" | "moon" | "star";
  theme: "light" | "dark" | "system";
  photo_version?: string | null;
};
export const defaults: Preferences = {
  display_name: "",
  avatar: "initials",
  theme: "system",
};
export const avatarSymbols = { leaf: "❧", sun: "☀", moon: "☾", star: "☆" };
export function applyTheme(theme: Preferences["theme"]) {
  document.documentElement.dataset.theme =
    theme === "system"
      ? window.matchMedia?.("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      : theme;
}
export async function loadPreferences() {
  const p: Preferences = await rest("/api/workspace/profile");
  applyTheme(p.theme);
  return p;
}
