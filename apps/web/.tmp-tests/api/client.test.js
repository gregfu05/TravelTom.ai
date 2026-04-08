import assert from "node:assert/strict";
import { apiClient } from "./client.js";
const originalFetch = globalThis.fetch;
function installFetchMock(handler) {
    globalThis.fetch = handler;
}
function restoreFetch() {
    globalThis.fetch = originalFetch;
}
async function testSendChatMessageSerializesExactlyOnce() {
    let capturedInit;
    installFetchMock(async (_input, init) => {
        capturedInit = init;
        return new Response(JSON.stringify({
            session_id: "session-123",
            message_id: "msg-001",
            assistant_message: "Hello back",
            recommendations: [],
            itinerary: { days: [] },
            state: {},
        }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
        });
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
    }
    finally {
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
    assert.equal(capturedInit.body, JSON.stringify({
        session_id: "session-123",
        message_id: "msg-001",
        message: "yo",
        client_context: {
            timezone: "Europe/Paris",
            locale: "en-US",
            currency: "USD",
        },
    }));
    assert.doesNotMatch(String(capturedInit.body), /^".*"$/);
}
async function testLoginSerializesExactlyOnce() {
    let capturedInit;
    installFetchMock(async (_input, init) => {
        capturedInit = init;
        return new Response(JSON.stringify({
            access_token: "token-123",
            token_type: "bearer",
            expires_in: 3600,
            idle_timeout_in: 900,
            user: {
                id: "user-123",
                email: "traveler@example.com",
            },
        }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
        });
    });
    try {
        await apiClient.login({
            email: "traveler@example.com",
            password: "password123",
        });
    }
    finally {
        restoreFetch();
    }
    assert.ok(capturedInit);
    assert.deepEqual(capturedInit.headers, {
        Accept: "application/json",
        "Content-Type": "application/json",
    });
    assert.equal(capturedInit.body, JSON.stringify({
        email: "traveler@example.com",
        password: "password123",
    }));
    assert.doesNotMatch(String(capturedInit.body), /^".*"$/);
}
async function testSignupSerializesExactlyOnce() {
    let capturedInit;
    installFetchMock(async (_input, init) => {
        capturedInit = init;
        return new Response(JSON.stringify({
            access_token: "token-456",
            token_type: "bearer",
            expires_in: 3600,
            idle_timeout_in: 900,
            user: {
                id: "user-456",
                email: "new@example.com",
            },
        }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
        });
    });
    try {
        await apiClient.signup({
            email: "new@example.com",
            password: "password123",
        });
    }
    finally {
        restoreFetch();
    }
    assert.ok(capturedInit);
    assert.deepEqual(capturedInit.headers, {
        Accept: "application/json",
        "Content-Type": "application/json",
    });
    assert.equal(capturedInit.body, JSON.stringify({
        email: "new@example.com",
        password: "password123",
    }));
    assert.doesNotMatch(String(capturedInit.body), /^".*"$/);
}
async function testGetChatSessionMapsPersistedTranscriptAndRecommendations() {
    let capturedInit;
    installFetchMock(async (_input, init) => {
        capturedInit = init;
        return new Response(JSON.stringify({
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
        }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
        });
    });
    try {
        const response = await apiClient.getChatSession({
            sessionId: "session-123",
            authToken: "token-123",
        });
        assert.equal(response.sessionId, "session-123");
        assert.equal(response.messages[0].createdAt, "2026-03-23T12:00:00Z");
        assert.equal(response.recommendations[0].itemId, "dest-lisbon");
        assert.deepEqual(response.recommendations[0].metadata, { name: "Lisbon" });
    }
    finally {
        restoreFetch();
    }
    assert.ok(capturedInit);
    assert.equal(capturedInit.method, "GET");
    assert.deepEqual(capturedInit.headers, {
        Accept: "application/json",
        Authorization: "Bearer token-123",
        "Content-Type": "application/json",
    });
}
async function testJsonHelperRejectsPreSerializedStringsInDevelopment() {
    let fetchCalled = false;
    installFetchMock(async () => {
        fetchCalled = true;
        throw new Error("fetch should not be called");
    });
    try {
        await assert.rejects(apiClient.login(JSON.stringify({
            email: "traveler@example.com",
            password: "password123",
        })), (error) => {
            assert.equal(error instanceof TypeError, true);
            assert.match(error.message, /plain object body|pre-serialized JSON string/);
            return true;
        });
    }
    finally {
        restoreFetch();
    }
    assert.equal(fetchCalled, false);
}
await testSendChatMessageSerializesExactlyOnce();
await testLoginSerializesExactlyOnce();
await testSignupSerializesExactlyOnce();
await testGetChatSessionMapsPersistedTranscriptAndRecommendations();
await testJsonHelperRejectsPreSerializedStringsInDevelopment();
restoreFetch();
