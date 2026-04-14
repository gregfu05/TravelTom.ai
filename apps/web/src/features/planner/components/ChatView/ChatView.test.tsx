import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClientError, apiClient } from "../../../../api/client";
import {
  renderWithProviders,
  seedSessionStore,
} from "../../../../test/testUtils";
import { useSessionStore } from "../../../../store/session";
import { ChatView } from "./ChatView";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("ChatView", () => {
  beforeEach(() => {
    vi.spyOn(apiClient, "getChatSession").mockResolvedValue({
      sessionId: "session-1",
      state: {},
      messages: [],
      recommendations: [],
    });
  });

  it("appends suggestion chips into the draft", async () => {
    const user = userEvent.setup();

    renderWithProviders(<ChatView />);

    await user.click(
      screen.getByRole("button", {
        name: "Beach destinations in Europe under 1500 EUR",
      }),
    );

    expect(screen.getByLabelText("Message input")).toHaveValue(
      "Beach destinations in Europe under 1500 EUR",
    );
  });

  it("sends a message, shows loading, and renders recommendations", async () => {
    const user = userEvent.setup();
    const sendRequest = deferred<Awaited<ReturnType<typeof apiClient.sendChatMessage>>>();
    vi.spyOn(apiClient, "sendChatMessage").mockReturnValue(sendRequest.promise);
    seedSessionStore({ authToken: "token-123", sessionId: "session-123" });

    renderWithProviders(<ChatView />);

    await user.type(screen.getByLabelText("Message input"), "Plan Lisbon for me");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(screen.getByLabelText("Tom is typing")).toBeTruthy();

    sendRequest.resolve({
      sessionId: "session-remote",
      messageId: "msg-2",
      assistantMessage: "Great choice. Top picks: details below",
      recommendations: [
        {
          itemId: "activity-lisbon",
          itemType: "activity",
          score: 0.94,
          rank: 1,
          explanation: "Culture and food fit.",
          metadata: {
            name: "Lisbon",
            city: "Lisbon",
            map_url: "https://example.com/map",
          },
        },
      ],
      state: {},
    });

    await waitFor(() => {
      expect(screen.getByText("Great choice.")).toBeTruthy();
    });
    expect(screen.getByText("Recommended options")).toBeTruthy();
    expect(screen.getAllByText("Lisbon").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "View on map" }).length).toBeGreaterThan(0);
    expect(useSessionStore.getState().sessionId).toBe("session-remote");
  });

  it("retries the last failed message without duplicating the user message", async () => {
    const user = userEvent.setup();
    const sendSpy = vi
      .spyOn(apiClient, "sendChatMessage")
      .mockRejectedValueOnce(new Error("Network down"))
      .mockResolvedValueOnce({
        sessionId: "session-123",
        messageId: "msg-1",
        assistantMessage: "Recovered response",
        recommendations: [],
        state: {},
      });

    renderWithProviders(<ChatView />);

    await user.type(screen.getByLabelText("Message input"), "Need hotels");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByRole("alert")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Retry last message" }));

    await waitFor(() => {
      expect(screen.getByText("Recovered response")).toBeTruthy();
    });
    expect(sendSpy).toHaveBeenCalledTimes(2);
    expect(screen.getAllByText("Need hotels")).toHaveLength(1);
  });

  it("shows cooldown copy and disables sending during a TravelTom rate limit", async () => {
    seedSessionStore({
      chatError: {
        kind: "traveltom_rate_limit",
        message: "Cooling down",
        actionLabel: "Retry last message",
        cooldownUntilMs: Date.now() + 5_000,
      },
    });

    renderWithProviders(<ChatView />);

    expect(screen.getByText(/Retry becomes available in 5s/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Retry in 5s" })).toBeDisabled();
  });

  it("hydrates a remote session transcript on mount", async () => {
    vi.spyOn(apiClient, "getChatSession").mockResolvedValue({
      sessionId: "session-remote",
      state: {},
      messages: [
        {
          id: "message-1",
          role: "user",
          content: "Hello",
          createdAt: "2026-03-23T12:00:00Z",
        },
        {
          id: "message-2",
          role: "assistant",
          content: "Hydrated reply",
          createdAt: "2026-03-23T12:00:01Z",
        },
      ],
      recommendations: [
        {
          itemId: "hotel-1",
          itemType: "hotel",
          score: 0.9,
          rank: 1,
          explanation: "Hydrated fit",
          metadata: { name: "Hydrated Hotel", city: "Lisbon" },
        },
      ],
    });
    seedSessionStore({
      authToken: "token-123",
      hasRemoteSession: true,
      sessionId: "session-remote",
    });

    renderWithProviders(<ChatView />);

    expect(await screen.findByText("Hydrated reply")).toBeTruthy();
    expect(screen.getAllByText("Hydrated Hotel").length).toBeGreaterThan(0);
  });

  it("clears auth and conversation after a hydration 401", async () => {
    vi.spyOn(apiClient, "getChatSession").mockRejectedValue(
      new ApiClientError(401, {
        code: "unauthorized",
        kind: "generic",
        message: "Unauthorized",
      }),
    );
    seedSessionStore({
      authToken: "token-123",
      hasRemoteSession: true,
      sessionId: "session-remote",
      messages: [
        {
          id: "message-1",
          role: "user",
          content: "Persisted",
          createdAt: "2026-03-23T12:00:00Z",
        },
      ],
    });

    renderWithProviders(<ChatView />);

    await waitFor(() => {
      expect(useSessionStore.getState().authToken).toBeNull();
    });
    expect(useSessionStore.getState().messages).toHaveLength(0);
    expect(useSessionStore.getState().hasRemoteSession).toBe(false);
  });

  it("resets the conversation while preserving auth on New Session", async () => {
    const user = userEvent.setup();
    seedSessionStore({
      authToken: "token-123",
      messages: [
        {
          id: "message-1",
          role: "user",
          content: "Persisted",
          createdAt: "2026-03-23T12:00:00Z",
        },
      ],
      latestRecommendations: [
        {
          itemId: "hotel-1",
          itemType: "hotel",
          score: 0.91,
          rank: 1,
          explanation: "Great",
          metadata: { name: "Test Hotel", city: "Lisbon" },
        },
      ],
    });

    renderWithProviders(<ChatView />);

    await user.click(screen.getByRole("button", { name: "New Session" }));

    expect(screen.getByText("Start with a trip idea")).toBeTruthy();
    expect(useSessionStore.getState().authToken).toBe("token-123");
    expect(useSessionStore.getState().messages).toHaveLength(0);
  });

  it("opens and closes the mobile recommendations drawer", async () => {
    const user = userEvent.setup();
    seedSessionStore({
      latestRecommendations: [
        {
          itemId: "hotel-1",
          itemType: "hotel",
          score: 0.91,
          rank: 1,
          explanation: "Great",
          metadata: { name: "Test Hotel", city: "Lisbon" },
        },
      ],
    });

    renderWithProviders(<ChatView />);

    await user.click(screen.getByRole("button", { name: "1 Picks" }));
    expect(screen.getByRole("dialog", { name: "Recommendations" })).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Close" }));

    expect(screen.getByRole("dialog", { name: "Recommendations" }).className).not.toContain(
      "drawer-open",
    );
  });
});
