# Tool Schemas

Source of truth:

- `apps/api/app/schemas/tools/recommendations.py`
- `apps/api/app/schemas/tools/catalog.py`
- `apps/api/app/schemas/tools/events.py`

All tool inputs and outputs must pass explicit Pydantic validation.

## Recommendation tool

- `RecommendationQuery`
  - `session_id: str`
  - `query: str`
  - `constraints: RecommendationConstraints`
  - `filters: dict[str, Any]`
    - supported runtime key: `item_type` (`hotel|restaurant|activity`)
  - `max_results: int`
  - `ranking_version: str`
- `RecommendationConstraints`
  - `origin: str | None`
  - `destination: str | None`
  - `dates: DateRange | None`
  - `budget: BudgetRange | None`
  - `party_size: PartySize | None`
  - `star_rating_min: int | None`
- `RecommendationResult`
  - `item_id: str`
  - `item_type: "hotel" | "restaurant" | "activity"`
  - `score: float`
  - `rank: int`
  - `features: dict[str, Any]`
  - `explanation: str`
- `RecommendationToolResponse`
  - `results: list[RecommendationResult]`
  - `ranking_version: str`

## Orchestrator usage notes

- `/api/v1/chat` does not rely on model-authored tool calls.
- Backend code builds and executes `RecommendationQuery` directly.
- `ranking_version` remains pinned to `"heuristic-v1"` in the conversational runtime.
- Chat default `max_results` stays policy-driven; direct recommendation requests remain request-driven.
- `filters.item_type` is normalized to `hotel|restaurant|activity` by backend guardrails.
- Empty recommendation results remain valid and expected.

## Catalog tool

- `CatalogSearchQuery`
  - `q: str`
  - `item_type: "hotel" | "restaurant" | "activity" | None`
  - `limit: int`
  - `offset: int`

## Events tool

- `EventPayload`
  - `event_id: str`
  - `event_type: str`
  - `event_version: int`
  - `occurred_at: datetime`
  - `session_id: str`
  - `user_id: str | None`
  - `idempotency_key: str`
  - `payload: dict[str, Any]`

## Failure handling baseline

- Validation failure: block execution and return a safe response.
- Recommendation timeout/error: normalize to deterministic fallback copy.
- Invalid payload: reject it rather than guessing.
