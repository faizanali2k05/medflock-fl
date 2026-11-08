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
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import CaseChat from "./CaseChat";
import { allowedRoute, landing, navigate } from "./navigation";
import { rest, streamCase } from "./api";
import type { CaseRecord } from "./workspaceApi";

vi.mock("./api", () => ({ rest: vi.fn(), streamCase: vi.fn() }));
const request = vi.mocked(rest),
  stream = vi.mocked(streamCase);
const record = (overrides = {}): CaseRecord => ({
  id: "case-1",
  title: "Synthetic review",
  status: "active",
  revision: 3,
  created_at: "2026-10-24",
  updated_at: "2026-10-24",
  details: {
    draft: "My original question",
    summary: "Extracted facts",
    reviewed: false,
    messages: [],
  },
  ...overrides,
});
beforeEach(() => {
  vi.resetAllMocks();
  window.history.replaceState({}, "", "#/cases/new");
});
afterEach(cleanup);

describe("workspace boundaries", () => {
  it("lands each role in its workspace and blocks unrelated routes", () => {
    expect(landing("clinician")).toBe("/cases");
    expect(landing("hospital")).toBe("/institution");
    expect(landing("admin")).toBe("/admin/hospitals");
    expect(landing("researcher")).toBe("/research/overview");
    expect(allowedRoute("/admin/users", "hospital")).toBe(false);
    expect(allowedRoute("/cases/case-1", "viewer")).toBe(false);
    expect(allowedRoute("/research/datasets", "researcher")).toBe(true);
  });
  it("honors cancellation before changing a deep link", () => {
    const stop = (event: Event) => event.preventDefault();
    window.addEventListener("medflock-before-navigation", stop);
    expect(navigate("/cases")).toBe(false);
    expect(window.location.pathname + window.location.hash).toBe(
      "/#/cases/new",
    );
    window.removeEventListener("medflock-before-navigation", stop);
  });
});

describe("case journeys", () => {
  it("takes a new synthetic case through extraction, review and a saved discussion", async () => {
    let saved = record({
      details: { draft: "", summary: "", reviewed: false, messages: [] },
    });
    request.mockImplementation(async (_path, method, body) => {
      if (method === "PUT")
        saved = {
          ...saved,
          revision: saved.revision + 1,
          details: { ...saved.details, ...(body as object) },
        };
      return saved;
    });
    stream.mockImplementation(async (body) => {
      const input = body as { prompt: string; mode: string };
      const answer =
        input.mode === "organize"
          ? "Synthetic extracted facts"
          : "Synthetic discussion draft";
      saved = {
        ...saved,
        revision: saved.revision + 1,
        details: {
          ...saved.details,
          draft: "",
          summary: input.mode === "organize" ? answer : saved.details.summary,
          messages: [
            ...saved.details.messages,
            { role: "user", content: input.prompt },
            { role: "assistant", content: answer },
          ],
        },
      };
      return {
        case: saved,
        answer,
        seconds: 1,
        usage: { completion_tokens: 8 },
        truncated: false,
      };
    });
    render(<CaseChat role="clinician" ready />);
    fireEvent.change(screen.getByLabelText("Case description"), {
      target: { value: "Synthetic initial question" },
    });
    fireEvent.click(
      screen.getByLabelText(
        "This is a synthetic case with no real patient information.",
      ),
    );
    fireEvent.click(screen.getByText("Organize case →"));
    await screen.findByDisplayValue("Synthetic extracted facts");
    fireEvent.click(screen.getByText("Save reviewed facts & discuss →"));
    fireEvent.change(await screen.findByLabelText("Your message"), {
      target: { value: "Synthetic follow-up" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await screen.findByRole("region", { name: "Case chat" });
    expect(screen.getByText("Synthetic discussion draft")).toBeTruthy();
    expect(saved.details.reviewed).toBe(true);
    expect(saved.details.messages).toHaveLength(4);
    fireEvent.change(screen.getByLabelText("Your message"), {
      target: { value: "Second follow-up in the same case" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await waitFor(() => expect(saved.details.messages).toHaveLength(6));
    expect(stream).toHaveBeenLastCalledWith(
      expect.objectContaining({
        case_id: "case-1",
        mode: "chat",
        use_reviewed_summary: false,
      }),
      expect.any(Function),
    );
    expect(screen.getByLabelText("Your message")).toBeTruthy();

    expect(window.location.pathname).toBe("/cases/case-1");
  });
  it("preserves edited text when a stale revision is rejected", async () => {
    request.mockImplementation(async (_path, method) => {
      if (method === "PUT")
        throw Error("Revision conflict: reload the saved version");
      return record({
        details: {
          draft: "Original",
          summary: "",
          reviewed: false,
          messages: [],
        },
      });
    });
    render(<CaseChat role="clinician" ready caseId="case-1" />);
    fireEvent.change(await screen.findByLabelText("Case description"), {
      target: { value: "Unsaved correction" },
    });
    fireEvent.click(screen.getByText("Save draft"));
    await screen.findByText(/Revision conflict/);
    expect(
      (screen.getByLabelText("Case description") as HTMLTextAreaElement).value,
    ).toBe("Unsaved correction");
  });
  it("saves reviewed facts without replacing the user's question", async () => {
    const row = record();
    request.mockImplementation(async (_path, method, body) =>
      method === "PUT"
        ? {
            ...row,
            details: { ...row.details, ...(body as object), reviewed: true },
          }
        : row,
    );
    render(<CaseChat role="clinician" ready caseId="case-1" />);
    fireEvent.click(await screen.findByText("Save reviewed facts & discuss →"));
    await screen.findByText(
      "Your reviewed summary is saved. Write your follow-up in your own words.",
    );
    expect(
      (screen.getByLabelText("Your message") as HTMLTextAreaElement).value,
    ).toBe("My original question");
    expect(request).toHaveBeenCalledWith(
      "/api/cases/case-1",
      "PUT",
      expect.objectContaining({
        reviewed: true,
        draft: "My original question",
      }),
    );
  });
  it("retains interrupted stream text and saved input without reporting success", async () => {
    const row = record({
      details: {
        draft: "Synthetic chest pain question",
        summary: "",
        reviewed: false,
        messages: [],
      },
    });
    request.mockResolvedValue(row);
    stream.mockImplementation(async (_body, chunk) => {
      chunk("Partial model text");
      throw Error("Connection interrupted");
    });
    render(<CaseChat role="clinician" ready caseId="case-1" />);
    fireEvent.click(await screen.findByText("Organize case →"));
    await screen.findByText("Interrupted draft · not saved as an answer");
    expect(screen.getByText("Partial model text")).toBeTruthy();
    expect(
      (screen.getByLabelText("Case description") as HTMLTextAreaElement).value,
    ).toBe("Synthetic chest pain question");
    expect(screen.queryByText(/Response saved/)).toBeNull();
  });
  it("keeps archived cases read-only", async () => {
    request.mockResolvedValue(record({ status: "archived" }));
    render(<CaseChat role="clinician" ready caseId="case-1" />);
    await screen.findByText("Restore case");
    expect(
      (
        screen.getByLabelText(
          "Editable case understanding",
        ) as HTMLTextAreaElement
      ).disabled,
    ).toBe(true);
    expect((screen.getByText("Save draft") as HTMLButtonElement).disabled).toBe(
      true,
    );
  });
  it("clears previous case content when a different case cannot load", async () => {
    request
      .mockResolvedValueOnce(record())
      .mockRejectedValueOnce(Error("Not found"));
    const view = render(<CaseChat role="clinician" ready caseId="case-1" />);
    await screen.findByDisplayValue("Extracted facts");
    view.rerender(<CaseChat role="clinician" ready caseId="missing" />);
    await screen.findByText("Not found", { exact: false });
    expect(screen.queryByDisplayValue("Extracted facts")).toBeNull();
  });
  it("prevents duplicate save requests while one is pending", async () => {
    let finish!: (value: unknown) => void;
    request.mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    render(<CaseChat role="clinician" ready />);
    fireEvent.click(
      screen.getByLabelText(
        "This is a synthetic case with no real patient information.",
      ),
    );
    const save = screen.getByText("Save draft");
    fireEvent.click(save);
    fireEvent.click(save);
    expect(request).toHaveBeenCalledTimes(1);
    await act(async () => {
      request.mockResolvedValue(record());
      finish(record());
    });
    await waitFor(() =>
      expect(
        screen.getByText("Draft saved. You can reopen it from My cases."),
      ).toBeTruthy(),
    );
  });
});
