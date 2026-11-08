// @vitest-environment jsdom
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import WorkspaceShell from "./components/WorkspaceShell";
import FederationGlobe from "./components/FederationGlobe";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it("supports keyboard skip navigation to the case content", async () => {
  render(
    <WorkspaceShell
      user={{
        id: "fixture",
        username: "fixture",
        role: "clinician",
        enabled: true,
        node_id: null,
      }}
      path="/cases"
      logout={() => {}}
    >
      <main>
        <h1>Cases</h1>
      </main>
    </WorkspaceShell>,
  );
  const user = userEvent.setup();
  screen.getByText("Skip to content").focus();
  await user.keyboard("{Enter}");
  expect(document.activeElement?.id).toBe("workspace-content");
  await user.tab();
  expect(document.activeElement).not.toBeNull();
});

it("does not animate the research globe when reduced motion is requested", () => {
  vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
  const frame = vi.spyOn(window, "requestAnimationFrame");
  render(<FederationGlobe events={[]} nodes={0} completed={0} />);
  expect(frame).not.toHaveBeenCalled();
  expect(screen.getByRole("img")).toBeTruthy();
});
