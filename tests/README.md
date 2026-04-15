# Tests

Purpose: unit, integration, and contract tests across the TravelTom stack.

Ownership: Engineering.

## What Lives Here

- `api/`: API integration and endpoint behavior tests.
- `orchestrator/`: orchestration, slot filling, fallback, and tool-call behavior.
- `recommender/`: deterministic ranking and recommendation pipeline tests.
- `scripts/`: checks around script behavior.
- root-level tests: configuration, DB session, event-model, and health checks.

## Common Commands

Run the full Python test suite:

```bash
python -m pytest tests -q
```

Run targeted backend slices:

```bash
python -m pytest tests/api tests/orchestrator -q
python -m pytest tests/recommender -q
```

Run frontend tests from `apps/web`:

```bash
npm run test
npm run test:e2e
```

## Notes

- Keep tests close to the behavior they validate.
- If runtime behavior changes, update tests in the same change rather than relying on docs-only drift.

## Related Docs

- `../README.md`
- `../instructions/08-quality/testing-strategy.md`
