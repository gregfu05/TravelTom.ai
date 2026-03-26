import { create } from "zustand";
import { persist } from "zustand/middleware";
function createSessionId() {
    try {
        return `session-${crypto.randomUUID()}`;
    }
    catch {
        return `session-${Date.now()}`;
    }
}
export const useSessionStore = create()(persist((set) => ({
    sessionId: createSessionId(),
    hasRemoteSession: false,
    messages: [],
    latestRecommendations: [],
    isSending: false,
    chatError: null,
    authToken: null,
    setSessionId: (sessionId) => {
        set({ sessionId });
    },
    setHasRemoteSession: (value) => {
        set({ hasRemoteSession: value });
    },
    addMessage: (message) => {
        set((state) => ({ messages: [...state.messages, message] }));
    },
    setLatestRecommendations: (items) => {
        set({ latestRecommendations: items });
    },
    setIsSending: (value) => {
        set({ isSending: value });
    },
    setChatError: (value) => {
        set({ chatError: value });
    },
    setAuthToken: (token) => set({ authToken: token }),
    hydrateConversation: (payload) => {
        set((state) => ({
            sessionId: payload.sessionId,
            hasRemoteSession: true,
            messages: payload.messages,
            latestRecommendations: payload.latestRecommendations,
            isSending: false,
            chatError: null,
            authToken: state.authToken,
        }));
    },
    resetConversation: () => {
        set((state) => ({
            sessionId: createSessionId(),
            hasRemoteSession: false,
            messages: [],
            latestRecommendations: [],
            isSending: false,
            chatError: null,
            authToken: state.authToken,
        }));
    },
}), {
    name: "traveltom-session",
    partialize: (state) => ({
        authToken: state.authToken,
        sessionId: state.sessionId,
        hasRemoteSession: state.hasRemoteSession,
    }),
}));
