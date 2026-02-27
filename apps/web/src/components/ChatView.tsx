import { FormEvent, useEffect, useState } from "react";

import { ApiClientError, apiClient, type Recommendation } from "../api/client";
import { SessionMessage, useSessionStore } from "../store/session";

interface PendingRequest {
  message: string;
  messageId: string;
}

function getClientContext() {
  return {
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone ?? "UTC",
    locale: navigator.language || "en-US",
    currency: "USD",
  };
}

function createMessageId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `${Date.now()}`;
  }
}

function createMessage(
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

function stripTopPicksSegment(content: string): string {
  const marker = "top picks:";
  const markerIndex = content.toLowerCase().indexOf(marker);
  if (markerIndex === -1) {
    return content;
  }
  return content.slice(0, markerIndex).trim();
}

function getRecommendationName(item: Recommendation): string {
  const name = item.metadata?.name;
  if (typeof name === "string" && name.trim()) {
    return name;
  }
  return item.itemId;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    if (error.status === 404) {
      return "Chat endpoint is not available yet. Start the backend service or implement /api/v1/chat.";
    }
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Something went wrong while sending your message.";
}

export function ChatView() {
  const {
    sessionId,
    messages,
    isSending,
    errorMessage,
    latestRecommendations,
    setSessionId,
    addMessage,
    setLatestRecommendations,
    setIsSending,
    setErrorMessage,
    resetConversation,
  } = useSessionStore();

  const [draft, setDraft] = useState("");
  const [pendingRequest, setPendingRequest] = useState<PendingRequest | null>(
    null,
  );
  const [isRecommendationsCollapsed, setIsRecommendationsCollapsed] =
    useState(false);

  const hasRecommendations = latestRecommendations.length > 0;
  const topRecommendations = latestRecommendations.slice(0, 5);
  const latestAssistantMessageId = [...messages]
    .reverse()
    .find((item) => item.role === "assistant")?.id;

  useEffect(() => {
    if (!hasRecommendations) {
      setIsRecommendationsCollapsed(false);
    }
  }, [hasRecommendations]);

  async function sendMessage(
    rawMessage: string,
    options?: { appendUserMessage?: boolean; messageId?: string },
  ) {
    const message = rawMessage.trim();
    if (!message || isSending) {
      return;
    }

    const messageId = options?.messageId ?? createMessageId();

    setErrorMessage(null);
    setIsSending(true);
    setPendingRequest({ message, messageId });

    if (options?.appendUserMessage ?? true) {
      addMessage(createMessage("user", message, messageId));
    }

    try {
      const response = await apiClient.sendChatMessage({
        sessionId,
        messageId,
        message,
        clientContext: getClientContext(),
      });

      setSessionId(response.sessionId);
      addMessage(
        createMessage(
          "assistant",
          response.assistantMessage,
          response.messageId || createMessageId(),
        ),
      );
      setLatestRecommendations(response.recommendations);
      setPendingRequest(null);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setIsSending(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message) {
      return;
    }
    setDraft("");
    void sendMessage(message, { appendUserMessage: true });
  }

  function handleRetry() {
    if (!pendingRequest || isSending) {
      return;
    }
    void sendMessage(pendingRequest.message, {
      appendUserMessage: false,
      messageId: pendingRequest.messageId,
    });
  }

  return (
    <section className="chat-view">
      <div className="chat-view-header">
        <div>
          <p className="eyebrow">Planner Chat</p>
          <h2>Describe your trip and refine options in real time</h2>
        </div>
        <div className="chat-header-actions">
          <p className="session-pill">Session {sessionId.slice(0, 12)}</p>
          <button
            className="button button-ghost button-xs"
            onClick={resetConversation}
            type="button"
          >
            New Session
          </button>
        </div>
      </div>

      <div
        className={`chat-layout ${hasRecommendations ? "chat-layout-with-recommendations" : ""}`}
      >
        <div
          className={`chat-main-column ${hasRecommendations ? "chat-main-column-with-recommendations" : ""}`}
        >
          <div
            className="chat-thread"
            role="log"
            aria-live="polite"
            aria-relevant="additions text"
          >
            {messages.length === 0 ? (
              <article className="chat-empty">
                <h3>Start with your destination goals</h3>
                <p>
                  Example: 7-day trip from NYC in June, budget 2,500 USD,
                  prefers coastal cities and boutique hotels.
                </p>
              </article>
            ) : null}

            {messages.map((message) => {
              const isLatestAssistantMessage =
                message.role === "assistant" &&
                message.id === latestAssistantMessageId;
              const shouldRenderRecommendationSummary =
                isLatestAssistantMessage && topRecommendations.length > 0;
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
                      <p className="chat-message-list-title">
                        Recommended options
                      </p>
                      <ol
                        className="chat-message-recommendation-list"
                        aria-label="Top recommendations"
                      >
                        {topRecommendations.map((item) => (
                          <li
                            key={`summary-${item.itemId}-${item.rank}`}
                            className="chat-message-recommendation-item"
                          >
                            <span className="chat-message-recommendation-rank">
                              #{item.rank}
                            </span>
                            <span className="chat-message-recommendation-name">
                              {getRecommendationName(item)}
                            </span>
                          </li>
                        ))}
                      </ol>
                    </section>
                  ) : null}
                </article>
              );
            })}

            {isSending ? (
              <article className="chat-message chat-message-assistant chat-message-loading">
                <p className="chat-message-role">TravelTom</p>
                <div
                  className="typing-indicator"
                  aria-label="TravelTom is typing"
                >
                  <span />
                  <span />
                  <span />
                </div>
              </article>
            ) : null}
          </div>

          {errorMessage ? (
            <aside className="chat-error" role="alert">
              <p>{errorMessage}</p>
              {pendingRequest ? (
                <button
                  className="button button-ghost button-xs"
                  onClick={handleRetry}
                  type="button"
                >
                  Retry last message
                </button>
              ) : null}
            </aside>
          ) : null}

          <form className="chat-input-form" onSubmit={handleSubmit}>
            <label className="sr-only" htmlFor="chat-message-input">
              Message input
            </label>
            <textarea
              id="chat-message-input"
              className="chat-input"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Tell TravelTom what kind of trip you want..."
              rows={3}
              disabled={isSending}
              required
            />
            <div className="chat-form-row">
              <p className="chat-form-hint">
                Be specific with dates, budget, origin city, and trip vibe.
              </p>
              <button
                className="button button-primary"
                type="submit"
                disabled={isSending}
              >
                {isSending ? "Sending..." : "Send"}
              </button>
            </div>
          </form>
        </div>

        {hasRecommendations ? (
          <aside className="recommendations-panel" aria-live="polite">
            <div className="recommendations-panel-header">
              <div>
                <p className="eyebrow">Recommendations</p>
                <p>Top {topRecommendations.length} picks from latest response</p>
              </div>
              <button
                className="button button-ghost button-xs"
                onClick={() =>
                  setIsRecommendationsCollapsed((collapsed) => !collapsed)
                }
                type="button"
                aria-expanded={!isRecommendationsCollapsed}
                aria-controls="recommendation-list"
              >
                {isRecommendationsCollapsed ? "Show picks" : "Hide picks"}
              </button>
            </div>

            {isRecommendationsCollapsed ? (
              <p className="recommendations-collapsed-copy">
                Recommendations are available when you need them.
              </p>
            ) : (
              <ol id="recommendation-list" className="recommendation-list">
                {topRecommendations.map((item) => (
                  <li
                    key={`${item.itemId}-${item.rank}`}
                    className="recommendation-list-item"
                  >
                    <article className="recommendation-card">
                      <div className="recommendation-card-head">
                        <p className="recommendation-rank">#{item.rank}</p>
                        <div className="recommendation-card-badges">
                          <p className="recommendation-type">{item.itemType}</p>
                          <p className="recommendation-score">
                            Score {item.score.toFixed(2)}
                          </p>
                        </div>
                      </div>
                      <h3>{getRecommendationName(item)}</h3>
                      <p className="recommendation-subline">
                        {item.metadata?.city
                          ? String(item.metadata.city)
                          : "Location unavailable"}
                        {item.metadata?.stars
                          ? ` - ${String(item.metadata.stars)} stars`
                          : ""}
                      </p>
                      <details className="recommendation-details">
                        <summary>Why this pick</summary>
                        <p>{item.explanation}</p>
                      </details>
                    </article>
                  </li>
                ))}
              </ol>
            )}
          </aside>
        ) : null}
      </div>
    </section>
  );
}
