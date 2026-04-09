import { afterEach, describe, expect, it } from "vitest";

import { apiClient } from "./client";

const originalFetch = globalThis.fetch;

function installFetchMock(
  handler: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>,
) {
  globalThis.fetch = handler as typeof fetch;
}

function restoreFetch() {
  globalThis.fetch = originalFetch;
}

describe("apiClient", () => {
  afterEach(() => {
    restoreFetch();
  });

  it("serializes chat requests exactly once", async () => {
    let capturedInit: RequestInit | undefined;

    installFetchMock(async (_input, init) => {
      capturedInit = init;

      return new Response(
        JSON.stringify({
          session_id: "session-123",
          message_id: "msg-001",
          assistant_message: "Hello back",
          recommendations: [],
          itinerary: { days: [] },
          state: {},
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    });

    await apiClient.sendChatMessage({
      sessionId: "session-123",
      messageId: "msg-001",
      message: "yo",
      clientContext: {
        timezone: "Europe/Paris",
        locale: "en-US",
        currency: "USD",
      },
      authToken: "token-123",
    });

    expect(capturedInit?.method).toBe("POST");
    expect(capturedInit?.headers).toEqual({
      Accept: "application/json",
      Authorization: "Bearer token-123",
      "Content-Type": "application/json",
    });
    expect(capturedInit?.body).toBe(
      JSON.stringify({
        session_id: "session-123",
        message_id: "msg-001",
        message: "yo",
        client_context: {
          timezone: "Europe/Paris",
          locale: "en-US",
          currency: "USD",
        },
      }),
    );
  });

  it("serializes login requests exactly once", async () => {
    let capturedInit: RequestInit | undefined;

    installFetchMock(async (_input, init) => {
      capturedInit = init;

      return new Response(
        JSON.stringify({
          access_token: "token-123",
          token_type: "bearer",
          expires_in: 3600,
          idle_timeout_in: 900,
          user: {
            id: "user-123",
            email: "traveler@example.com",
          },
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    });

    await apiClient.login({
      email: "traveler@example.com",
      password: "password123",
    });

    expect(capturedInit?.headers).toEqual({
      Accept: "application/json",
      "Content-Type": "application/json",
    });
    expect(capturedInit?.body).toBe(
      JSON.stringify({
        email: "traveler@example.com",
        password: "password123",
      }),
    );
  });

  it("maps persisted transcript and recommendations", async () => {
    let capturedInit: RequestInit | undefined;

    installFetchMock(async (_input, init) => {
      capturedInit = init;

      return new Response(
        JSON.stringify({
          session_id: "session-123",
          state: { status: "refine" },
          messages: [
            {
              id: "message-1",
              role: "user",
              content: "Hello",
              created_at: "2026-03-23T12:00:00Z",
            },
            {
              id: "message-2",
              role: "assistant",
              content: "Hi, I'm Tom.",
              created_at: "2026-03-23T12:00:01Z",
            },
          ],
          recommendations: [
            {
              item_id: "dest-lisbon",
              item_type: "destination",
              score: 0.93,
              rank: 1,
              explanation: "Excellent match for culture and food.",
              metadata: { name: "Lisbon" },
            },
          ],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    });

    const response = await apiClient.getChatSession({
      sessionId: "session-123",
      authToken: "token-123",
    });

    expect(response.sessionId).toBe("session-123");
    expect(response.messages[0]?.createdAt).toBe("2026-03-23T12:00:00Z");
    expect(response.recommendations[0]?.itemId).toBe("dest-lisbon");
    expect(response.recommendations[0]?.metadata).toEqual({ name: "Lisbon" });
    expect(capturedInit?.method).toBe("GET");
  });

  it("rejects pre-serialized string bodies in development", async () => {
    let fetchCalled = false;

    installFetchMock(async () => {
      fetchCalled = true;
      throw new Error("fetch should not be called");
    });

    await expect(
      apiClient.login(
        JSON.stringify({
          email: "traveler@example.com",
          password: "password123",
        }) as unknown as {
          email: string;
          password: string;
        },
      ),
    ).rejects.toThrow(/plain object body|pre-serialized JSON string/);

    expect(fetchCalled).toBe(false);
  });
});
