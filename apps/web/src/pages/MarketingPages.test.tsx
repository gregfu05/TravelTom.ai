import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import { renderWithProviders } from "../test/testUtils";
import { HowItWorksPage } from "./HowItWorksPage";
import { WhyTravelTomPage } from "./WhyTravelTomPage";

describe("marketing pages", () => {
  beforeEach(() => {
    vi.spyOn(apiClient, "getHealth").mockResolvedValue({ status: "ok" });
  });

  it("renders the Why TravelTom page sections and CTAs", () => {
    renderWithProviders(<WhyTravelTomPage />);

    expect(
      screen.getByRole("heading", {
        name: "Built to make travel choices clearer, faster, and more confident.",
      }),
    ).toBeTruthy();
    expect(screen.getByText("Deterministic by default")).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "Open Planner" }).getAttribute("href"),
    ).toBe("/planner");
  });

  it("renders the How It Works journey and CTA", () => {
    renderWithProviders(<HowItWorksPage />);

    expect(
      screen.getByRole("heading", {
        name: "A practical flow from intent capture to trip-ready shortlist.",
      }),
    ).toBeTruthy();
    expect(screen.getByText("Share your trip goals")).toBeTruthy();
    expect(screen.getByText("Return actionable output")).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "Open Planner" }).getAttribute("href"),
    ).toBe("/planner");
  });
});
