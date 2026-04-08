import assert from "node:assert/strict";
import { DEFAULT_AUTH_REDIRECT, getAuthLinkState, getAuthRedirectTarget, } from "./authFlow.js";
function testGetAuthRedirectTargetReturnsInternalRoute() {
    assert.equal(getAuthRedirectTarget({ from: "/planner?draft=summer" }), "/planner?draft=summer");
}
function testGetAuthRedirectTargetFallsBackForUnsafeRoutes() {
    assert.equal(getAuthRedirectTarget({ from: "https://example.com" }), DEFAULT_AUTH_REDIRECT);
    assert.equal(getAuthRedirectTarget({ from: "//malicious.test" }), DEFAULT_AUTH_REDIRECT);
    assert.equal(getAuthRedirectTarget({ from: 123 }), DEFAULT_AUTH_REDIRECT);
}
function testGetAuthLinkStateCarriesOnlyNonDefaultTargets() {
    assert.deepEqual(getAuthLinkState({ from: "/planner?tab=saved" }), {
        from: "/planner?tab=saved",
    });
    assert.equal(getAuthLinkState(undefined), undefined);
    assert.equal(getAuthLinkState({ from: "/planner" }), undefined);
}
testGetAuthRedirectTargetReturnsInternalRoute();
testGetAuthRedirectTargetFallsBackForUnsafeRoutes();
testGetAuthLinkStateCarriesOnlyNonDefaultTargets();
