import assert from "node:assert/strict";

import { shouldDiscardHydratedSession } from "./sessionHydration.js";

assert.equal(
  shouldDiscardHydratedSession({
    messages: [
      {
        id: "message-1",
        role: "user",
        content: "Hello Tom",
        createdAt: "2026-03-23T12:00:00Z",
      },
      {
        id: "message-2",
        role: "assistant",
        content: "What destination should I focus on?",
        createdAt: "2026-03-23T12:00:01Z",
      },
    ],
    recommendations: [],
    state: {
      conversation: {
        last_requested_slots: ["destination"],
        last_user_intent: "recommend",
      },
    },
  }),
  true,
);

assert.equal(
  shouldDiscardHydratedSession({
    messages: [
      {
        id: "message-1",
        role: "user",
        content: "Hello Tom",
        createdAt: "2026-03-23T12:00:00Z",
      },
      {
        id: "message-2",
        role: "assistant",
        content: "What travel dates should I plan around?",
        createdAt: "2026-03-23T12:00:01Z",
      },
    ],
    recommendations: [],
    state: {
      constraints: {
        destination: "Lisbon",
      },
      conversation: {
        last_requested_slots: ["dates"],
        last_recommendation_item_type: "hotel",
        last_recommendation_query: "recommend hotels",
      },
    },
  }),
  false,
);

assert.equal(
  shouldDiscardHydratedSession({
    messages: [
      {
        id: "message-1",
        role: "user",
        content: "Hello Tom",
        createdAt: "2026-03-23T12:00:00Z",
      },
    ],
    recommendations: [
      {
        itemId: "hotel-1",
        itemType: "hotel",
        score: 0.95,
        rank: 1,
        explanation: "Great fit.",
      },
    ],
    state: {},
  }),
  false,
);
