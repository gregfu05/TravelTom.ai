# Feature Modules

Purpose: feature-scoped frontend code, currently centered on the planner experience.

Ownership: Frontend.

## What Lives Here

- `planner/`: planner chat UI, recommendations rail, state helpers, and session hydration logic.

## Notes

- Prefer colocating feature logic, UI, and tests under the feature boundary.
- If the planner interaction contract changes, coordinate updates with API chat/recommendation schemas.

## Related Docs

- `../README.md`
- `../../../../instructions/05-frontend/ux-flows.md`
