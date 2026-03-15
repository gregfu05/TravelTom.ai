import { z } from "zod";

const API_BASE_URL = "/api/v1";

const healthResponseSchema = z.object({
  status: z.literal("ok"),
});

const apiErrorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.record(z.string(), z.unknown()).optional(),
    trace_id: z.string().optional(),
  }),
});

const recommendationSchema = z.object({
  item_id: z.string(),
  item_type: z.enum(["destination", "hotel", "flight"]),
  score: z.number(),
  rank: z.number(),
  explanation: z.string(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

const itinerarySchema = z.object({
  days: z.array(z.unknown()),
});

const chatResponseSchema = z.object({
  session_id: z.string(),
  message_id: z.string(),
  assistant_message: z.string(),
  recommendations: z.array(recommendationSchema).default([]),
  itinerary: itinerarySchema.optional(),
  state: z.record(z.string(), z.unknown()).optional(),
});

const authResponseSchema = z.object({
  token: z.string(),
});

type ApiErrorPayload = z.infer<typeof apiErrorSchema>;

export type HealthResponse = z.infer<typeof healthResponseSchema>;
export type ItemType = z.infer<typeof recommendationSchema>["item_type"];

export interface ClientContext {
  timezone: string;
  locale: string;
  currency: string;
}

export interface ChatRequest {
  sessionId: string;
  messageId: string;
  message: string;
  clientContext?: ClientContext;
}

export interface Recommendation {
  itemId: string;
  itemType: ItemType;
  score: number;
  rank: number;
  explanation: string;
  metadata?: Record<string, unknown>;
}

export interface ChatResponse {
  sessionId: string;
  messageId: string;
  assistantMessage: string;
  recommendations: Recommendation[];
  itinerary?: z.infer<typeof itinerarySchema>;
  state?: Record<string, unknown>;
}

export class ApiClientError extends Error {
  readonly status: number;
  readonly payload?: ApiErrorPayload;

  constructor(status: number, message: string, payload?: ApiErrorPayload) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.payload = payload;
  }
}

async function parseJsonSafely(response: Response): Promise<unknown | null> {
  const contentType = response.headers.get("content-type");
  if (!contentType || !contentType.includes("application/json")) {
    return null;
  }

  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function request<TSchema extends z.ZodTypeAny>(
  path: string,
  init: RequestInit,
  schema: TSchema,
): Promise<z.output<TSchema>> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...init.headers,
    },
    ...init,
  });

  const payload = await parseJsonSafely(response);

  if (!response.ok) {
    const parsedError = payload ? apiErrorSchema.safeParse(payload) : null;
    const message = parsedError?.success
      ? parsedError.data.error.message
      : `Request failed with status ${response.status}`;

    throw new ApiClientError(
      response.status,
      message,
      parsedError?.success ? parsedError.data : undefined,
    );
  }

  return schema.parse(payload);
}

function mapChatResponse(raw: z.output<typeof chatResponseSchema>): ChatResponse {
  return {
    sessionId: raw.session_id,
    messageId: raw.message_id,
    assistantMessage: raw.assistant_message,
    recommendations: raw.recommendations.map((item) => ({
      itemId: item.item_id,
      itemType: item.item_type,
      score: item.score,
      rank: item.rank,
      explanation: item.explanation,
      metadata: item.metadata,
    })),
    itinerary: raw.itinerary,
    state: raw.state,
  };
}

export const apiClient = {
  getHealth(signal?: AbortSignal): Promise<HealthResponse> {
    return request("/health", { method: "GET", signal }, healthResponseSchema);
  },

  async sendChatMessage(
    input: ChatRequest,
    signal?: AbortSignal,
  ): Promise<ChatResponse> {
    const payload = {
      session_id: input.sessionId,
      message_id: input.messageId,
      message: input.message,
      client_context: input.clientContext,
    };

    const response = await request(
      "/chat",
      {
        method: "POST",
        body: JSON.stringify(payload),
        signal,
      },
      chatResponseSchema,
    );

    return mapChatResponse(response);
  },

  async login(input: { email: string; password: string }): Promise<{ token: string }> {
    return request(
      "/auth/login",
      {
        method: "POST",
        body: JSON.stringify(input),
      },
      authResponseSchema,
    );
  },

  async signup(input: { email: string; password: string }): Promise<void> {
    await request(
      "/auth/signup",
      {
        method: "POST",
        body: JSON.stringify(input),
      },
      z.void(),
    );
  },
};
