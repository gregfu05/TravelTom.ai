import assert from "node:assert/strict";
import { ApiClientError } from "../api/client.js";
import { buildChatErrorState, getCooldownRemainingSeconds, } from "./chatErrorState.js";
const travelTomError = new ApiClientError(429, {
    code: "rate_limit_exceeded",
    kind: "traveltom_rate_limit",
    message: "Chat rate limit exceeded",
    retryAfterSeconds: 15,
    traceId: "trace-abc",
});
const travelTomState = buildChatErrorState(travelTomError, 1_000);
assert.equal(travelTomState.kind, "traveltom_rate_limit");
assert.equal(travelTomState.cooldownUntilMs, 16_000);
assert.equal(travelTomState.actionLabel, "Retry last message");
assert.match(travelTomState.message, /15 seconds/);
assert.equal(travelTomState.traceId, "trace-abc");
assert.equal(getCooldownRemainingSeconds(travelTomState.cooldownUntilMs, 9_500), 7);
const providerError = new ApiClientError(429, {
    code: "provider_rate_limited",
    kind: "provider_rate_limit",
    message: "Upstream chat provider is rate limited",
    provider: "openai",
    traceId: "trace-def",
});
const providerState = buildChatErrorState(providerError, 2_000);
assert.equal(providerState.kind, "provider_rate_limit");
assert.equal(providerState.cooldownUntilMs, null);
assert.equal(providerState.actionLabel, null);
assert.match(providerState.message, /openai/i);
