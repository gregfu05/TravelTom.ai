# Chat Feature Audit Matrix

## Summary

This matrix is the implementation-facing audit for the chat feature across the
API contract, orchestrator behavior, slot/state persistence, runtime smoke
checks, and frontend planner continuity.

Mandatory provider modes for release verification:

- `disabled`: deterministic fallback path
- `ollama`: provider-assisted planner/composer path

Primary automated commands:

- `venv\Scripts\python.exe -m pytest tests\orchestrator tests\api\test_chat.py -q`
- `cd apps/web && npm test`
- `cd apps/web && npm run test:e2e`
- `pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl http://localhost:8000 -Provider disabled`
- `pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl http://localhost:8000 -Provider ollama -Email <generated>`
- `pwsh ./scripts/smoke-planner-live.ps1 -ApiBaseUrl http://localhost:8000 -Provider disabled`

## Scenario Matrix

| Scenario | Expected slot/state outcome | Evidence | Provider modes | Status |
| --- | --- | --- | --- | --- |
| Greeting, social, and meta turns | No trip constraints persist; fast-path clarification remains conversational | `tests/orchestrator/test_service.py`, `tests/orchestrator/test_extraction.py`, `scripts/smoke-chat-runtime.ps1` | `disabled`, `ollama` | Covered |
| Hotel slot gating | `last_recommendation_item_type=hotel`; `last_requested_slots=["destination"]` until destination is captured | `tests/orchestrator/test_service.py`, `tests/orchestrator/test_eval_conversations.py`, `scripts/smoke-chat-runtime.ps1` | `disabled`, `ollama` | Covered |
| Complete one-shot hotel request | Destination and dates persist; budget persists when present; `last_requested_slots=[]` | `tests/orchestrator/test_eval_conversations.py`, `tests/api/test_chat.py`, `scripts/smoke-chat-runtime.ps1` | `disabled`, `ollama` | Covered |
| Generic trip setup | Destination and dates persist; `last_clarification_kind=search_type`; search type is asked before budget | `tests/orchestrator/test_service.py`, `tests/orchestrator/test_eval_conversations.py`, `scripts/smoke-chat-runtime.ps1` | `disabled`, `ollama` | Covered |
| Progressive slot filling and carry-forward | Newly captured slots are acknowledged; destination and dates survive later slot-filling replies | `tests/orchestrator/test_service.py`, `tests/orchestrator/test_extraction.py`, `scripts/smoke-chat-runtime.ps1` | `disabled`, `ollama` | Covered |
| Destination overwrite protection | Weak or unrelated phrases do not overwrite a valid destination; direct destination updates still work | `tests/orchestrator/test_extraction.py`, `tests/orchestrator/test_service.py`, `scripts/smoke-chat-runtime.ps1` | `disabled`, `ollama` | Covered |
| Preference carry-forward | Interests persist into `last_recommendation_query` and later clarification turns | `tests/orchestrator/test_eval_conversations.py`, `tests/orchestrator/test_extraction.py`, `scripts/smoke-chat-runtime.ps1` | `disabled`, `ollama` | Covered |
| Repair and negation turns | Session stays in clarification; prior domain assumptions are corrected without false slot writes | `tests/orchestrator/test_service.py`, `tests/orchestrator/test_extraction.py`, `scripts/smoke-chat-runtime.ps1` | `disabled`, `ollama` | Covered |
| Unsupported flights and route replies | Refusal copy is returned; origin/destination and recommendation mode are not mutated from flight text | `tests/orchestrator/test_service.py`, `tests/orchestrator/test_extraction.py`, `scripts/smoke-chat-runtime.ps1` | `disabled`, `ollama` | Covered |
| Empty-results response | `last_search_outcome=empty_results`; `last_clarification_kind=refine_preference`; no hallucinated recommendations | `tests/orchestrator/test_eval_conversations.py`, `tests/orchestrator/test_service.py`, `scripts/smoke-chat-runtime.ps1` | `disabled`, `ollama` | Covered |
| Vague follow-up after empty results | Session remains in `empty_results`; stronger guidance is returned instead of looping silently | `tests/orchestrator/test_service.py`, `tests/orchestrator/test_extraction.py`, `scripts/smoke-chat-runtime.ps1` | `disabled`, `ollama` | Covered |
| Same-session refinement continuity | Follow-ups like `show me more` and `lower cost` retain item type, query topic, and slot completeness | `tests/orchestrator/test_service.py`, `tests/orchestrator/test_extraction.py`, `scripts/smoke-chat-runtime.ps1` | `disabled`, `ollama` | Covered |
| API persistence and transcript hydration | Session state is validated and persisted; transcript and latest recommendations can be reloaded | `tests/api/test_chat.py`, `apps/web/src/features/planner/components/ChatView.test.tsx`, `apps/web/src/features/planner/lib/sessionHydration/sessionHydration.test.ts` | Provider-agnostic | Covered |
| API failure handling | Rollback, invalid-state rejection, provider `429` mapping, auth ownership, and TravelTom rate limiting are surfaced correctly | `tests/api/test_chat.py`, `tests/api/test_auth.py`, `tests/api/test_local_auth.py`, `tests/orchestrator/test_llm_provider.py` | Provider-agnostic | Covered |
| Frontend happy path | Login redirect, message send, assistant response, and recommendation rendering work end-to-end with mocked API responses | `apps/web/e2e/planner-smoke.spec.ts`, `apps/web/src/features/planner/components/ChatView.test.tsx` | Mocked frontend | Covered |
| Frontend recovery and continuity UI | Retry flow avoids duplicate user messages; new-session reset and hydration discard logic remain stable | `apps/web/e2e/planner-smoke.spec.ts`, `apps/web/src/features/planner/components/ChatView.test.tsx`, `apps/web/src/features/planner/lib/sessionHydration/sessionHydration.test.ts` | Mocked frontend | Covered |
| Frontend against the real backend | Planner UI matches live backend behavior for one supported flow and one continuity/recovery flow | `scripts/smoke-planner-live.ps1`, `apps/web/e2e/planner-live.spec.ts` | `disabled`; optional `ollama` gate | Covered |
| Live degraded provider visibility | `X-TravelTom-*` degraded headers are asserted through tests, but not forced by the default live smoke path | `tests/api/test_chat.py`, `tests/api/test_local_auth.py` | `ollama` | Partial |

## Live Planner Release Verification

Run the real frontend against a migrated, seeded backend:

```powershell
pwsh ./scripts/smoke-planner-live.ps1 -ApiBaseUrl http://localhost:8000 -Provider disabled
```

The smoke signs up through the UI when auth is enabled, checks health and
catalog readiness before browser assertions, sends a complete seeded-destination
hotel request, confirms recommendation cards reflect the latest assistant turn,
then sends `show me more` in the same session and verifies the UI updates from
that latest backend response.

Use `-AuthMode disabled` only for a backend deliberately running without auth;
the frontend still receives a local smoke token so `/planner` can render while
the backend ignores bearer validation. Run `-Provider ollama` as an optional
provider-assisted release gate after the default deterministic smoke passes.

If Playwright or Vite fails with `spawn EPERM` under a restricted sandbox, rerun
the same command in a normal PowerShell session or approved elevated shell.

## Notes

- Backend correctness is intentionally locked at orchestrator and API-test layers first.
- The PowerShell smoke script is the live evidence for slot persistence and
  provider-assisted parity, but it is not the only guardrail.
- Frontend Playwright coverage remains mocked by design for fast CI feedback;
  the live planner smoke is a release verification command for seeded local or
  deployed environments.
- Provider-assisted naturalness is preferred when the composed result summary
  stays grounded to surfaced recommendation records; otherwise backend-owned
  fallback copy takes over.
- Deterministic and fallback copy can now vary across a small semantically
  equivalent response set so disabled runs stay less obviously predefined.
