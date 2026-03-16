import { ApiClientError } from "../api/client.js";

export interface ChatErrorState {
  actionLabel: string | null;
  cooldownUntilMs: number | null;
  kind: "traveltom_rate_limit" | "provider_rate_limit" | "generic";
  message: string;
  traceId?: string;
}

export function buildChatErrorState(
  error: unknown,
  nowMs: number = Date.now(),
): ChatErrorState {
  if (error instanceof ApiClientError) {
    if (error.metadata.kind === "traveltom_rate_limit") {
      const retryAfterSeconds = error.metadata.retryAfterSeconds ?? 0;
      const cooldownUntilMs = nowMs + retryAfterSeconds * 1000;
      return {
        actionLabel: "Retry last message",
        cooldownUntilMs,
        kind: "traveltom_rate_limit",
        message:
          retryAfterSeconds > 0
            ? `TravelTom is cooling down. Retry this chat message in about ${retryAfterSeconds} second${retryAfterSeconds === 1 ? "" : "s"}.`
            : "TravelTom is cooling down. Retry this chat message shortly.",
        traceId: error.metadata.traceId,
      };
    }

    if (error.metadata.kind === "provider_rate_limit") {
      const providerName = error.metadata.provider
        ? `${error.metadata.provider} `
        : "";
      return {
        actionLabel: null,
        cooldownUntilMs: null,
        kind: "provider_rate_limit",
        message: `The ${providerName}chat provider is quota-limited right now. Try again later or switch providers.`,
        traceId: error.metadata.traceId,
      };
    }

    if (error.status === 404) {
      return {
        actionLabel: "Retry last message",
        cooldownUntilMs: null,
        kind: "generic",
        message:
          "Chat endpoint is not available yet. Start the backend service or implement /api/v1/chat.",
        traceId: error.metadata.traceId,
      };
    }

    return {
      actionLabel: "Retry last message",
      cooldownUntilMs: null,
      kind: "generic",
      message: error.message,
      traceId: error.metadata.traceId,
    };
  }

  if (error instanceof Error) {
    return {
      actionLabel: "Retry last message",
      cooldownUntilMs: null,
      kind: "generic",
      message: error.message,
    };
  }

  return {
    actionLabel: "Retry last message",
    cooldownUntilMs: null,
    kind: "generic",
    message: "Something went wrong while sending your message.",
  };
}

export function getCooldownRemainingSeconds(
  cooldownUntilMs: number | null,
  nowMs: number = Date.now(),
): number {
  if (cooldownUntilMs === null) {
    return 0;
  }

  return Math.max(0, Math.ceil((cooldownUntilMs - nowMs) / 1000));
}
