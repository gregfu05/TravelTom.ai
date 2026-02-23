# Tool Schemas

Source of truth:

- `apps/api/app/schemas/tools/recommendations.py`
- `apps/api/app/schemas/tools/catalog.py`
- `apps/api/app/schemas/tools/events.py`

All tool inputs and outputs must pass explicit Pydantic validation.

## Recommendation tool

- `RecommendationQuery`
  - `session_id: str` (required)
  - `query: str` (required)
  - `constraints: RecommendationConstraints` (defaults to empty object)
  - `filters: dict[str, Any]` (default `{}`)
    - supported runtime key: `item_type` (`destination|hotel|flight`)
  - `max_results: int` (default `20`, range `1..50`)
  - `ranking_version: str` (default `"heuristic-v1"`)
- `RecommendationConstraints`
  - `origin: str | None`
  - `destination: str | None`
  - `dates: DateRange | None`
  - `budget: BudgetRange | None`
  - `party_size: PartySize | None`
  - `star_rating_min: int | None` (range `0..5`)
- `RecommendationResult`
  - `item_id: str`
  - `item_type: "destination" | "hotel" | "flight"`
  - `score: float`
  - `rank: int` (>= 1)
  - `features: dict[str, Any]` (default `{}`)
  - `explanation: str`
- `RecommendationToolResponse`
  - `results: list[RecommendationResult]` (default `[]`)
  - `ranking_version: str`

Note: empty recommendation results are valid and expected in placeholder mode.

## Catalog tool

- `CatalogSearchQuery`
  - `q: str`
  - `item_type: "destination" | "hotel" | "flight" | None` (alias input key: `type`)
  - `limit: int` (default `20`, range `1..100`)
  - `offset: int` (default `0`, `>= 0`)

## Events tool

- `EventPayload`
  - `event_id: str`
  - `event_type: str`
  - `event_version: int` (>= 1)
  - `occurred_at: datetime`
  - `session_id: str`
  - `user_id: str | None`
  - `idempotency_key: str` (required)
  - `payload: dict[str, Any]` (default `{}`)

## Failure handling baseline

- Validation failure: block tool execution and return a safe user response.
- Tool timeout/error: return partial orchestration output and prompt for retry.
- Use per-tool timeout policies from orchestration config.

