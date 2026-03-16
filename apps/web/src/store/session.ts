import { create } from "zustand";
import { persist } from "zustand/middleware";

import { ChatErrorState } from "../components/chatErrorState";

export type SessionMessageRole = "user" | "assistant";

export interface SessionRecommendation {
  itemId: string;
  itemType: "destination" | "hotel" | "flight";
  score: number;
  rank: number;
  explanation: string;
  metadata?: Record<string, unknown>;
}

export interface SessionMessage {
  id: string;
  role: SessionMessageRole;
  content: string;
  createdAt: string;
}

interface SessionState {
  sessionId: string;
  messages: SessionMessage[];
  latestRecommendations: SessionRecommendation[];
  isSending: boolean;
  chatError: ChatErrorState | null;
  authToken: string | null;
  setSessionId: (sessionId: string) => void;
  addMessage: (message: SessionMessage) => void;
  setLatestRecommendations: (items: SessionRecommendation[]) => void;
  setIsSending: (value: boolean) => void;
  setChatError: (value: ChatErrorState | null) => void;
  setAuthToken: (token: string | null) => void;
  resetConversation: () => void;
}

function createSessionId(): string {
  try {
    return `session-${crypto.randomUUID()}`;
  } catch {
    return `session-${Date.now()}`;
  }
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      sessionId: createSessionId(),
      messages: [],
      latestRecommendations: [],
      isSending: false,
      chatError: null,
      authToken: null,
      setSessionId: (sessionId) => {
        set({ sessionId });
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
      resetConversation: () => {
        set((state) => ({
          sessionId: createSessionId(),
          messages: [],
          latestRecommendations: [],
          isSending: false,
          chatError: null,
          authToken: state.authToken,
        }));
      },
    }),
    {
      name: "traveltom-session",
      partialize: (state) => ({
        authToken: state.authToken,
      }),
    },
  ),
);
