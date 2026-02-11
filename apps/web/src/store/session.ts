import { create } from "zustand";

export type SessionMessageRole = "user" | "assistant";

export interface SessionMessage {
  id: string;
  role: SessionMessageRole;
  content: string;
  createdAt: string;
}

interface SessionState {
  sessionId: string;
  messages: SessionMessage[];
  isSending: boolean;
  errorMessage: string | null;
  setSessionId: (sessionId: string) => void;
  addMessage: (message: SessionMessage) => void;
  setIsSending: (value: boolean) => void;
  setErrorMessage: (value: string | null) => void;
  resetConversation: () => void;
}

function createSessionId(): string {
  try {
    return `session-${crypto.randomUUID()}`;
  } catch {
    return `session-${Date.now()}`;
  }
}

export const useSessionStore = create<SessionState>((set) => ({
  sessionId: createSessionId(),
  messages: [],
  isSending: false,
  errorMessage: null,
  setSessionId: (sessionId) => {
    set({ sessionId });
  },
  addMessage: (message) => {
    set((state) => ({ messages: [...state.messages, message] }));
  },
  setIsSending: (value) => {
    set({ isSending: value });
  },
  setErrorMessage: (value) => {
    set({ errorMessage: value });
  },
  resetConversation: () => {
    set({
      sessionId: createSessionId(),
      messages: [],
      isSending: false,
      errorMessage: null,
    });
  },
}));
