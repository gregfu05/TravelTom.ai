import { ChatSessionResponse } from "../api/client.js";

const TRIVIAL_GREETING_PATTERN =
  /^\s*(?:hello|hi|hey|yo|howdy|greetings)\b(?:[\s,.!?:-]*(?:tom|travel\s*tom|traveltom))?[\s,.!?:-]*$/i;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasMeaningfulValue(value: unknown): boolean {
  if (value === null || value === undefined) {
    return false;
  }

  if (typeof value === "string") {
    return value.trim().length > 0;
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return true;
  }

  if (Array.isArray(value)) {
    return value.some((item) => hasMeaningfulValue(item));
  }

  if (isRecord(value)) {
    return Object.values(value).some((item) => hasMeaningfulValue(item));
  }

  return false;
}

function hasMeaningfulState(state: Record<string, unknown>): boolean {
  const constraints = state.constraints;
  if (isRecord(constraints)) {
    if (
      hasMeaningfulValue(constraints.origin) ||
      hasMeaningfulValue(constraints.destination) ||
      hasMeaningfulValue(constraints.dates) ||
      hasMeaningfulValue(constraints.trip_length_days) ||
      hasMeaningfulValue(constraints.budget) ||
      hasMeaningfulValue(constraints.party_size)
    ) {
      return true;
    }
  }

  const preferences = state.preferences;
  if (isRecord(preferences)) {
    if (
      hasMeaningfulValue(preferences.weighted_interests) ||
      hasMeaningfulValue(preferences.dislikes)
    ) {
      return true;
    }
  }

  const entities = state.entities;
  if (isRecord(entities) && hasMeaningfulValue(entities.destinations)) {
    return true;
  }

  const conversation = state.conversation;
  if (isRecord(conversation)) {
    if (
      hasMeaningfulValue(conversation.last_recommendation_item_type) ||
      hasMeaningfulValue(conversation.last_recommendation_query) ||
      hasMeaningfulValue(conversation.last_recommendation_result_ids)
    ) {
      return true;
    }
  }

  return hasMeaningfulValue(state.last_recommendation_version);
}

export function shouldDiscardHydratedSession(
  session: Pick<ChatSessionResponse, "messages" | "recommendations" | "state">,
): boolean {
  if (session.recommendations.length > 0) {
    return false;
  }

  if (session.messages.length === 0 || session.messages.length > 2) {
    return false;
  }

  if (hasMeaningfulState(session.state)) {
    return false;
  }

  const userMessages = session.messages.filter(
    (message: ChatSessionResponse["messages"][number]) => message.role === "user",
  );
  if (userMessages.length !== 1) {
    return false;
  }

  return TRIVIAL_GREETING_PATTERN.test(userMessages[0]?.content ?? "");
}
