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
import PasswordInput from "./components/PasswordInput";
import { navigate, useRoute } from "./navigation";

afterEach(cleanup);
it("lets the user reveal and hide their password without submitting", () => {
  render(
    <label>
      Password
      <PasswordInput name="password" required />
    </label>,
  );
  const input = screen.getByLabelText("Password") as HTMLInputElement;
  expect(input.type).toBe("password");
  fireEvent.click(screen.getByRole("button", { name: "Show password" }));
  expect(input.type).toBe("text");
  fireEvent.click(screen.getByRole("button", { name: "Hide password" }));
  expect(input.type).toBe("password");
});
it("migrates old bookmarks to clean URLs and follows browser history", async () => {
  window.history.replaceState({}, "", "/#/cases");
  function Route() {
    const path = useRoute();
    return <span data-testid="route">{path}</span>;
  }
  render(<Route />);
  expect(window.location.hash).toBe("");
  expect(window.location.pathname).toBe("/cases");
  act(() => {
    navigate("/account");
  });
  expect(screen.getByTestId("route").textContent).toBe("/account");
  await act(async () => window.history.back());
  await waitFor(() =>
    expect(screen.getByTestId("route").textContent).toBe("/cases"),
  );
});
