import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";

import { ApiClientError, apiClient, type Recommendation } from "../api/client";
import { SessionMessage, useSessionStore } from "../store/session";

interface PendingRequest {
  message: string;
  messageId: string;
}

const SUGGESTION_CHIPS = [
  "Weekend getaway from Madrid",
  "Beach + relax",
  "Budget under €500",
  "No long flights",
  "City break",
  "Family-friendly",
] as const;

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

  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [recsJustArrived, setRecsJustArrived] = useState(false);
  const prevRecsLenRef = useRef(latestRecommendations.length);

  const hasRecommendations = latestRecommendations.length > 0;
  const topRecommendations = latestRecommendations.slice(0, 5);
  const latestAssistantMessageId = [...messages]
    .reverse()
    .find((item) => item.role === "assistant")?.id;

  // Detect new recommendations → glow avatar + pulse pill
  useEffect(() => {
    if (
      latestRecommendations.length > 0 &&
      latestRecommendations.length !== prevRecsLenRef.current
    ) {
      setRecsJustArrived(true);
    }
    prevRecsLenRef.current = latestRecommendations.length;
  }, [latestRecommendations]);

  // Clear glow after animation
  useEffect(() => {
    if (!recsJustArrived) return;
    const t = window.setTimeout(() => setRecsJustArrived(false), 900);
    return () => window.clearTimeout(t);
  }, [recsJustArrived]);

  // Prevent background scroll when mobile drawer open
  useEffect(() => {
    if (!isDrawerOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [isDrawerOpen]);

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

  // Avatar state class
  const avatarClass = [
    "tom-avatar",
    isSending ? "tom-avatar-thinking" : "",
    recsJustArrived ? "tom-avatar-glow" : "",
  ]
    .filter(Boolean)
    .join(" ");

  // Shared recommendation card renderer
  const renderRecommendationCards = () => (
    <ol className="recommendation-list">
      {topRecommendations.map((item) => (
        <li
          key={`${item.itemId}-${item.rank}`}
          className="recommendation-list-item"
        >
          <article className="recommendation-card">
            <h3>
              {item.metadata?.name
                ? String(item.metadata.name)
                : item.itemId}
            </h3>
            {typeof item.metadata?.map_url === "string" ? (
              <a
                className="recommendation-link"
                href={item.metadata.map_url}
                target="_blank"
                rel="noreferrer"
              >
                Open in Google Maps
              </a>
            ) : (
              <p className="recommendation-subline">Map link unavailable</p>
            )}
          </article>
        </li>
      ))}
    </ol>
  );

  return (
    <section className="chat-view">
      {/* ── Chat Header ── */}
      <div className="chat-view-header">
        <div className="tom-identity">
          <div className={avatarClass} aria-hidden="true">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="4" width="18" height="14" rx="3" />
              <circle cx="9" cy="11" r="1.2" fill="currentColor" stroke="none" />
              <circle cx="15" cy="11" r="1.2" fill="currentColor" stroke="none" />
              <path d="M2 8h2M20 8h2M9 18v2M15 18v2" />
            </svg>
          </div>
          <span className="tom-name">Tom</span>
          <span className="tom-status-dot" aria-label="Online" />
        </div>
        <div className="chat-header-actions">
          {/* Mobile-only: open drawer button */}
          {hasRecommendations ? (
            <button
              className={`picks-glow-pill picks-glow-pill-mobile ${recsJustArrived ? "picks-glow-pill-pulse" : ""}`}
              onClick={() => setIsDrawerOpen(true)}
              type="button"
              aria-expanded={isDrawerOpen}
              aria-controls="recommendations-drawer"
            >
              <span className="picks-glow-pill-sparkle" aria-hidden="true">✦</span>
              {topRecommendations.length} Picks
            </button>
          ) : null}
          <p className="session-pill">Session {sessionId.slice(0, 8)}</p>
          <button
            className="button button-ghost button-xs"
            onClick={resetConversation}
            type="button"
          >
            New Session
          </button>
        </div>
      </div>

      {/* ── Chat body: side-by-side when recommendations exist ── */}
      <div
        className={`chat-layout ${hasRecommendations ? "chat-layout-with-recommendations" : ""}`}
      >
        <div className="chat-main-column">
          <div
            className="chat-thread"
            role="log"
            aria-live="polite"
            aria-relevant="additions text"
          >
            {/* Empty state */}
            {messages.length === 0 ? (
              <div className="chat-welcome">
                <div className={`chat-welcome-avatar ${avatarClass}`} aria-hidden="true">
                  <svg viewBox="0 0 24 24" width="44" height="44" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="4" width="18" height="14" rx="3" />
                    <circle cx="9" cy="11" r="1.4" fill="currentColor" stroke="none" />
                    <circle cx="15" cy="11" r="1.4" fill="currentColor" stroke="none" />
                    <path d="M2 8h2M20 8h2M9 18v2M15 18v2" />
                  </svg>
                </div>
                <h2 className="chat-welcome-heading">Where to?</h2>
                <p className="chat-welcome-sub">Tell Tom your dates and vibe.</p>
                <div className="suggestion-chips">
                  {SUGGESTION_CHIPS.map((chip) => (
                    <button
                      key={chip}
                      className="suggestion-chip"
                      type="button"
                      onClick={() =>
                        setDraft((prev) =>
                          prev ? `${prev}, ${chip.toLowerCase()}` : chip,
                        )
                      }
                    >
                      {chip}
                    </button>
                  ))}
                </div>
              </div>
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
                primaryMessage ||
                "I found recommendations that match your request.";

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
                        {topRecommendations.map((item) => {
                          const name = getRecommendationName(item);
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
                                {name}
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
            <div className="chat-input-container">
              <textarea
                id="chat-message-input"
                className="chat-input"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event: KeyboardEvent<HTMLTextAreaElement>) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    const message = draft.trim();
                    if (!message || isSending) return;
                    setDraft("");
                    void sendMessage(message, { appendUserMessage: true });
                  }
                }}
                placeholder="Tell Tom what kind of trip you want..."
                rows={2}
                disabled={isSending}
                required
              />
              <button
                className="button button-primary chat-send-button"
                type="submit"
                disabled={isSending}
              >
                {isSending ? "Sending..." : "Send"}
              </button>
            </div>
            <p className="chat-form-hint">
              Be specific with dates, budget, origin city, and trip vibe.
            </p>
          </form>
        </div>

        {/* ── Inline side panel (desktop) ── */}
        {hasRecommendations ? (
          <aside
            className={`recommendations-panel ${recsJustArrived ? "recommendations-panel-arrive" : ""}`}
            aria-live="polite"
          >
            <div className="recommendations-panel-header">
              <div>
                <p className="eyebrow">✦ Top Picks</p>
                <p>Top {topRecommendations.length} from latest response</p>
              </div>
            </div>

            <ol id="recommendation-list" className="recommendation-list">
              {topRecommendations.map((item) => {
                const name = getRecommendationName(item);
                const mapUrl =
                  typeof item.metadata?.map_url === "string"
                    ? item.metadata.map_url
                    : undefined;

                return (
                  <li
                    key={`${item.itemId}-${item.rank}`}
                    className="recommendation-list-item"
                  >
                    <article className="recommendation-card">
                      <h3 className="recommendation-name">{name}</h3>

                      {mapUrl ? (
                        <a
                          href={mapUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="recommendation-map-link"
                        >
                          View on map
                        </a>
                      ) : null}
                    </article>
                  </li>
                );
              })}
            </ol>
          </aside>
        ) : null}
      </div>

      {/* ── Mobile drawer overlay ── */}
      {isDrawerOpen ? (
        <div
          className="drawer-overlay"
          onClick={() => setIsDrawerOpen(false)}
          aria-hidden="true"
        />
      ) : null}

      {/* ── Mobile drawer ── */}
      <aside
        id="recommendations-drawer"
        className={`drawer ${isDrawerOpen ? "drawer-open" : ""}`}
        aria-live="polite"
      >
        <div className="drawer-header">
          <div>
            <p className="eyebrow">✦ Recommendations</p>
            <p className="drawer-subtitle">
              Top {topRecommendations.length} picks from latest response
            </p>
          </div>
          <button
            className="button button-ghost button-xs"
            onClick={() => setIsDrawerOpen(false)}
            type="button"
          >
            Close
          </button>
        </div>
        {renderRecommendationCards()}
      </aside>
    </section>
  );
}
