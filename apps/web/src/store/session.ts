import { create } from "zustand";
import { persist } from "zustand/middleware";

import { ChatErrorState } from "../features/planner/model/chatErrorState/chatErrorState.js";

export type SessionMessageRole = "user" | "assistant";

export interface SessionRecommendation {
  itemId: string;
  itemType: "hotel" | "restaurant" | "activity";
  score?: number;
  rank: number;
  explanation?: string;
  metadata?: Record<string, unknown>;
}

export interface SavedRecommendation extends SessionRecommendation {
  savedAt: string;
  sourceSessionId: string;
}

export interface SessionItinerary {
  days: unknown[];
}

export interface BookingStubConfirmation {
  itemId: string;
  itemName: string;
  confirmedAt: string;
  sourceSessionId: string;
}

export interface SessionMessage {
  id: string;
  role: SessionMessageRole;
  content: string;
  createdAt: string;
}

interface SessionState {
  sessionId: string;
  hasRemoteSession: boolean;
  messages: SessionMessage[];
  latestRecommendations: SessionRecommendation[];
  latestItinerary: SessionItinerary | null;
  savedRecommendations: SavedRecommendation[];
  bookingConfirmation: BookingStubConfirmation | null;
  isSending: boolean;
  chatError: ChatErrorState | null;
  authToken: string | null;
  setSessionId: (sessionId: string) => void;
  setHasRemoteSession: (value: boolean) => void;
  addMessage: (message: SessionMessage) => void;
  setLatestRecommendations: (items: SessionRecommendation[]) => void;
  setLatestItinerary: (itinerary: SessionItinerary | null) => void;
  saveRecommendation: (
    item: SessionRecommendation,
    sourceSessionId?: string,
  ) => void;
  removeSavedRecommendation: (itemId: string) => void;
  confirmBookingStub: (
    item: SessionRecommendation,
    itemName: string,
    sourceSessionId?: string,
  ) => void;
  clearBookingConfirmation: () => void;
  setIsSending: (value: boolean) => void;
  setChatError: (value: ChatErrorState | null) => void;
  setAuthToken: (token: string | null) => void;
  hydrateConversation: (payload: {
    sessionId: string;
    messages: SessionMessage[];
    latestRecommendations: SessionRecommendation[];
    latestItinerary?: SessionItinerary | null;
  }) => void;
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
      hasRemoteSession: false,
      messages: [],
      latestRecommendations: [],
      latestItinerary: null,
      savedRecommendations: [],
      bookingConfirmation: null,
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
      setLatestItinerary: (itinerary) => {
        set({ latestItinerary: itinerary });
      },
      saveRecommendation: (item, sourceSessionId) => {
        set((state) => {
          if (
            state.savedRecommendations.some(
              (savedItem) => savedItem.itemId === item.itemId,
            )
          ) {
            return state;
          }

          return {
            savedRecommendations: [
              ...state.savedRecommendations,
              {
                ...item,
                savedAt: new Date().toISOString(),
                sourceSessionId: sourceSessionId ?? state.sessionId,
              },
            ],
          };
        });
      },
      removeSavedRecommendation: (itemId) => {
        set((state) => ({
          savedRecommendations: state.savedRecommendations.filter(
            (item) => item.itemId !== itemId,
          ),
          bookingConfirmation:
            state.bookingConfirmation?.itemId === itemId
              ? null
              : state.bookingConfirmation,
        }));
      },
      confirmBookingStub: (item, itemName, sourceSessionId) => {
        set((state) => ({
          bookingConfirmation: {
            itemId: item.itemId,
            itemName,
            confirmedAt: new Date().toISOString(),
            sourceSessionId: sourceSessionId ?? state.sessionId,
          },
        }));
      },
      clearBookingConfirmation: () => {
        set({ bookingConfirmation: null });
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
          latestItinerary: payload.latestItinerary ?? state.latestItinerary,
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
          latestItinerary: null,
          savedRecommendations: [],
          bookingConfirmation: null,
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
        sessionId: state.sessionId,
        hasRemoteSession: state.hasRemoteSession,
      }),
    },
  ),
);
