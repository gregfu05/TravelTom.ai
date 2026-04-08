import { describe, expect, it } from "vitest";

import { parseApiErrorMetadata } from "./errorHandling";

describe("parseApiErrorMetadata", () => {
  it("classifies TravelTom-owned rate limits", () => {
    expect(
      parseApiErrorMetadata({
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
      }),
    ).toEqual({
      code: "rate_limit_exceeded",
      kind: "traveltom_rate_limit",
      message: "Chat rate limit exceeded",
      retryAfterSeconds: 23,
      traceId: "trace-123",
    });
  });

  it("classifies provider rate limits", () => {
    expect(
      parseApiErrorMetadata({
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
      }),
    ).toEqual({
      code: "provider_rate_limited",
      kind: "provider_rate_limit",
      message: "Upstream chat provider is rate limited",
      provider: "openai",
      retryAfterSeconds: undefined,
      traceId: "trace-456",
    });
  });
});
