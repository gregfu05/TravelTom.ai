import { z } from "zod";

import {
  ApiErrorMetadata,
  ApiErrorPayload,
  apiErrorSchema,
  parseApiErrorMetadata,
} from "./errorHandling.js";

const API_BASE_URL = "/api/v1";

const healthResponseSchema = z.object({
  status: z.literal("ok"),
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

const chatSessionMessageSchema = z.object({
  id: z.string(),
  role: z.enum(["user", "assistant"]),
  content: z.string(),
  created_at: z.string(),
});

const chatSessionResponseSchema = z.object({
  session_id: z.string(),
  state: z.record(z.string(), z.unknown()),
  messages: z.array(chatSessionMessageSchema).default([]),
  recommendations: z.array(recommendationSchema).default([]),
});

const authResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.literal("bearer"),
  expires_in: z.number(),
  idle_timeout_in: z.number(),
  user: z.object({
    id: z.string(),
    email: z.string(),
  }),
});

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
  authToken?: string;
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

export interface ChatSessionMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
}

export interface ChatSessionResponse {
  sessionId: string;
  state: Record<string, unknown>;
  messages: ChatSessionMessage[];
  recommendations: Recommendation[];
}

export interface AuthSession {
  accessToken: string;
  tokenType: "bearer";
  expiresIn: number;
  idleTimeoutIn: number;
  user: {
    id: string;
    email: string;
  };
}

export class ApiClientError extends Error {
  readonly status: number;
  readonly metadata: ApiErrorMetadata;
  readonly payload?: ApiErrorPayload;

  constructor(status: number, metadata: ApiErrorMetadata, payload?: ApiErrorPayload) {
    super(metadata.message);
    this.name = "ApiClientError";
    this.status = status;
    this.metadata = metadata;
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
  const { headers, ...rest } = init;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...headers,
    },
  });

  const payload = await parseJsonSafely(response);

  if (!response.ok) {
    const parsedError = payload ? apiErrorSchema.safeParse(payload) : null;
    const metadata = parseApiErrorMetadata({
      status: response.status,
      payload,
      retryAfterHeader: response.headers.get("Retry-After"),
    });

    throw new ApiClientError(
      response.status,
      metadata,
      parsedError?.success ? parsedError.data : undefined,
    );
  }

  return schema.parse(payload);
}

function shouldGuardJsonBody(): boolean {
  if (typeof import.meta.env.DEV === "boolean") {
    return import.meta.env.DEV;
  }

  if (typeof import.meta.env.MODE === "string") {
    return import.meta.env.MODE !== "production";
  }

  return true;
}

function requestJson<TSchema extends z.ZodTypeAny>(
  path: string,
  init: Omit<RequestInit, "body"> & { body?: unknown },
  schema: TSchema,
): Promise<z.output<TSchema>> {
  const { body, headers, ...rest } = init;

  if (typeof body === "string" && shouldGuardJsonBody()) {
    throw new TypeError(
      "requestJson expected a plain object body. Pass structured data instead of a pre-serialized JSON string.",
    );
  }

  return request(
    path,
    {
      ...rest,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    },
    schema,
  );
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

function mapAuthSession(raw: z.output<typeof authResponseSchema>): AuthSession {
  return {
    accessToken: raw.access_token,
    tokenType: raw.token_type,
    expiresIn: raw.expires_in,
    idleTimeoutIn: raw.idle_timeout_in,
    user: raw.user,
  };
}

function mapChatSessionResponse(
  raw: z.output<typeof chatSessionResponseSchema>,
): ChatSessionResponse {
  return {
    sessionId: raw.session_id,
    state: raw.state,
    messages: raw.messages.map((message) => ({
      id: message.id,
      role: message.role,
      content: message.content,
      createdAt: message.created_at,
    })),
    recommendations: raw.recommendations.map((item) => ({
      itemId: item.item_id,
      itemType: item.item_type,
      score: item.score,
      rank: item.rank,
      explanation: item.explanation,
      metadata: item.metadata,
    })),
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

    const response = await requestJson(
      "/chat",
      {
        method: "POST",
        body: payload,
        headers: input.authToken
          ? { Authorization: `Bearer ${input.authToken}` }
          : undefined,
        signal,
      },
      chatResponseSchema,
    );

    return mapChatResponse(response);
  },

  async getChatSession(
    input: { sessionId: string; authToken?: string },
    signal?: AbortSignal,
  ): Promise<ChatSessionResponse> {
    const response = await request(
      `/chat/${encodeURIComponent(input.sessionId)}`,
      {
        method: "GET",
        headers: input.authToken
          ? { Authorization: `Bearer ${input.authToken}` }
          : undefined,
        signal,
      },
      chatSessionResponseSchema,
    );

    return mapChatSessionResponse(response);
  },

  async login(input: {
    email: string;
    password: string;
  }): Promise<AuthSession> {
    const response = await requestJson(
      "/auth/login",
      {
        method: "POST",
        body: input,
      },
      authResponseSchema,
    );

    return mapAuthSession(response);
  },

  async signup(input: {
    email: string;
    password: string;
  }): Promise<AuthSession> {
    const response = await requestJson(
      "/auth/signup",
      {
        method: "POST",
        body: input,
      },
      authResponseSchema,
    );

    return mapAuthSession(response);
  },

  async logout(authToken: string): Promise<void> {
    await request(
      "/auth/logout",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      },
      z.null().transform(() => undefined),
    );
  },
};
