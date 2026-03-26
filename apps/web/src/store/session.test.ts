import assert from "node:assert/strict";

const storage = new Map<string, string>();

Object.defineProperty(globalThis, "localStorage", {
  value: {
    getItem(key: string) {
      return storage.has(key) ? storage.get(key)! : null;
    },
    setItem(key: string, value: string) {
      storage.set(key, value);
    },
    removeItem(key: string) {
      storage.delete(key);
    },
  },
  configurable: true,
});

const { useSessionStore } = await import("./session.js");

useSessionStore.setState({
  sessionId: "session-initial",
  hasRemoteSession: false,
  messages: [],
  latestRecommendations: [],
  isSending: false,
  chatError: { kind: "provider_rate_limit", message: "Busy", cooldownUntilMs: null, actionLabel: null },
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
      itemId: "dest-lisbon",
      itemType: "destination",
      score: 0.93,
      rank: 1,
      explanation: "Excellent match for culture and food.",
      metadata: { name: "Lisbon" },
    },
  ],
});

const hydratedState = useSessionStore.getState();

assert.equal(hydratedState.sessionId, "session-restored");
assert.equal(hydratedState.hasRemoteSession, true);
assert.equal(hydratedState.messages.length, 2);
assert.equal(hydratedState.latestRecommendations[0].itemId, "dest-lisbon");
assert.equal(hydratedState.isSending, false);
assert.equal(hydratedState.chatError, null);
assert.equal(hydratedState.authToken, "token-123");

hydratedState.setSessionId("session-persisted");
assert.equal(useSessionStore.getState().sessionId, "session-persisted");
hydratedState.resetConversation();
assert.equal(useSessionStore.getState().hasRemoteSession, false);
