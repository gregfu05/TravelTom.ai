# Recommender Overview

## Runtime source of truth

- Active API runtime: `traveltom/recommendor/recommendor_v1.py`
- Runtime data source: PostgreSQL `catalog_items`
- Shared runtime adapter: `apps/api/app/services/recommendation_runtime.py`
- Endpoints using that runtime:
  - `/api/v1/recommendations/query`
  - `/api/v1/chat`

The chat and recommendation endpoints no longer depend on a CSV file at runtime.
`RECOMMENDER_DATASET_PATH` remains a legacy/offline setting and is not part of
the live API path.

## Runtime behavior

- Reads the seeded catalog from `catalog_items`.
- Applies hard destination filtering from `RecommendationQuery.constraints.destination`.
- Applies hard item-type filtering from `RecommendationQuery.filters.item_type`.
- Uses deterministic scoring and tie-breaking.
- Returns validated `RecommendationToolResponse`.

## Operational implications

- Local/dev and deployed environments must seed `catalog_items` before chat
  recommendations are expected to succeed.
- `preload_recommendation_catalog(...)` now preloads the same runtime catalog
  used by both chat and direct recommendation queries.
- Empty runtime catalog is treated as an operator/runtime problem, not as a
  missing CSV boot path.

## Offline assets

- `scripts/seed_catalog.py` remains the supported ingestion path for loading
  cleaned data into `catalog_items`.
- `traveltom/datasets/*` and legacy dataset-path settings are offline inputs for
  cleaning, training, or seeding workflows.

## Verification

- `venv\Scripts\python.exe -m pytest tests\api\test_recommendation_runtime.py tests\api\test_recommendations.py -q`
- `pwsh ./scripts/smoke-api.ps1 -BaseUrl http://localhost:8000`
