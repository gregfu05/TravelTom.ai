import type { ReactElement, PropsWithChildren } from "react";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, type MemoryRouterProps } from "react-router-dom";

import { useSessionStore } from "../store/session";

const initialSessionState = useSessionStore.getInitialState();

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0,
        gcTime: 0,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

export function resetSessionStore() {
  useSessionStore.setState(initialSessionState, true);
  window.localStorage.removeItem("traveltom-session");
}

export function seedSessionStore(
  state: Partial<ReturnType<typeof useSessionStore.getState>>,
) {
  useSessionStore.setState({
    ...useSessionStore.getState(),
    ...state,
  });
}

export function renderWithProviders(
  ui: ReactElement,
  options?: {
    entries?: MemoryRouterProps["initialEntries"];
  },
) {
  const queryClient = createTestQueryClient();

  function Wrapper({ children }: PropsWithChildren) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={options?.entries ?? ["/"]}>
          {children}
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  return {
    queryClient,
    ...render(ui, { wrapper: Wrapper }),
  };
}
