import { useEffect, useState } from "react";

export type Role =
  | "admin"
  | "clinician"
  | "researcher"
  | "hospital"
  | "client"
  | "viewer";
export const researchPages = [
  "Overview",
  "Experiments",
  "Datasets",
  "Fleet",
  "Models",
  "Model lab",
  "API explorer",
] as const;
export const adminPages = [
  "Hospitals",
  "Users",
  "Clients",
  "Corpora",
  "Datasets",
  "Assistant",
  "Audit",
] as const;
export const segment = (name: string) =>
  name.toLowerCase().replaceAll(" ", "-");
export const landing = (role: Role) =>
  role === "admin"
    ? "/admin/hospitals"
    : ["hospital", "client"].includes(role)
      ? "/institution"
      : ["researcher", "viewer"].includes(role)
        ? "/research/overview"
        : "/cases";
export const canUseCases = (role: Role) =>
  ["admin", "clinician", "researcher", "hospital"].includes(role);
export function allowedRoute(path: string, role: Role) {
  if (["/account", "/help"].includes(path)) return true;
  if (/^\/cases(?:\/[a-zA-Z0-9_-]+)?$/.test(path)) return canUseCases(role);
  if (path === "/institution") return ["hospital", "client"].includes(role);
  if (path === "/evolution")
    return ["admin", "researcher", "viewer"].includes(role);
  if (researchPages.some((p) => path === `/research/${segment(p)}`))
    return ["admin", "researcher", "viewer"].includes(role);
  return (
    role === "admin" && adminPages.some((p) => path === `/admin/${segment(p)}`)
  );
}
export const currentPath = () =>
  window.location.hash.startsWith("#/")
    ? window.location.hash.slice(1)
    : window.location.pathname;
export const canLeave = () =>
  window.dispatchEvent(
    new Event("medflock-before-navigation", { cancelable: true }),
  );
export function navigate(path: string, replace = false, guarded = true) {
  if (guarded && !canLeave()) return false;
  window.history[replace ? "replaceState" : "pushState"]({}, "", path);
  window.dispatchEvent(new Event("medflock-route"));
  return true;
}
export function useRoute() {
  const [path, setPath] = useState(currentPath);
  useEffect(() => {
    if (window.location.hash.startsWith("#/"))
      window.history.replaceState({}, "", window.location.hash.slice(1));
    let previous = currentPath();
    const change = () => {
      previous = currentPath();
      setPath(previous);
    };
    const history = () => {
      if (currentPath() === previous) return;
      if (!canLeave()) window.history.replaceState({}, "", previous);
      else change();
    };
    window.addEventListener("medflock-route", change);
    window.addEventListener("popstate", history);
    window.addEventListener("hashchange", history);
    return () => {
      window.removeEventListener("medflock-route", change);
      window.removeEventListener("popstate", history);
      window.removeEventListener("hashchange", history);
    };
  }, []);
  return path;
}
