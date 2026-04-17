import { FormEvent, useEffect, useRef, useState } from "react";

import { ApiClientError, apiClient } from "../../../../api/client";
import { useSessionStore } from "../../../../store/session";
import {
  createMessage,
  createMessageId,
  getClientContext,
  type PendingRequest,
} from "../../lib/plannerChat";
import { shouldDiscardHydratedSession } from "../../lib/sessionHydration/sessionHydration";
import {
  buildChatErrorState,
  getCooldownRemainingSeconds,
} from "../../model/chatErrorState/chatErrorState";
import {
  handleComposerKeyDown,
  PlannerConversation,
} from "../PlannerConversation";
import {
  PlannerRecommendationsSurface,
  PlannerRecommendationsToggle,
} from "../PlannerRecommendations";

function TomAvatar({ className }: { className: string }) {
  return (
    <div className={className} aria-hidden="true">
      <svg
        viewBox="0 0 24 24"
        width="22"
        height="22"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="3" y="4" width="18" height="14" rx="3" />
        <circle cx="9" cy="11" r="1.2" fill="currentColor" stroke="none" />
        <circle cx="15" cy="11" r="1.2" fill="currentColor" stroke="none" />
        <path d="M2 8h2M20 8h2M9 18v2M15 18v2" />
      </svg>
    </div>
  );
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
  const hasRecommendations = topRecommendations.length > 0;

  useEffect(() => {
    if (
      latestRecommendations.length > 0 &&
      latestRecommendations.length !== prevRecsLenRef.current
    ) {
      setRecsJustArrived(true);
    }
    prevRecsLenRef.current = latestRecommendations.length;
  }, [latestRecommendations]);

  useEffect(() => {
    if (!recsJustArrived) {
      return;
    }
    const timeoutId = window.setTimeout(() => setRecsJustArrived(false), 900);
    return () => window.clearTimeout(timeoutId);
  }, [recsJustArrived]);

  useEffect(() => {
    if (!isDrawerOpen) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
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
          if (
            error.status === 401 ||
            error.status === 403 ||
            error.status === 404
          ) {
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

  function submitDraft() {
    const message = draft.trim();
    if (!message) {
      return;
    }

    setDraft("");
    void sendMessage(message, { appendUserMessage: true });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submitDraft();
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

  const avatarClass = [
    "tom-avatar",
    isSending ? "tom-avatar-thinking" : "",
    recsJustArrived ? "tom-avatar-glow" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <section className="chat-view">
      <div className="chat-view-header">
        <div className="tom-identity">
          <TomAvatar className={avatarClass} />
          <span className="tom-name">Tom</span>
          <span className="tom-status-dot" aria-label="Online" />
        </div>
        <div className="chat-header-actions">
          <PlannerRecommendationsToggle
            isDrawerOpen={isDrawerOpen}
            onOpenDrawer={() => setIsDrawerOpen(true)}
            recommendationsCount={topRecommendations.length}
            recsJustArrived={recsJustArrived}
          />
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

      <div
        className={`chat-layout ${hasRecommendations ? "chat-layout-with-recommendations" : ""}`}
      >
        <div className="chat-main-column">
          <PlannerConversation
            avatarClass={avatarClass}
            isSending={isSending}
            latestAssistantMessageId={latestAssistantMessageId}
            messages={messages}
            onSuggestionSelect={(chip) => {
              setDraft((previousDraft) =>
                previousDraft ? `${previousDraft}, ${chip.toLowerCase()}` : chip,
              );
            }}
            recommendations={topRecommendations}
          />

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
                onKeyDown={(event) =>
                  handleComposerKeyDown(event, {
                    draft,
                    isSending,
                    isTravelTomCooldownActive,
                    isHydrating,
                    onSubmit: submitDraft,
                  })
                }
                placeholder="Share your destination, or add destination, dates, and budget..."
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
              For hotels, include destination and dates. Add budget if you want
              tighter price filtering. For restaurants or activities,
              destination is enough to get started.
            </p>
          </form>
        </div>

        {hasRecommendations ? (
          <PlannerRecommendationsSurface
            isDrawerOpen={isDrawerOpen}
            onCloseDrawer={() => setIsDrawerOpen(false)}
            recommendations={topRecommendations}
            recsJustArrived={recsJustArrived}
          />
        ) : null}
      </div>
    </section>
  );
}
