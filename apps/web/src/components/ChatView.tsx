import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";

import { ApiClientError, apiClient, type Recommendation } from "../api/client";
import {
  buildChatErrorState,
  getCooldownRemainingSeconds,
} from "./chatErrorState";
import { shouldDiscardHydratedSession } from "./sessionHydration";
import { SessionMessage, useSessionStore } from "../store/session";

interface PendingRequest {
  message: string;
  messageId: string;
}

const LEGACY_SUGGESTION_CHIPS = [
  "Beach destinations in Europe under 1500 EUR",
  "City break ideas for 4 days in May",
  "Budget under €500",
  "Flights from Madrid to Lisbon next weekend",
  "Family-friendly destinations in June under 2000 USD",
  "Romantic weekend in Italy under 1200 EUR",
] as const;

const SUGGESTION_CHIPS = [
  "Beach destinations in Europe under 1500 EUR",
  "City break ideas for 4 days in May",
  "Hotels in Lisbon next weekend under 1500 EUR",
  "Flights from Madrid to Lisbon next weekend",
  "Family-friendly destinations in June under 2000 USD",
  "Romantic weekend in Italy under 1200 EUR",
] as const;

void LEGACY_SUGGESTION_CHIPS;

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

export function ChatView() {
  const {
    sessionId,
    hasRemoteSession,
    messages,
    isSending,
    chatError,
    latestRecommendations,
    authToken,
    setSessionId,
    setHasRemoteSession,
    addMessage,
    setLatestRecommendations,
    setIsSending,
    setChatError,
    setAuthToken,
    hydrateConversation,
    resetConversation,
  } = useSessionStore();

  const [draft, setDraft] = useState("");
  const [pendingRequest, setPendingRequest] = useState<PendingRequest | null>(
    null,
  );
  const [isHydrating, setIsHydrating] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());

  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [recsJustArrived, setRecsJustArrived] = useState(false);
  const prevRecsLenRef = useRef(latestRecommendations.length);
  const shouldHydrateInitialSessionRef = useRef(hasRemoteSession);
  const hydratedSessionIdRef = useRef<string | null>(null);

  const hasRecommendations = latestRecommendations.length > 0;
  const topRecommendations = latestRecommendations.slice(0, 5);
  const cooldownRemainingSeconds = getCooldownRemainingSeconds(
    chatError?.cooldownUntilMs ?? null,
    nowMs,
  );
  const isTravelTomCooldownActive =
    chatError?.kind === "traveltom_rate_limit" && cooldownRemainingSeconds > 0;
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

  useEffect(() => {
    if (!isDrawerOpen) {
      return;
    }

    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        setIsDrawerOpen(false);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isDrawerOpen]);

  useEffect(() => {
    if (!isTravelTomCooldownActive) {
      return;
    }
    const intervalId = window.setInterval(() => {
      setNowMs(Date.now());
    }, 1000);
    return () => window.clearInterval(intervalId);
  }, [isTravelTomCooldownActive]);

  useEffect(() => {
    if (
      !authToken ||
      !hasRemoteSession ||
      !shouldHydrateInitialSessionRef.current ||
      hydratedSessionIdRef.current === sessionId
    ) {
      return;
    }

    const abortController = new AbortController();
    let settled = false;
    hydratedSessionIdRef.current = sessionId;
    setIsHydrating(true);

    void apiClient
      .getChatSession({ sessionId, authToken }, abortController.signal)
      .then((response) => {
        if (abortController.signal.aborted) {
          return;
        }
        settled = true;
        shouldHydrateInitialSessionRef.current = false;
        setIsHydrating(false);
        if (shouldDiscardHydratedSession(response)) {
          resetConversation();
          setChatError(null);
          return;
        }
        hydrateConversation({
          sessionId: response.sessionId,
          messages: response.messages,
          latestRecommendations: response.recommendations,
        });
        setChatError(null);
      })
      .catch((error: unknown) => {
        if (abortController.signal.aborted) {
          return;
        }
        settled = true;
        shouldHydrateInitialSessionRef.current = false;
        setIsHydrating(false);
        if (error instanceof ApiClientError) {
          if (error.status === 401) {
            setAuthToken(null);
          }
          if (error.status === 401 || error.status === 403 || error.status === 404) {
            resetConversation();
            return;
          }
        }
        setChatError(buildChatErrorState(error));
      });

    return () => {
      abortController.abort();
      if (!settled && hydratedSessionIdRef.current === sessionId) {
        hydratedSessionIdRef.current = null;
        setIsHydrating(false);
      }
    };
  }, [
    authToken,
    hasRemoteSession,
    hydrateConversation,
    resetConversation,
    sessionId,
    setAuthToken,
    setChatError,
  ]);

  async function sendMessage(
    rawMessage: string,
    options?: { appendUserMessage?: boolean; messageId?: string },
  ) {
    const message = rawMessage.trim();
    if (!message || isSending || isTravelTomCooldownActive || isHydrating) {
      return;
    }

    const messageId = options?.messageId ?? createMessageId();

    setChatError(null);
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
        authToken: authToken ?? undefined,
      });

      setSessionId(response.sessionId);
      setHasRemoteSession(true);
      addMessage(
        createMessage(
          "assistant",
          response.assistantMessage,
          createMessageId(),
        ),
      );
      setLatestRecommendations(response.recommendations);
      setPendingRequest(null);
      setChatError(null);
    } catch (error: unknown) {
      if (error instanceof ApiClientError && error.status === 401) {
        setAuthToken(null);
      }
      setChatError(buildChatErrorState(error));
      setNowMs(Date.now());
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
    if (!pendingRequest || isSending || isTravelTomCooldownActive) {
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
            {typeof item.metadata?.map_url === "string" ? (
              <a
                className="recommendation-map-link"
                href={item.metadata.map_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                View on map
              </a>
            ) : null}
            <details className="recommendation-details">
              <summary>Why this pick</summary>
              <p>{item.explanation}</p>
            </details>
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
              <span className="picks-glow-pill-sparkle" aria-hidden="true">*</span>
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
                <h2 className="chat-welcome-heading">Start with a trip idea</h2>
                <p className="chat-welcome-sub">
                  Start broad with a destination idea, or share destination,
                  dates, and budget if you want hotel or flight recommendations.
                </p>
                <div className="suggestion-chips">
                  {SUGGESTION_CHIPS.map((chip) => (
                    <button
                      key={chip}
                      className="suggestion-chip"
                      type="button"
                      onClick={() => setDraft((prev) => (prev ? `${prev}, ${chip.toLowerCase()}` : chip))}
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

          {chatError ? (
            <aside className="chat-error" role="alert">
              <p>{chatError.message}</p>
              {chatError.traceId ? (
                <p className="chat-form-hint">Trace ID: {chatError.traceId}</p>
              ) : null}
              {isTravelTomCooldownActive ? (
                <p className="chat-form-hint">
                  Retry becomes available in {cooldownRemainingSeconds}s.
                </p>
              ) : null}
              {pendingRequest && chatError.actionLabel ? (
                <button
                  className="button button-ghost button-xs"
                  onClick={handleRetry}
                  type="button"
                  disabled={isTravelTomCooldownActive}
                >
                  {chatError.actionLabel}
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
                    if (
                      !message ||
                      isSending ||
                      isTravelTomCooldownActive ||
                      isHydrating
                    ) {
                      return;
                    }
                    setDraft("");
                    void sendMessage(message, { appendUserMessage: true });
                  }
                }}
                placeholder="Share a destination idea, or give destination, dates, and budget..."
                rows={2}
                disabled={isSending || isTravelTomCooldownActive || isHydrating}
                required
              />
              <button
                className="button button-primary chat-send-button"
                type="submit"
                disabled={isSending || isTravelTomCooldownActive || isHydrating}
              >
                {isHydrating
                  ? "Restoring..."
                  : isSending
                  ? "Sending..."
                  : isTravelTomCooldownActive
                    ? `Retry in ${cooldownRemainingSeconds}s`
                    : "Send"}
              </button>
            </div>
            <p className="chat-form-hint">
              Destination exploration can start broad. For hotels or flights,
              include destination, dates, and budget.
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
                <p className="eyebrow">Current Picks</p>
                <p>{topRecommendations.length} current candidates from this turn</p>
              </div>
            </div>
            {renderRecommendationCards()}
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
        role="dialog"
        aria-modal="true"
        aria-label="Recommendations"
        aria-live="polite"
      >
        <div className="drawer-header">
          <div>
            <p className="eyebrow">Recommendations</p>
            <p className="drawer-subtitle">
              {topRecommendations.length} current candidates from this turn
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
