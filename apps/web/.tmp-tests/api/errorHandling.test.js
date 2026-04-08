import assert from "node:assert/strict";
import { parseApiErrorMetadata } from "./errorHandling.js";
const travelTomMetadata = parseApiErrorMetadata({
    status: 429,
    payload: {
        error: {
            code: "rate_limit_exceeded",
            message: "Chat rate limit exceeded",
            details: {
                retry_after_seconds: 23,
                source: "traveltom",
            },
            trace_id: "trace-123",
        },
    },
    retryAfterHeader: "19",
});
assert.deepEqual(travelTomMetadata, {
    code: "rate_limit_exceeded",
    kind: "traveltom_rate_limit",
    message: "Chat rate limit exceeded",
    retryAfterSeconds: 23,
    traceId: "trace-123",
});
const providerMetadata = parseApiErrorMetadata({
    status: 429,
    payload: {
        error: {
            code: "provider_rate_limited",
            message: "Upstream chat provider is rate limited",
            details: {
                provider: "openai",
            },
            trace_id: "trace-456",
        },
    },
    retryAfterHeader: null,
});
assert.deepEqual(providerMetadata, {
    code: "provider_rate_limited",
    kind: "provider_rate_limit",
    message: "Upstream chat provider is rate limited",
    provider: "openai",
    retryAfterSeconds: undefined,
    traceId: "trace-456",
});
