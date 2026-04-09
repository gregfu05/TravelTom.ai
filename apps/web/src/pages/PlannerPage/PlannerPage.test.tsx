import { render, screen, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { seedSessionStore, createTestQueryClient } from "../../test/testUtils";
import { PlannerPage } from "./PlannerPage";

function LoginProbe() {
  const location = useLocation();
  return <p>{JSON.stringify(location.state)}</p>;
}

describe("PlannerPage", () => {
  beforeEach(() => {
    vi.spyOn(apiClient, "getHealth").mockResolvedValue({ status: "ok" });
  });

  it("redirects unauthenticated users to login and preserves the planner target", async () => {
    const queryClient = createTestQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/planner"]}>
          <Routes>
            <Route path="/planner" element={<PlannerPage />} />
            <Route path="/login" element={<LoginProbe />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText('{"from":"/planner"}')).toBeTruthy();
    });
  });

  it("renders the planner chat view when authenticated", () => {
    seedSessionStore({ authToken: "token-123" });

    const queryClient = createTestQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/planner"]}>
          <Routes>
            <Route path="/planner" element={<PlannerPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByText("Start with a trip idea")).toBeTruthy();
  });
});
