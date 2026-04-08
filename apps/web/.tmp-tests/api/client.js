import { z } from "zod";
import { apiErrorSchema, parseApiErrorMetadata, } from "./errorHandling.js";
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
export class ApiClientError extends Error {
    status;
    metadata;
    payload;
    constructor(status, metadata, payload) {
        super(metadata.message);
        this.name = "ApiClientError";
        this.status = status;
        this.metadata = metadata;
        this.payload = payload;
    }
}
async function parseJsonSafely(response) {
    const contentType = response.headers.get("content-type");
    if (!contentType || !contentType.includes("application/json")) {
        return null;
    }
    try {
        return await response.json();
    }
    catch {
        return null;
    }
}
async function request(path, init, schema) {
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
        throw new ApiClientError(response.status, metadata, parsedError?.success ? parsedError.data : undefined);
    }
    return schema.parse(payload);
}
function shouldGuardJsonBody() {
    const viteDevFlag = import.meta.env?.DEV;
    if (typeof viteDevFlag === "boolean") {
        return viteDevFlag;
    }
    if (typeof process !== "undefined") {
        return process.env.NODE_ENV !== "production";
    }
    return true;
}
function requestJson(path, init, schema) {
    const { body, headers, ...rest } = init;
    if (typeof body === "string" && shouldGuardJsonBody()) {
        throw new TypeError("requestJson expected a plain object body. Pass structured data instead of a pre-serialized JSON string.");
    }
    return request(path, {
        ...rest,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
    }, schema);
}
function mapChatResponse(raw) {
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
function mapAuthSession(raw) {
    return {
        accessToken: raw.access_token,
        tokenType: raw.token_type,
        expiresIn: raw.expires_in,
        idleTimeoutIn: raw.idle_timeout_in,
        user: raw.user,
    };
}
function mapChatSessionResponse(raw) {
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
    getHealth(signal) {
        return request("/health", { method: "GET", signal }, healthResponseSchema);
    },
    async sendChatMessage(input, signal) {
        const payload = {
            session_id: input.sessionId,
            message_id: input.messageId,
            message: input.message,
            client_context: input.clientContext,
        };
        const response = await requestJson("/chat", {
            method: "POST",
            body: payload,
            headers: input.authToken
                ? { Authorization: `Bearer ${input.authToken}` }
                : undefined,
            signal,
        }, chatResponseSchema);
        return mapChatResponse(response);
    },
    async getChatSession(input, signal) {
        const response = await request(`/chat/${encodeURIComponent(input.sessionId)}`, {
            method: "GET",
            headers: input.authToken
                ? { Authorization: `Bearer ${input.authToken}` }
                : undefined,
            signal,
        }, chatSessionResponseSchema);
        return mapChatSessionResponse(response);
    },
    async login(input) {
        const response = await requestJson("/auth/login", {
            method: "POST",
            body: input,
        }, authResponseSchema);
        return mapAuthSession(response);
    },
    async signup(input) {
        const response = await requestJson("/auth/signup", {
            method: "POST",
            body: input,
        }, authResponseSchema);
        return mapAuthSession(response);
    },
    async logout(authToken) {
        await request("/auth/logout", {
            method: "POST",
            headers: {
                Authorization: `Bearer ${authToken}`,
            },
        }, z.null().transform(() => undefined));
    },
};
