import { describe, expect, it } from "vitest";

import {
  DEFAULT_AUTH_REDIRECT,
  getAuthLinkState,
  getAuthRedirectTarget,
} from "./authFlow";

describe("authFlow", () => {
  it("returns internal redirect targets", () => {
    expect(getAuthRedirectTarget({ from: "/planner?draft=summer" })).toBe(
      "/planner?draft=summer",
    );
  });

  it("falls back for unsafe redirect targets", () => {
    expect(getAuthRedirectTarget({ from: "https://example.com" })).toBe(
      DEFAULT_AUTH_REDIRECT,
    );
    expect(getAuthRedirectTarget({ from: "//malicious.test" })).toBe(
      DEFAULT_AUTH_REDIRECT,
    );
    expect(getAuthRedirectTarget({ from: 123 })).toBe(DEFAULT_AUTH_REDIRECT);
  });

  it("only preserves non-default redirect state for auth links", () => {
    expect(getAuthLinkState({ from: "/planner?tab=saved" })).toEqual({
      from: "/planner?tab=saved",
    });
    expect(getAuthLinkState(undefined)).toBeUndefined();
    expect(getAuthLinkState({ from: "/planner" })).toBeUndefined();
  });
});
