import type { KeyboardEvent } from "react";

import type { Recommendation } from "../../../api/client";
import type { SessionMessage } from "../../../store/session";
import {
  getRecommendationName,
  SUGGESTION_CHIPS,
  stripTopPicksSegment,
} from "../lib/plannerChat";

interface PlannerConversationProps {
  avatarClass: string;
  isSending: boolean;
  latestAssistantMessageId?: string;
  messages: SessionMessage[];
  onSuggestionSelect: (chip: string) => void;
  recommendations: Recommendation[];
}

export function PlannerConversation({
  avatarClass,
  isSending,
  latestAssistantMessageId,
  messages,
  onSuggestionSelect,
  recommendations,
}: PlannerConversationProps) {
  return (
    <div
      className="chat-thread"
      role="log"
      aria-live="polite"
      aria-relevant="additions text"
    >
      {messages.length === 0 ? (
        <div className="chat-welcome">
          <div className={`chat-welcome-avatar ${avatarClass}`} aria-hidden="true">
            <svg
              viewBox="0 0 24 24"
              width="44"
              height="44"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="3" y="4" width="18" height="14" rx="3" />
              <circle cx="9" cy="11" r="1.4" fill="currentColor" stroke="none" />
              <circle cx="15" cy="11" r="1.4" fill="currentColor" stroke="none" />
              <path d="M2 8h2M20 8h2M9 18v2M15 18v2" />
            </svg>
          </div>
          <h2 className="chat-welcome-heading">Start with a trip idea</h2>
          <p className="chat-welcome-sub">
            Share a destination, then add dates for hotels, or jump straight
            into restaurants and activities for a place you already have in
            mind. Add budget when you want tighter hotel price filtering.
          </p>
          <div className="suggestion-chips">
            {SUGGESTION_CHIPS.map((chip) => (
              <button
                key={chip}
                className="suggestion-chip"
                type="button"
                onClick={() => onSuggestionSelect(chip)}
              >
                {chip}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {messages.map((message) => {
        const isLatestAssistantMessage =
          message.role === "assistant" && message.id === latestAssistantMessageId;
        const shouldRenderRecommendationSummary =
          isLatestAssistantMessage && recommendations.length > 0;
        const primaryMessage = shouldRenderRecommendationSummary
          ? stripTopPicksSegment(message.content)
          : message.content;
        const displayMessage =
          primaryMessage || "I found recommendations that match your request.";

        return (
          <article
            key={message.id}
            className={`chat-message chat-message-${message.role}`}
          >
            <p className="chat-message-role">
              {message.role === "assistant" ? "TravelTom" : "You"}
            </p>
            <p className="chat-message-content">{displayMessage}</p>
            {shouldRenderRecommendationSummary ? (
              <section className="chat-message-recommendation-block">
                <div className="chat-message-divider" aria-hidden="true" />
                <p className="chat-message-list-title">Recommended options</p>
                <ol
                  className="chat-message-recommendation-list"
                  aria-label="Top recommendations"
                >
                  {recommendations.map((item) => {
                    const mapUrl =
                      typeof item.metadata?.map_url === "string"
                        ? item.metadata.map_url
                        : undefined;

                    return (
                      <li
                        key={`summary-${item.itemId}-${item.rank}`}
                        className="chat-message-recommendation-item"
                      >
                        <span className="chat-message-recommendation-name">
                          {getRecommendationName(item)}
                        </span>
                        {mapUrl ? (
                          <a
                            href={mapUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="chat-message-map-link"
                          >
                            View on map
                          </a>
                        ) : null}
                      </li>
                    );
                  })}
                </ol>
              </section>
            ) : null}
          </article>
        );
      })}

      {isSending ? (
        <article className="chat-message chat-message-assistant chat-message-loading">
          <p className="chat-message-role">Tom</p>
          <div className="typing-indicator" aria-label="Tom is typing">
            <span />
            <span />
            <span />
          </div>
        </article>
      ) : null}
    </div>
  );
}

export function handleComposerKeyDown(
  event: KeyboardEvent<HTMLTextAreaElement>,
  options: {
    draft: string;
    isSending: boolean;
    isTravelTomCooldownActive: boolean;
    isHydrating: boolean;
    onSubmit: () => void;
  },
) {
  if (event.key !== "Enter" || event.shiftKey) {
    return;
  }

  event.preventDefault();
  if (
    !options.draft.trim() ||
    options.isSending ||
    options.isTravelTomCooldownActive ||
    options.isHydrating
  ) {
    return;
  }

  options.onSubmit();
}
