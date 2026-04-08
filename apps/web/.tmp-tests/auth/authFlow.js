export const DEFAULT_AUTH_REDIRECT = "/planner";
function isSafeInternalRoute(value) {
    return value.startsWith("/") && !value.startsWith("//");
}
export function getAuthRedirectTarget(state) {
    const candidate = state && typeof state === "object"
        ? state.from
        : undefined;
    if (typeof candidate === "string" && isSafeInternalRoute(candidate)) {
        return candidate;
    }
    return DEFAULT_AUTH_REDIRECT;
}
export function getAuthLinkState(state) {
    const target = getAuthRedirectTarget(state);
    if (target === DEFAULT_AUTH_REDIRECT) {
        return undefined;
    }
    return { from: target };
}
