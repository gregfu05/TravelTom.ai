# Tool Schemas

All tool inputs and outputs must be validated with explicit schemas.

## Example Pydantic models (conceptual)

- `RecommendationQuery`:
  - `session_id: str`
  - `query: str`
  - `constraints: Constraints`
  - `filters: dict`
  - `max_results: int`
  - `ranking_version: str`

- `Constraints`:
  - `origin: str | None`
  - `destination: str | None`
  - `dates: DateRange`
  - `budget: BudgetRange`
  - `party_size: PartySize`

- `RecommendationResult`:
  - `item_id: str`
  - `item_type: Literal["destination", "hotel", "flight"]`
  - `score: float`
  - `rank: int`
  - `features: dict`
  - `explanation: str`

- `CatalogSearchQuery`:
  - `q: str`
  - `type: str`
  - `limit: int`
  - `offset: int`

- `EventPayload`:
  - `event_id: str`
  - `event_type: str`
  - `event_version: int`
  - `occurred_at: datetime`
  - `session_id: str`
  - `user_id: str | None`
  - `idempotency_key: str`
  - `payload: dict`

## Failure handling

- Validation error: do not call the tool; return a user-safe error.
- Tool error: retry once with backoff; if still failing, return a partial response.
- Timeouts: 2s for catalog, 4s for recommendations, 6s for LLM.

## Circuit breakers

- Open circuit after 5 consecutive failures per tool.
- Cooldown: 60 seconds.
- Log circuit events as `system.tool_circuit_open`.

