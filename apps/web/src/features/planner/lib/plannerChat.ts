import type { Recommendation } from "../../../api/client";
import type { SessionMessage } from "../../../store/session";

export interface PendingRequest {
  message: string;
  messageId: string;
}

const LEGACY_SUGGESTION_CHIPS = [
  "Beach destinations in Europe under 1500 EUR",
  "City break ideas for 4 days in May",
  "Budget under EUR500",
  "Flights from Madrid to Lisbon next weekend",
  "Family-friendly destinations in June under 2000 USD",
  "Romantic weekend in Italy under 1200 EUR",
] as const;

export const SUGGESTION_CHIPS = [
  "Beach destinations in Europe under 1500 EUR",
  "City break ideas for 4 days in May",
  "Hotels in Lisbon next weekend under 1500 EUR",
  "Flights from Madrid to Lisbon next weekend",
  "Family-friendly destinations in June under 2000 USD",
  "Romantic weekend in Italy under 1200 EUR",
] as const;

void LEGACY_SUGGESTION_CHIPS;

export function getClientContext() {
  return {
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone ?? "UTC",
    locale: navigator.language || "en-US",
    currency: "USD",
  };
}

export function createMessageId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `${Date.now()}`;
  }
}

export function createMessage(
  role: SessionMessage["role"],
  content: string,
  id: string,
): SessionMessage {
  return {
    id,
    role,
    content,
    createdAt: new Date().toISOString(),
  };
}

export function stripTopPicksSegment(content: string): string {
  const marker = "top picks:";
  const markerIndex = content.toLowerCase().indexOf(marker);
  if (markerIndex === -1) {
    return content;
  }
  return content.slice(0, markerIndex).trim();
}

export function getRecommendationName(item: Recommendation): string {
  const name = item.metadata?.name;
  if (typeof name === "string" && name.trim()) {
    return name;
  }
  return item.itemId;
}
