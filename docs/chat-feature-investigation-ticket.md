# Ticket: Investigate chat latency, naturalness, and recommendation continuity

## Outcome / Goal

Produce a full investigation of the `/planner` plus `/api/v1/chat` flow that explains why chat feels slow, sounds unnatural, loses continuity, and often fails to land grounded recommendations. End the investigation with a root-cause summary, latency breakdown, and a prioritized remediation split that can be handed off as follow-up implementation tickets.

## Why / Context

The current chat experience is misaligned with the product goal:

- A greeting like `Hello` should produce a natural TravelTom greeting, not jump straight into locking down recommendations or slot collection.
- Users report that the assistant keeps asking the same things, does not visibly lock down context, and struggles to actually reach recommendations.
- Responses feel stiff and procedural rather than conversational.
- Chat turns feel too slow, especially for a workflow that should often just acknowledge, carry forward context, and ask one useful next question.
- The system appears to persist some state on the backend, but the user experience still behaves like context is fragile or lost.

This ticket is for investigation first, not a broad rewrite. The goal is to explain the failures precisely and split fixes cleanly by subsystem.

## In Scope

- Reproduce and document 5 core flows:
  - greeting/opening turn
  - multi-turn recommendation slot filling
  - follow-up refinement like `show me more` or `cheaper`
  - page refresh and session resume
  - recommendation failure / no-results path
- Measure per-turn latency across planner, chat-agent, response composition, recommender execution, and DB persistence.
- Audit persistence at 3 layers:
  - frontend browser state
  - API session identity
  - backend `SessionState` plus recent transcript replay
- Determine why clarification loops still happen and whether they come from extraction misses, small replay windows, frontend resets, or intentionally narrow conversation memory.
- Determine why grounded recommendations do not arrive reliably even when the user is trying to get them.
- Produce follow-up remediation tickets ordered by impact.

## Out of Scope

- Implementing the full fix set in this ticket.
- Replacing the ranking algorithm in `traveltom/recommendor/recommendor_v1.py`.
- Broad auth redesign or unrelated frontend redesign.
- Relaxing grounding rules so the model can invent recommendations.

## Repo Context To Read First

- `instructions/04-llm-orchestrator/orchestrator-overview.md`
- `instructions/04-llm-orchestrator/prompts-and-guardrails.md`
- `instructions/04-llm-orchestrator/session-state-schema.md`
- `instructions/05-frontend/frontend-architecture.md`
- `instructions/02-backend/api-design.md`
- `instructions/08-quality/testing-strategy.md`

## Relevant Files / Modules

- `apps/web/src/components/ChatView.tsx`: planner UX, send/retry flow, empty-state messaging, and latest recommendation rendering.
- `apps/web/src/store/session.ts`: browser persistence behavior for `sessionId`, transcript, recommendations, and auth state.
- `apps/api/app/api/v1/chat.py`: backend session load, transcript replay load, and persistence wiring.
- `apps/api/app/repositories/chat.py`: persisted state, message history, and recommendation snapshot storage.
- `apps/api/app/services/travel_tom_agent.py`: planner execution, chat-agent execution, response composition, and recommender execution stack.
- `apps/api/app/services/orchestrator/service.py`: carry-forward logic, clarification loops, normalization, and recommendation fallback behavior.
- `apps/api/app/services/orchestrator/policies.py`: deterministic greeting/meta handling and slot-first clarification behavior.
- `apps/api/app/services/orchestrator/extraction.py`: deterministic constraint extraction and follow-up query shaping.
- `apps/api/app/services/orchestrator/providers/ollama.py`: structured planner/composer transport and timeout floor.
- `traveltom/recommendor/recommendor_v1.py`: catalog prerequisites, item-type filtering, destination filtering, and no-results behavior.
- `tests/orchestrator/test_service.py`: current expected orchestrator behavior, including greeting and follow-up continuity assertions.

## Verified Findings To Start From

- Frontend persistence is currently minimal. `apps/web/src/store/session.ts` persists only `authToken` through `partialize`, while `sessionId`, `messages`, and `latestRecommendations` reset on reload.
- Backend persistence does exist. `/api/v1/chat` loads `sessions.state_json`, replays persisted recent messages, and saves updated state plus user/assistant messages and a recommendation snapshot on every turn.
- Recent transcript replay is intentionally small. The orchestrator policy currently caps replay at 6 messages.
- Greeting behavior is currently encoded as expected behavior in tests. `tests/orchestrator/test_service.py` asserts that `Hello Tommy` leads to `Which destination should I focus on?`, so at least part of the reported UX problem is codified rather than accidental.
- Chat latency can stack multiple expensive steps per turn:
  - structured planner call
  - chat-agent call
  - response-composer call
  - recommendation tool execution in a worker thread
- Local Ollama structured planning/composition currently enforces a 60-second timeout floor, which can make bad local latency feel much worse before fallback.
- `OrchestratorService._compose_assistant_message(...)` accepts `candidate_message`, but current composition flow does not actually use that candidate transcript text when choosing the final fallback response. That may contribute to unnatural deterministic copy even when the agent produced more natural wording.
- Recommendation quality and availability depend on seeded `catalog_items` data plus a hard destination filter against catalog city names. Empty or mismatched catalog data can surface as “can’t get recommendations” even when orchestration is otherwise behaving as designed.

## Current Behavior

- Greeting turns do not persist fake destination state, but they still immediately ask for the next slot instead of greeting naturally.
- The browser loses visible transcript continuity after refresh because the client store does not restore session transcript or recommendation state.
- Backend continuity depends on a narrow combination of:
  - `SessionState`
  - the last 6 persisted transcript messages
  - carry-forward query/item-type helpers
- The final assistant message often comes from deterministic fallback copy or composer output rather than the agent’s more natural transcript wording.
- Recommendation flows can fail because of missing captured slots, duplicate-only follow-ups, empty catalog results, or destination/item-type filters that return no candidates.

## Desired Behavior

- `Hello`, `Hi`, and similar low-intent openers should get a natural branded greeting and light prompt, not immediate slot enforcement.
- Once a trip detail is captured, the assistant should not re-ask for it unless the state was never actually persisted or the user changed it.
- Context should survive normal user behavior, including refresh/session resume for the same browser session.
- Recommendation flows should either return grounded picks or explain the exact blocker:
  - missing trip detail
  - no catalog matches
  - system/runtime issue
- The investigation output should leave no ambiguity about which fixes belong in frontend state, orchestrator policy, response generation, or recommender/data reliability.

## Constraints / Non-negotiables

- Keep recommendation grounding strict; never invent items, prices, or availability.
- Preserve thin-router boundaries and validated schema/state handling.
- Keep fixes small and reviewable; do not turn this into an unrestricted chat rewrite.
- If current docs or tests encode the wrong UX, call that out explicitly.
- Any proposed remediation must state whether it changes:
  - user-visible chat behavior
  - persistence or hydration behavior
  - orchestrator/runtime behavior
  - recommender data prerequisites

## Implementation Notes

- Reproduce these scenarios manually:
  - `Hello`
  - `recommend hotels`
  - 4-turn slot filling to recommendation
  - `show me more`
  - refresh after 2 successful turns
- Capture timing around:
  - session load
  - planner invocation
  - chat-agent invocation
  - response-composer invocation
  - recommendation tool execution
  - DB write/commit
- Compare runtime behavior against the current tests and list which tests currently lock in undesired UX.
- Explicitly answer these 4 questions in the investigation summary:
  1. Why does a greeting become a slot question?
  2. Why does context disappear after refresh or resume?
  3. Why do clarification loops still happen even though backend state is persisted?
  4. Why do recommendation requests stall, return empty, or never visibly land?
- Deliverables should include:
  - root-cause matrix
  - latency table
  - persistence lifecycle notes
  - follow-up tickets ordered by impact

## Acceptance Criteria

- [ ] Each reported symptom is mapped to concrete code paths, configs, and reproduction steps.
- [ ] The investigation includes a measured latency breakdown for greeting, slot-filling, and refine flows.
- [ ] The persistence audit clearly separates backend persistence from frontend persistence/hydration gaps.
- [ ] The recommendation audit documents at least one concrete no-recommendations path tied to data or filtering behavior.
- [ ] The investigation identifies which current tests and docs encode undesired behavior and should change.
- [ ] The output includes a prioritized remediation split that another engineer can implement without rediscovering the problem.

## Verification / Tests

- Run: `python -m pytest tests/api/test_chat.py tests/orchestrator/test_service.py tests/orchestrator/test_extraction.py -q`
- Run: `python -m pytest tests/orchestrator/test_llm_provider.py -q`
- Manually verify:
  - `/planner` greeting flow
  - 4-turn recommendation flow
  - `show me more`
  - refresh/session resume
- Check DB state during repros:
  - `sessions`
  - `messages`
  - `recommendations`
  - `catalog_items`
- If recommendation failures are reproduced, verify whether `catalog_items` is seeded before assigning blame to orchestrator logic.

## Docs To Update

- `instructions/04-llm-orchestrator/orchestrator-overview.md`
- `instructions/04-llm-orchestrator/prompts-and-guardrails.md`
- `instructions/04-llm-orchestrator/session-state-schema.md`
- `instructions/05-frontend/frontend-architecture.md`
- `instructions/CHANGELOG.md` if instruction docs change

## Definition of Done

- Investigation report is complete and reproducible.
- Root causes are tied to specific modules, configs, and tests.
- Follow-up remediation tickets are scoped and prioritized.
- Relevant tests are run and the current baseline is recorded.
- Any doc/runtime mismatch is explicitly listed.

## Open Questions / Assumptions

- Assumption: `context persistence` includes refresh/session-resume behavior, not only same-tab multi-turn continuity.
- Assumption: this should be one mixed investigation ticket first, followed by implementation tickets split by subsystem.
- Open question: whether the intended persistence fix should restore full transcript/history in the UI or only enough state to continue the planning flow cleanly.
