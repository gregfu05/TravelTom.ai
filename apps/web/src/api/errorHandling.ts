import { z } from "zod";

export const apiErrorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.record(z.string(), z.unknown()).optional(),
    trace_id: z.string().optional(),
  }),
});

export type ApiErrorPayload = z.infer<typeof apiErrorSchema>;
export type ChatErrorKind =
  | "traveltom_rate_limit"
  | "provider_rate_limit"
  | "generic";

export interface ApiErrorMetadata {
  code?: string;
  kind: ChatErrorKind;
  message: string;
  provider?: string;
  retryAfterSeconds?: number;
  traceId?: string;
}

export function parseApiErrorMetadata(input: {
  status: number;
  payload?: unknown;
  retryAfterHeader?: string | null;
}): ApiErrorMetadata {
  const parsedError = input.payload
    ? apiErrorSchema.safeParse(input.payload)
    : undefined;
  const errorPayload = parsedError?.success ? parsedError.data.error : undefined;
  const message = errorPayload?.message ?? `Request failed with status ${input.status}`;
  const details = errorPayload?.details;
  const retryAfterSeconds =
    parseRetryAfterSeconds(details?.retry_after_seconds) ??
    parseRetryAfterHeader(input.retryAfterHeader);
  const code = errorPayload?.code;

  if (input.status === 429 && code === "rate_limit_exceeded") {
    return {
      code,
      kind: "traveltom_rate_limit",
      message,
      retryAfterSeconds,
      traceId: errorPayload?.trace_id,
    };
  }

  if (input.status === 429 && code === "provider_rate_limited") {
    return {
      code,
      kind: "provider_rate_limit",
      message,
      provider:
        typeof details?.provider === "string" ? details.provider : undefined,
      retryAfterSeconds,
      traceId: errorPayload?.trace_id,
    };
  }

  return {
    code,
    kind: "generic",
    message,
    traceId: errorPayload?.trace_id,
  };
}

function parseRetryAfterSeconds(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.max(0, Math.trunc(value));
  }
  if (typeof value === "string" && /^\d+$/.test(value)) {
    return Math.max(0, Number.parseInt(value, 10));
  }
  return undefined;
}

function parseRetryAfterHeader(value: string | null | undefined): number | undefined {
  if (!value) {
    return undefined;
  }

  const trimmed = value.trim();
  if (/^\d+$/.test(trimmed)) {
    return Math.max(0, Number.parseInt(trimmed, 10));
  }

  const retryAt = Date.parse(trimmed);
  if (Number.isNaN(retryAt)) {
    return undefined;
  }

  return Math.max(0, Math.ceil((retryAt - Date.now()) / 1000));
}
