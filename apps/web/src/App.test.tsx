import { render, screen, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { apiClient } from "./api/client";
import { createTestQueryClient } from "./test/testUtils";

describe("App routing", () => {
  beforeEach(() => {
    vi.spyOn(apiClient, "getHealth").mockResolvedValue({ status: "ok" });
  });

  it("renders the homepage on the default route", () => {
    window.history.pushState({}, "", "/");

    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <App />
      </QueryClientProvider>,
    );

    expect(
      screen.getByRole("heading", {
        name: "Plan an incredible trip with one conversation.",
      }),
    ).toBeTruthy();
  });

  it("redirects unknown routes back to the homepage", async () => {
    window.history.pushState({}, "", "/missing-route");

    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <App />
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(window.location.pathname).toBe("/");
    });
    expect(
      screen.getByRole("heading", {
        name: "Plan an incredible trip with one conversation.",
      }),
    ).toBeTruthy();
  });
});
