import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { HomePage } from "./HomePage";
import { renderWithProviders } from "../../test/testUtils";

describe("HomePage", () => {
  beforeEach(() => {
    vi.spyOn(apiClient, "getHealth").mockResolvedValue({ status: "ok" });
  });

  it("renders the primary CTA links and planner preview", () => {
    renderWithProviders(<HomePage />);

    expect(
      screen.getByRole("link", { name: "Open Planner" }).getAttribute("href"),
    ).toBe("/planner");
    expect(
      screen
        .getAllByRole("link", { name: "How It Works" })
        .some((link) => link.getAttribute("href") === "/how-it-works"),
    ).toBe(true);
    expect(screen.getByLabelText("Travel planner snapshot")).toBeTruthy();
    expect(screen.getByText("Sunset Sailing in Lisbon")).toBeTruthy();
    expect(screen.getByText("Solaris Riverside Hotel")).toBeTruthy();
  });
});
