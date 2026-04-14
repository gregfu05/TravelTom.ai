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
    - supported runtime key: `item_type` (`hotel|restaurant|activity`)
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
  - `item_type: "hotel" | "restaurant" | "activity"`
  - `score: float`
  - `rank: int` (>= 1)
  - `features: dict[str, Any]` (default `{}`)
  - `explanation: str`
- `RecommendationToolResponse`
  - `results: list[RecommendationResult]` (default `[]`)
  - `ranking_version: str`

Note: empty recommendation results are valid and expected in placeholder mode.

## Orchestrator usage notes (LangChain-native flow)

- `TravelTomAgent` registers the recommendation tool once with LangChain's
  `@tool` decorator and supplies it to two `create_agent` instances:
  - a bounded chat agent
  - a deterministic direct recommendation agent
- `ranking_version` remains pinned to `"heuristic-v1"` in orchestrator runtime.
- `max_results` defaults to the chat policy value (`5`) in the bounded chat
  fallback path and remains request-driven for `/api/v1/recommendations/query`.
- `filters.item_type` is normalized to `hotel|restaurant|activity` with
  deterministic extraction when absent from the agent path.
- The tool returns a LangChain runtime artifact with:
  - `status`: `success|timeout|invalid_payload|failure`
  - `response`: validated `RecommendationToolResponse` on success
  - `error_code` / `error_message` on failure
- Direct recommendation mode uses the same `RecommendationQuery` and
  `RecommendationToolResponse` contracts and returns only validated tool-backed
  results to the route.

## Catalog tool

- `CatalogSearchQuery`
  - `q: str`
  - `item_type: "hotel" | "restaurant" | "activity" | None` (alias input key: `type`)
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
- Tool timeout/error: normalize to a runtime artifact and return a deterministic safe response.
- Use per-tool timeout policies from orchestration config.
