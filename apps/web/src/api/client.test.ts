import assert from "node:assert/strict";

import { apiClient } from "./client.js";

const originalFetch = globalThis.fetch;

function installFetchMock(
  handler: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>,
) {
  globalThis.fetch = handler as typeof fetch;
}

function restoreFetch() {
  globalThis.fetch = originalFetch;
}

async function testSendChatMessageSerializesExactlyOnce() {
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

  try {
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
  } finally {
    restoreFetch();
  }

  assert.ok(capturedInit);
  assert.equal(capturedInit.method, "POST");
  assert.equal(capturedInit.headers instanceof Headers, false);
  assert.deepEqual(capturedInit.headers, {
    Accept: "application/json",
    Authorization: "Bearer token-123",
    "Content-Type": "application/json",
  });
  assert.equal(
    capturedInit.body,
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
  assert.doesNotMatch(String(capturedInit.body), /^".*"$/);
}

async function testLoginSerializesExactlyOnce() {
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

  try {
    await apiClient.login({
      email: "traveler@example.com",
      password: "password123",
    });
  } finally {
    restoreFetch();
  }

  assert.ok(capturedInit);
  assert.deepEqual(capturedInit.headers, {
    Accept: "application/json",
    "Content-Type": "application/json",
  });
  assert.equal(
    capturedInit.body,
    JSON.stringify({
      email: "traveler@example.com",
      password: "password123",
    }),
  );
  assert.doesNotMatch(String(capturedInit.body), /^".*"$/);
}

async function testSignupSerializesExactlyOnce() {
  let capturedInit: RequestInit | undefined;

  installFetchMock(async (_input, init) => {
    capturedInit = init;

    return new Response(
      JSON.stringify({
        access_token: "token-456",
        token_type: "bearer",
        expires_in: 3600,
        idle_timeout_in: 900,
        user: {
          id: "user-456",
          email: "new@example.com",
        },
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    );
  });

  try {
    await apiClient.signup({
      email: "new@example.com",
      password: "password123",
    });
  } finally {
    restoreFetch();
  }

  assert.ok(capturedInit);
  assert.deepEqual(capturedInit.headers, {
    Accept: "application/json",
    "Content-Type": "application/json",
  });
  assert.equal(
    capturedInit.body,
    JSON.stringify({
      email: "new@example.com",
      password: "password123",
    }),
  );
  assert.doesNotMatch(String(capturedInit.body), /^".*"$/);
}

async function testJsonHelperRejectsPreSerializedStringsInDevelopment() {
  let fetchCalled = false;

  installFetchMock(async () => {
    fetchCalled = true;
    throw new Error("fetch should not be called");
  });

  try {
    await assert.rejects(
      apiClient.login(
        JSON.stringify({
          email: "traveler@example.com",
          password: "password123",
        }) as unknown as {
          email: string;
          password: string;
        },
      ),
      (error: unknown) => {
        assert.equal(error instanceof TypeError, true);
        assert.match(
          (error as TypeError).message,
          /plain object body|pre-serialized JSON string/,
        );
        return true;
      },
    );
  } finally {
    restoreFetch();
  }

  assert.equal(fetchCalled, false);
}

await testSendChatMessageSerializesExactlyOnce();
await testLoginSerializesExactlyOnce();
await testSignupSerializesExactlyOnce();
await testJsonHelperRejectsPreSerializedStringsInDevelopment();

restoreFetch();
