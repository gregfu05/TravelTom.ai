import { render, screen, waitFor, within } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { seedSessionStore, createTestQueryClient } from "../../test/testUtils";
import { TopNav } from "./TopNav";
import { useSessionStore } from "../../store/session";

function renderTopNav(initialEntries: string[] = ["/"]) {
  const queryClient = createTestQueryClient();

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route path="*" element={<TopNav />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

describe("TopNav", () => {
  beforeEach(() => {
    vi.spyOn(apiClient, "logout").mockResolvedValue(undefined);
  });

  it("shows the checking state before health resolves", () => {
    const pendingHealth = deferred<{ status: "ok" }>();
    vi.spyOn(apiClient, "getHealth").mockReturnValue(pendingHealth.promise);

    renderTopNav();

    expect(screen.getAllByText("API checking").length).toBeGreaterThan(0);
  });

  it("shows the online state after a successful health check", async () => {
    vi.spyOn(apiClient, "getHealth").mockResolvedValue({ status: "ok" });

    renderTopNav();

    await waitFor(() => {
      expect(screen.getAllByText("API online").length).toBeGreaterThan(0);
    });
  });

  it("shows the unreachable state after a failed health check", async () => {
    vi.spyOn(apiClient, "getHealth").mockRejectedValue(new Error("offline"));

    renderTopNav();

    await waitFor(() => {
      expect(screen.getAllByText("API unreachable").length).toBeGreaterThan(0);
    });
  });

  it("opens the mobile nav and closes it on route change", async () => {
    vi.spyOn(apiClient, "getHealth").mockResolvedValue({ status: "ok" });
    const user = userEvent.setup();

    renderTopNav();

    const menuButton = screen.getByRole("button", { name: "Menu" });
    await user.click(menuButton);
    expect(menuButton.getAttribute("aria-expanded")).toBe("true");

    const mobileNav = screen.getByLabelText("Mobile primary");
    await user.click(within(mobileNav).getByRole("link", { name: "Planner" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Menu" }).getAttribute("aria-expanded")).toBe(
        "false",
      );
    });
  });

  it("clears auth and planner state on logout even if the backend call fails", async () => {
    vi.spyOn(apiClient, "getHealth").mockResolvedValue({ status: "ok" });
    vi.spyOn(apiClient, "logout").mockRejectedValue(new Error("expired"));
    seedSessionStore({
      authToken: "token-123",
      hasRemoteSession: true,
      messages: [
        {
          id: "message-1",
          role: "user",
          content: "Hello",
          createdAt: "2026-03-23T12:00:00Z",
        },
      ],
    });
    const user = userEvent.setup();

    renderTopNav();

    await user.click(screen.getByRole("button", { name: "Logout" }));

    await waitFor(() => {
      expect(screen.getByRole("link", { name: "Login" })).toBeTruthy();
    });
    expect(useSessionStore.getState().authToken).toBeNull();
    expect(useSessionStore.getState().messages).toHaveLength(0);
    expect(useSessionStore.getState().hasRemoteSession).toBe(false);
  });
});
