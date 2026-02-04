# Explanation Generation

## Principle

Explanations must be derived ONLY from ranker features and business rules. The LLM must not invent explanations.

## Example explanation clauses

- "Matches museums preference"
- "Within budget range"
- "Walkable neighborhood"
- "Low layover time"

## Assembly rules

- Pick at most 2 explanation clauses.
- Order by feature importance (similarity, budget fit, rating, popularity, penalties).
- If no clause meets thresholds, use: "A good overall match for your request."

## Tests

- Given a fixed feature vector, explanation is deterministic.
- No mention of attributes that are missing or below threshold.

