# Heuristic Ranker Spec

## Version

- Ranking version: `heuristic_v1`
- Changes require a new version and updated tests.

## Inputs

- `Candidate` fields (common):
  - `similarity` in [0, 1] (content match)
  - `price` numeric
  - `budget_min`, `budget_max`
  - `rating` in [0, 5]
  - `popularity` in [0, 1]
  - `distance_km` (optional for hotels, restaurants, and activities)

## Normalization

- `rating_norm = rating / 5.0`
- `target_budget = (budget_min + budget_max) / 2`
- `budget_fit = 1 - min(|price - target_budget| / max(target_budget, 1), 1)`
- `popularity_norm = popularity`
- `distance_norm = 1 / (1 + distance_km)` (if missing, use 0.5)

## Scoring formula

Base score (all items):

```
base =
  0.40 * similarity +
  0.25 * budget_fit +
  0.20 * rating_norm +
  0.10 * popularity_norm +
  0.05 * distance_norm
```

Final score:

```
score = clamp(base, 0, 1)
```

- Round scores to 6 decimal places before sorting.

## Tie-breaking

1. Higher `score`
2. Higher `similarity`
3. Higher `rating`
4. Lexicographic `item_id`

## Determinism rules

- Input ordering must not affect output.
- Always use stable sorting with explicit tie-break keys.

## Unit tests

- Deterministic ordering for a fixed candidate set.
- Score monotonicity for each feature.
- Tie-break order is stable with equal scores.
