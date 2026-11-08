// @vitest-environment jsdom
import React from "react";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import Account from "./Account";
import ModelText, { hasRepetition } from "./components/ModelText";
import FederationGlobe from "./components/FederationGlobe";
import { rest } from "./api";

vi.mock("./api", () => ({ rest: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it("uploads a photo separately from preferences and lets its owner remove it", async () => {
  vi.mocked(rest).mockImplementation(async (_path, method) =>
    method === "POST"
      ? { photo_version: "new-photo" }
      : {
          display_name: "Reviewer",
          avatar: "initials",
          theme: "light",
          photo_version: null,
        },
  );
  render(<Account />);
  await waitFor(() =>
    expect(
      (screen.getByLabelText("Display name") as HTMLInputElement).value,
    ).toBe("Reviewer"),
  );
  const file = new File(["fixture"], "photo.png", { type: "image/png" });
  fireEvent.change(screen.getByLabelText("Profile photo"), {
    target: { files: [file] },
  });
  await screen.findByAltText("Your profile");
  expect(
    vi
      .mocked(rest)
      .mock.calls.some(
        ([path, method, body]) =>
          path === "/api/workspace/profile/photo" &&
          method === "POST" &&
          body instanceof FormData,
      ),
  ).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Save preferences" }));
  await waitFor(() =>
    expect(vi.mocked(rest)).toHaveBeenCalledWith(
      "/api/workspace/profile",
      "PUT",
      { display_name: "Reviewer", avatar: "initials", theme: "light" },
    ),
  );
  fireEvent.click(screen.getByRole("button", { name: "Remove photo" }));
  await waitFor(() => expect(screen.queryByAltText("Your profile")).toBeNull());
});

it("collapses repeated historical output and renders formatting without interpreting HTML", () => {
  const repeated =
    "Specific details about the patient's previous medication side effect history. ".repeat(
      3,
    );
  expect(hasRepetition(repeated)).toBe(true);
  const { container } = render(<ModelText text={repeated} />);
  expect(container.querySelector("details")?.open).toBe(false);
  cleanup();
  render(
    <ModelText text={"**Timing:** 90 minutes\n<img src=x onerror=alert(1)>"} />,
  );
  expect(screen.getByText("Timing:").tagName).toBe("STRONG");
  expect(document.querySelector("img")).toBeNull();
});

it("animates only newly accepted contributions with a source and weight label", () => {
  vi.useFakeTimers();
  vi.stubGlobal("matchMedia", () => ({ matches: true }));
  const event = {
    sequence: 1,
    eventId: "event-1",
    createdAt: "2026-10-25",
    kind: "contribution.accepted",
    details: { node_id: "hospital-a" },
  };
  const { rerender, container } = render(
    <FederationGlobe events={[event]} nodes={1} completed={0} />,
  );
  expect(container.querySelector("[data-event-sequence]")).toBeNull();
  rerender(
    <FederationGlobe
      events={[event, { ...event, sequence: 2 }]}
      nodes={1}
      completed={0}
    />,
  );
  expect(screen.getByText("Weights received · hospital-a")).toBeTruthy();
  // Reduced motion reports activity without starting projectiles.
  act(() => vi.advanceTimersByTime(2000));
  expect(container.querySelector("[data-event-sequence]")).toBeNull();
});

it("starts each arriving projectile on its own animation timeline", () => {
  vi.useFakeTimers();
  vi.stubGlobal("matchMedia", () => ({ matches: false }));
  const start = vi.fn();
  Object.defineProperty(SVGElement.prototype, "beginElementAt", {
    configurable: true,
    value: start,
  });
  vi.stubGlobal("requestAnimationFrame", () => 1);
  vi.stubGlobal("cancelAnimationFrame", vi.fn());
  const { rerender, container } = render(
    <FederationGlobe events={[]} nodes={1} completed={0} />,
  );
  rerender(
    <FederationGlobe
      events={[
        {
          sequence: 2,
          eventId: "arrival",
          createdAt: "2026-10-25",
          kind: "contribution.accepted",
          details: { node_id: "hospital-b" },
        },
      ]}
      nodes={1}
      completed={0}
    />,
  );
  act(() => vi.advanceTimersByTime(1900));
  expect(container.querySelector('[data-event-sequence="2"]')).toBeTruthy();
  expect(
    screen.getByText("Weights · hospital-b", { selector: "text" }),
  ).toBeTruthy();
  expect(start).toHaveBeenCalledWith(0);
  expect(start).toHaveBeenCalledWith(1.45);
  delete (SVGElement.prototype as unknown as Record<string, unknown>)
    .beginElementAt;
});
