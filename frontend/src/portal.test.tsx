// @vitest-environment jsdom
import React from "react";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Portal from "./Portal";
import { HospitalApplications, HospitalWorkspace } from "./Hospitals";
import { rest } from "./api";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  rest: vi.fn(),
}));
const request = vi.mocked(rest);
const session = {
  user: {
    id: "test-clinician",
    username: "test_clinician",
    role: "clinician",
    enabled: true,
    node_id: null,
  },
  csrf: "test-only",
};
beforeEach(() => {
  vi.resetAllMocks();
  window.history.replaceState({}, "", "#/cases/new");
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("session recovery", () => {
  it("preserves unsaved case text after expiry and same-account login", async () => {
    request.mockImplementation(async (path) =>
      path === "/api/llm/status"
        ? { runtime_ready: false, settings: { enabled: false } }
        : session,
    );
    render(<Portal />);
    fireEvent.change(await screen.findByLabelText("Case description"), {
      target: { value: "Unsaved synthetic scenario" },
    });
    act(() => window.dispatchEvent(new Event("medflock-expired")));
    await screen.findByText("Continue your session");
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "test_clinician" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "local-fixture-password" },
    });
    fireEvent.click(screen.getByText("Sign in →"));
    await screen.findByRole("heading", { name: "Describe the case" });
    expect(
      (screen.getByLabelText("Case description") as HTMLTextAreaElement).value,
    ).toBe("Unsaved synthetic scenario");
  });
  it("shows rejected sign-in without exposing a workspace", async () => {
    request.mockRejectedValue(Error("Invalid credentials"));
    render(<Portal />);
    fireEvent.change(await screen.findByLabelText("Username"), {
      target: { value: "bad-user" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "local-fixture-password" },
    });
    fireEvent.click(screen.getByText("Sign in →"));
    await screen.findByText("Invalid credentials");
    expect(
      screen.queryByRole("navigation", { name: "Main navigation" }),
    ).toBeNull();
  });
});

describe("hospital readiness and decisions", () => {
  it("does not treat a bound identity or permissive policy as a live connection", async () => {
    request.mockResolvedValue({
      id: "node-1",
      label: "Synthetic hospital",
      effective_status: "active",
      training_allowed: true,
      transport: "flower",
      transport_binding: {
        flower_node_id: "123",
        public_key_sha256: "a".repeat(64),
      },
      details: {},
    });
    render(<HospitalWorkspace />);
    await screen.findByText("Arrange a verified connection check");
    expect(screen.getByText("Unknown")).toBeTruthy();
    expect(screen.getByText("Blocked pending verification")).toBeTruthy();
    expect(screen.getByText("Binding recorded")).toBeTruthy();
  });
  it("requires confirmation and preserves verification reference for a decision", async () => {
    request.mockResolvedValue([
      {
        id: "request-1",
        organization: "Synthetic institution",
        contact_name: "Fixture",
        contact_email: "fixture@example.invalid",
        location: "Test city",
        registration_reference: "TEST",
        intended_use: "Synthetic training",
        username: "test_hospital",
        status: "pending",
      },
    ]);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<HospitalApplications />);
    fireEvent.change(
      await screen.findByLabelText("Verification record reference"),
      { target: { value: "manual-review-fixture" } },
    );
    fireEvent.change(screen.getByLabelText("Decision"), {
      target: { value: "approved" },
    });
    fireEvent.click(screen.getByText("Record decision"));
    expect(request).toHaveBeenCalledTimes(1);
    confirm.mockReturnValue(true);
    fireEvent.click(screen.getByText("Record decision"));
    expect(request).toHaveBeenCalledWith(
      "/api/admin/hospital-applications/request-1/decision",
      "POST",
      { decision: "approved", verification_reference: "manual-review-fixture" },
    );
    await screen.findByText("Synthetic institution");
  });
});
