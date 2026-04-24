import { beforeEach, describe, expect, it } from "vitest";

import { useSessionStore } from "./session";

describe("useSessionStore", () => {
  beforeEach(() => {
    useSessionStore.setState(useSessionStore.getInitialState(), true);
    window.localStorage.removeItem("traveltom-session");
  });

  it("hydrates a backend-backed conversation without losing auth", () => {
    useSessionStore.setState({
      sessionId: "session-initial",
      hasRemoteSession: false,
      messages: [],
      latestRecommendations: [],
      isSending: false,
      chatError: {
        kind: "provider_rate_limit",
        message: "Busy",
        cooldownUntilMs: null,
        actionLabel: null,
      },
      authToken: "token-123",
    });

    useSessionStore.getState().hydrateConversation({
      sessionId: "session-restored",
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
          content: "Hi, I'm Tom.",
          createdAt: "2026-03-23T12:00:01Z",
        },
      ],
      latestRecommendations: [
        {
          itemId: "restaurant-lisbon",
          itemType: "restaurant",
          rank: 1,
          metadata: { name: "Lisbon" },
        },
      ],
    });

    const hydratedState = useSessionStore.getState();

    expect(hydratedState.sessionId).toBe("session-restored");
    expect(hydratedState.hasRemoteSession).toBe(true);
    expect(hydratedState.messages).toHaveLength(2);
    expect(hydratedState.latestRecommendations[0]?.itemId).toBe("restaurant-lisbon");
    expect(hydratedState.isSending).toBe(false);
    expect(hydratedState.chatError).toBeNull();
    expect(hydratedState.authToken).toBe("token-123");
  });

  it("can persist a session id and then reset the conversation", () => {
    const state = useSessionStore.getState();

    state.setSessionId("session-persisted");
    expect(useSessionStore.getState().sessionId).toBe("session-persisted");

    state.resetConversation();
    expect(useSessionStore.getState().hasRemoteSession).toBe(false);
    expect(useSessionStore.getState().authToken).toBe(state.authToken);
  });

  it("stores saved recommendation snapshots once and clears workflow state on reset", () => {
    const state = useSessionStore.getState();

    state.setSessionId("session-workflow");
    state.saveRecommendation(
      {
        itemId: "hotel-1",
        itemType: "hotel",
        rank: 1,
        score: 0.91,
        explanation: "Near the beach",
        metadata: { name: "Harbor Hotel", city: "Lisbon" },
      },
      "session-workflow",
    );
    state.saveRecommendation(
      {
        itemId: "hotel-1",
        itemType: "hotel",
        rank: 1,
        metadata: { name: "Harbor Hotel" },
      },
      "session-workflow",
    );
    state.confirmBookingStub(
      {
        itemId: "hotel-1",
        itemType: "hotel",
        rank: 1,
        metadata: { name: "Harbor Hotel" },
      },
      "Harbor Hotel",
      "session-workflow",
    );

    expect(useSessionStore.getState().savedRecommendations).toHaveLength(1);
    expect(useSessionStore.getState().savedRecommendations[0]).toMatchObject({
      itemId: "hotel-1",
      score: 0.91,
      explanation: "Near the beach",
      sourceSessionId: "session-workflow",
    });
    expect(useSessionStore.getState().bookingConfirmation?.itemName).toBe(
      "Harbor Hotel",
    );

    state.resetConversation();

    expect(useSessionStore.getState().savedRecommendations).toHaveLength(0);
    expect(useSessionStore.getState().bookingConfirmation).toBeNull();
  });

  it("removing a saved item also clears its booking confirmation", () => {
    const state = useSessionStore.getState();

    state.saveRecommendation({
      itemId: "restaurant-1",
      itemType: "restaurant",
      rank: 1,
      metadata: { name: "Mesa" },
    });
    state.confirmBookingStub(
      {
        itemId: "restaurant-1",
        itemType: "restaurant",
        rank: 1,
        metadata: { name: "Mesa" },
      },
      "Mesa",
    );

    state.removeSavedRecommendation("restaurant-1");

    expect(useSessionStore.getState().savedRecommendations).toHaveLength(0);
    expect(useSessionStore.getState().bookingConfirmation).toBeNull();
  });
});
