import { describe, expect, it } from "vitest";

import { ApiClientError } from "../api/client";
import {
  buildChatErrorState,
  getCooldownRemainingSeconds,
} from "./chatErrorState";

describe("chatErrorState", () => {
  it("builds a TravelTom cooldown state", () => {
    const travelTomError = new ApiClientError(429, {
      code: "rate_limit_exceeded",
      kind: "traveltom_rate_limit",
      message: "Chat rate limit exceeded",
      retryAfterSeconds: 15,
      traceId: "trace-abc",
    });

    const state = buildChatErrorState(travelTomError, 1_000);

    expect(state.kind).toBe("traveltom_rate_limit");
    expect(state.cooldownUntilMs).toBe(16_000);
    expect(state.actionLabel).toBe("Retry last message");
    expect(state.message).toContain("15 seconds");
    expect(state.traceId).toBe("trace-abc");
    expect(getCooldownRemainingSeconds(state.cooldownUntilMs, 9_500)).toBe(7);
  });

  it("builds a provider rate-limit state", () => {
    const providerError = new ApiClientError(429, {
      code: "provider_rate_limited",
      kind: "provider_rate_limit",
      message: "Upstream chat provider is rate limited",
      provider: "openai",
      traceId: "trace-def",
    });

    const state = buildChatErrorState(providerError, 2_000);

    expect(state.kind).toBe("provider_rate_limit");
    expect(state.cooldownUntilMs).toBeNull();
    expect(state.actionLabel).toBeNull();
    expect(state.message).toContain("openai");
  });
});
