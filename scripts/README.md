# Scripts

Purpose: seeding, evaluation, smoke checks, and local helper tooling.

Ownership: Backend/Data.

## What Lives Here

- `seed_catalog.py`: loads a cleaned snapshot into `catalog_items`.
- `train_ranker_v3.py`: ranker training entrypoint.
- `evaluate_ranker_v3.py`: evaluation helper for the recommender pipeline.
- `check_ranker_gates.py`: gate/check helper for ranking outputs.
- `smoke-api.ps1`: API smoke verification.
- `smoke-web.ps1`: web smoke verification.

## Common Tasks

### Catalog seeding

Load the cleaned Yelp snapshot into `catalog_items`:

```bash
python scripts/seed_catalog.py --truncate
```

Preview without writing:

```bash
python scripts/seed_catalog.py --dry-run
```

The seed script defaults to `traveltom/datasets/composite/traveltom_clean.csv`.
Parquet-era Santa Barbara snapshots remain legacy artifacts and are not used by
the active seed path.

### Smoke checks

```bash
pwsh ./scripts/smoke-api.ps1 -BaseUrl http://localhost:8000
pwsh ./scripts/smoke-web.ps1 -BaseUrl http://localhost:5173
```

## Smoke checks

API health plus deterministic recommendation endpoint:

```bash
pwsh ./scripts/smoke-api.ps1 -BaseUrl http://localhost:8000
```

If auth is enabled locally, `smoke-api.ps1` can create a temporary account on
its own, or you can pass `-AccessToken`, `-Email`, and `-Password`.

Conversational runtime checks across greeting, slot gating, complete hotel
search, same-session refinement continuity, empty-results recovery,
follow-up carry-forward, generic search-type clarification, repair turns,
unsupported-flight refusal, and direct recommendation execution:

```bash
pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl http://localhost:8000 -Provider disabled
pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl http://localhost:8000 -Provider ollama
```

If you need a stable auth credential for repeated runs, pass `-Password`
explicitly or set `TRAVELTOM_SMOKE_PASSWORD`. Otherwise the script generates a
one-off password for the temporary smoke account it creates.

For the full scenario matrix, expected slot/state outcomes, and manual release
checks that still sit outside automated smoke coverage, see
`docs/chat-feature-audit.md`.
