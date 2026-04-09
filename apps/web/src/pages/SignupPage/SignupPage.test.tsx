import { render, screen, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { createTestQueryClient } from "../../test/testUtils";
import { useSessionStore } from "../../store/session";
import { SignupPage } from "./SignupPage";

function LocationProbe() {
  const location = useLocation();
  return <p>{location.pathname}:{JSON.stringify(location.state)}</p>;
}

function renderSignupPage(initialEntry: { pathname: string; state?: unknown }) {
  const queryClient = createTestQueryClient();

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/login" element={<LocationProbe />} />
          <Route path="/planner" element={<LocationProbe />} />
          <Route path="/how-it-works" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("SignupPage", () => {
  beforeEach(() => {
    vi.spyOn(apiClient, "getHealth").mockResolvedValue({ status: "ok" });
  });

  it("blocks mismatched passwords before calling the API", async () => {
    const signupSpy = vi.spyOn(apiClient, "signup");
    const user = userEvent.setup();

    renderSignupPage({ pathname: "/signup" });

    await user.type(screen.getByLabelText("Email"), "traveler@example.com");
    await user.type(screen.getByLabelText(/^Password$/), "password123");
    await user.type(screen.getByLabelText("Confirm password"), "different");
    await user.click(screen.getByRole("button", { name: "Start planning" }));

    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByText("Passwords do not match.")).toBeTruthy();
    expect(signupSpy).not.toHaveBeenCalled();
  });

  it("submits signup, stores auth, and redirects into the planner", async () => {
    vi.spyOn(apiClient, "signup").mockResolvedValue({
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

    renderSignupPage({ pathname: "/signup", state: { from: "/how-it-works" } });

    await user.type(screen.getByLabelText("Email"), "traveler@example.com");
    await user.type(screen.getByLabelText(/^Password$/), "password123");
    await user.type(screen.getByLabelText("Confirm password"), "password123");
    await user.click(screen.getByRole("button", { name: "Start planning" }));

    await waitFor(() => {
      expect(screen.getByText("/planner:null")).toBeTruthy();
    });
    expect(useSessionStore.getState().authToken).toBe("token-123");
  });

  it("shows API errors on failed signup", async () => {
    vi.spyOn(apiClient, "signup").mockRejectedValue(new Error("Email already exists"));
    const user = userEvent.setup();

    renderSignupPage({ pathname: "/signup" });

    await user.type(screen.getByLabelText("Email"), "traveler@example.com");
    await user.type(screen.getByLabelText(/^Password$/), "password123");
    await user.type(screen.getByLabelText("Confirm password"), "password123");
    await user.click(screen.getByRole("button", { name: "Start planning" }));

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText("Email already exists")).toBeTruthy();
  });

  it("preserves redirect state on the login link", async () => {
    const user = userEvent.setup();

    renderSignupPage({ pathname: "/signup", state: { from: "/how-it-works" } });

    await user.click(screen.getByRole("link", { name: "Sign in" }));

    expect(await screen.findByText('/login:{"from":"/how-it-works"}')).toBeTruthy();
  });
});
