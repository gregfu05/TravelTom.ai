export const DEFAULT_AUTH_REDIRECT = "/planner";

interface AuthRouteState {
  from?: unknown;
}

function isSafeInternalRoute(value: string): boolean {
  return value.startsWith("/") && !value.startsWith("//");
}

export function getAuthRedirectTarget(state: unknown): string {
  const candidate =
    state && typeof state === "object"
      ? (state as AuthRouteState).from
      : undefined;

  if (typeof candidate === "string" && isSafeInternalRoute(candidate)) {
    return candidate;
  }

  return DEFAULT_AUTH_REDIRECT;
}

export function getAuthLinkState(state: unknown): { from: string } | undefined {
  const target = getAuthRedirectTarget(state);

  if (target === DEFAULT_AUTH_REDIRECT) {
    return undefined;
  }

  return { from: target };
}
