import { useEffect, useState, type ReactNode } from "react";
import ProfileMenu from "./ProfileMenu";
import type { User } from "../workspaceApi";
import {
  canUseCases,
  landing,
  navigate,
  researchPages,
  segment,
} from "../navigation";

export default function WorkspaceShell({
  user,
  path,
  children,
  logout,
}: {
  user: User;
  path: string;
  children: ReactNode;
  logout: () => void;
}) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    setOpen(false);
    document.querySelector<HTMLElement>("#workspace-content")?.focus();
  }, [path]);
  const links = [
    ...(canUseCases(user.role) ? [["/cases", "My cases", "▤"]] : []),
    ...(["hospital", "client"].includes(user.role)
      ? [["/institution", "Institution setup", "⌂"]]
      : []),
    ...(user.role === "admin"
      ? [
          ["/admin/hospitals", "Hospital requests", "◇"],
          ["/admin/users", "Manage workspace", "⚙"],
        ]
      : []),
    ...(["admin", "researcher", "viewer"].includes(user.role)
      ? [
          ["/research/overview", "Learning network", "◎"],
          ["/evolution", "Model progress", "↗"],
        ]
      : []),
  ];
  const section = path.startsWith("/cases")
    ? "My cases"
    : path.startsWith("/admin")
      ? "Administration"
      : path.startsWith("/research")
        ? "Research workspace"
        : path === "/institution"
          ? "Institution setup"
          : path === "/evolution"
            ? "Model evolution"
            : path === "/account"
              ? "Account security"
              : "Help";
  return (
    <div className="workspace-shell">
      <a
        className="skip-link"
        href="#workspace-content"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("workspace-content")?.focus();
        }}
      >
        Skip to content
      </a>
      <aside
        className={`workspace-nav ${open ? "is-open" : ""}`}
        id="workspace-navigation"
      >
        <button
          className="workspace-brand"
          onClick={() => navigate(landing(user.role))}
        >
          <span className="brand-symbol" aria-hidden="true">
            m
          </span>
          medflock
          <span className="brand-dot" />
        </button>
        <div className="workspace-role">
          <span className="eyebrow">WORKSPACE</span>
          <strong>
            {user.role === "hospital"
              ? "Hospital partner"
              : user.role === "clinician"
                ? "Care professional"
                : user.role}
          </strong>
        </div>
        <nav aria-label="Main navigation">
          {links.map(([url, label, number]) => (
            <a
              key={url}
              href={url}
              aria-current={
                path === url ||
                (url === "/cases" && path.startsWith("/cases/")) ||
                (url === "/research/overview" && path.startsWith("/research/"))
                  ? "page"
                  : undefined
              }
              onClick={(e) => {
                e.preventDefault();
                navigate(url);
              }}
            >
              <span aria-hidden="true">{number}</span>
              {label}
            </a>
          ))}
        </nav>
        {path.startsWith("/research") && (
          <nav className="research-subnav" aria-label="Research tools">
            {researchPages.map((page) => (
              <a
                href={`/research/${segment(page)}`}
                key={page}
                aria-current={
                  path === `/research/${segment(page)}` ? "page" : undefined
                }
                onClick={(e) => {
                  e.preventDefault();
                  navigate(`/research/${segment(page)}`);
                }}
              >
                {page}
              </a>
            ))}
          </nav>
        )}
        <div className="workspace-nav-foot">
          <span className="status-pill warning">Research beta</span>
          <p>
            Clinical review required.
            <br />
            Synthetic cases only.
          </p>
          <a
            href="/help"
            onClick={(e) => {
              e.preventDefault();
              navigate("/help");
            }}
          >
            Getting started & help
          </a>
        </div>
      </aside>
      <div className="workspace-body">
        <header className="workspace-topbar">
          <button
            className="mobile-menu secondary"
            aria-expanded={open}
            aria-controls="workspace-navigation"
            onClick={() => setOpen(!open)}
          >
            Menu
          </button>
          <div className="breadcrumbs">
            MedFlock <span aria-hidden="true">/</span>{" "}
            <strong>{section}</strong>
            <span className="topbar-caption">
              A little more clarity. At every step.
            </span>
          </div>
          <ProfileMenu user={user} logout={logout} />
        </header>
        <div id="workspace-content" tabIndex={-1}>
          {children}
        </div>
        <footer
          className={`workspace-footer ${path.startsWith("/cases/") ? "chat-footer" : ""}`}
        >
          MedFlock <span>Clinical collaboration · Research beta</span>
        </footer>
      </div>
    </div>
  );
}
