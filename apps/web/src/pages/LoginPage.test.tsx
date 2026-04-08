import { render, screen, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import { createTestQueryClient, seedSessionStore } from "../test/testUtils";
import { useSessionStore } from "../store/session";
import { LoginPage } from "./LoginPage";

function LocationProbe() {
  const location = useLocation();
  return <p>{location.pathname}:{JSON.stringify(location.state)}</p>;
}

function renderLoginPage(initialEntry: { pathname: string; state?: unknown }) {
  const queryClient = createTestQueryClient();

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<LocationProbe />} />
          <Route path="/planner" element={<LocationProbe />} />
          <Route path="/why-traveltom" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    vi.spyOn(apiClient, "getHealth").mockResolvedValue({ status: "ok" });
  });

  it("redirects authenticated users to the planner", async () => {
    seedSessionStore({ authToken: "token-123" });

    renderLoginPage({ pathname: "/login" });

    expect(await screen.findByText("/planner:null")).toBeTruthy();
  });

  it("submits login, stores auth, and redirects into the planner", async () => {
    vi.spyOn(apiClient, "login").mockResolvedValue({
      accessToken: "token-123",
      tokenType: "bearer",
      expiresIn: 3600,
      idleTimeoutIn: 900,
      user: {
        id: "user-1",
        email: "traveler@example.com",
      },
    });
    const user = userEvent.setup();

    renderLoginPage({ pathname: "/login", state: { from: "/why-traveltom" } });

    await user.type(screen.getByLabelText("Email"), "traveler@example.com");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.click(screen.getByRole("button", { name: "Enter the planner" }));

    await waitFor(() => {
      expect(screen.getByText("/planner:null")).toBeTruthy();
    });
    expect(apiClient.login).toHaveBeenCalledWith({
      email: "traveler@example.com",
      password: "password123",
    });
    expect(useSessionStore.getState().authToken).toBe("token-123");
  });

  it("shows API errors on failed login", async () => {
    vi.spyOn(apiClient, "login").mockRejectedValue(new Error("Invalid credentials"));
    const user = userEvent.setup();

    renderLoginPage({ pathname: "/login" });

    await user.type(screen.getByLabelText("Email"), "traveler@example.com");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.click(screen.getByRole("button", { name: "Enter the planner" }));

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText("Invalid credentials")).toBeTruthy();
  });

  it("preserves redirect state on the signup link", async () => {
    const user = userEvent.setup();

    renderLoginPage({ pathname: "/login", state: { from: "/why-traveltom" } });

    await user.click(screen.getByRole("link", { name: "Create one" }));

    expect(await screen.findByText('/signup:{"from":"/why-traveltom"}')).toBeTruthy();
  });
});
