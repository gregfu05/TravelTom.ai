import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { renderWithProviders } from "../../test/testUtils";
import { AuthLayout } from "./AuthLayout";

describe("AuthLayout", () => {
  beforeEach(() => {
    vi.spyOn(apiClient, "getHealth").mockResolvedValue({ status: "ok" });
  });

  it("renders shared auth chrome and highlights", () => {
    renderWithProviders(
      <AuthLayout
        eyebrow="Welcome"
        title="Sign in to TravelTom"
        description="Continue your trip."
        panelTitle="Panel title"
        panelBody="Panel body"
        highlights={["One", "Two"]}
        reassurance={<p>Reassurance copy</p>}
      >
        <form aria-label="Auth form" />
      </AuthLayout>,
    );

    expect(screen.getByRole("link", { name: "TravelTom homepage" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to home" })).toBeTruthy();
    expect(screen.getByLabelText("TravelTom planning highlights")).toBeTruthy();
    expect(screen.getByText("Reassurance copy")).toBeTruthy();
  });
});
