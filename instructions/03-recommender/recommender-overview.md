# Recommender Overview

## Two-stage design

1. Retrieval: Candidate generation using vector similarity and hard filters.
2. Ranking: Deterministic scoring for MVP; ML ranker for final.

## Fixed implementation decisions

- Recommender runtime boundary: in-process module inside the API service.
- Retrieval backend strategy:
  - Final primary: Azure AI Search.
  - Fallback: PostgreSQL + pgvector (local dev, rollback mode, and low-cost mode).
- Final ML model family: LightGBM.
- Final model registry: Azure ML Registry.

## Goals

- Low-latency candidate generation.
- High-relevance ranking.
- Deterministic and testable behavior.

## Determinism requirements

- Given the same input query, filters, and catalog snapshot, outputs must be identical.
- Tie-breaking must be deterministic and documented.
- Ranking version must be recorded in all outputs and events.

## Retrieval

Purpose: generate a broad candidate set.

Techniques:
- Vector similarity search (query vs item embeddings).
- Hard filters: budget, dates, star rating, location constraints, flight constraints.
- Keyword fallback when vector retrieval returns fewer than 20 candidates.

Output: Top-K candidates (100-300 items) with basic metadata.

Implementations:
- Azure AI Search (primary in final).
- PostgreSQL + pgvector (MVP and fallback).

## Ranking

Purpose: produce final top-N results (default 20, max 50).

Signals:
- Session context (constraints, inferred preferences).
- User profile (historical behavior, final only).
- Item features (price, rating, amenities, popularity).
- Business rules (hard exclusions, diversity constraints).

Midterm:
- Deterministic heuristic scoring.
- Content match, budget fit, popularity/rating.
- Penalties: early flights, long layovers, distance.

Final:
- ML-based ranker (LightGBM).
- Labels derived from logged events.
- Model registry: Azure ML Registry.

## Outputs

- Ranked list of items with scores and explanations derived from ranker features.
- Full feature vector retained for evaluation and debugging.

## Item types

- Destinations
- Hotels
- Flights

## Recommender v2 (active, Yelp parquet)

- Location: `traveltom/recommendor/recommendor_v2.py`
- Dataset: `traveltom/datasets/cleaned_Yelp_DS.parquet` (returns empty results if missing).
- API integration:
  - `apps/api/app/api/v1/recommendations.py` uses v2 for `/api/v1/recommendations/query`.
  - `apps/api/app/api/v1/chat.py` injects v2 into `OrchestratorService`.
- Behavior:
  - Parses user intent for categories (bars, restaurants, pizza, burgers, coffee, shopping, beauty, nightlife, hotels, active life, automotive) and attributes (parking, late night, kid-friendly, outdoor seating, reservations, wifi, alcohol).
  - City is the primary filter: if a city is mentioned and present, only that city’s rows are considered; if the city is absent in the dataset, a friendly message is returned.
  - Filters candidates first on intent (parking via parking columns, late night flag, burgers category, wifi/reservations/alcohol/outdoor/kid-friendly, price tiers) using `cat_*`, `categories_list`, and `categories` text.
  - Ranking: `score = stars + 0.25 * log1p(review_count) + 0.25 * popularity` plus boosts for `weekly_open_minutes` and `weekend_open_minutes`; tie-breaks on `review_count`, `popularity`, `business_id`.
  - Uses additional dataset signals: `categories_list/categories` text, weekly/weekend open minutes boost, price-range filters, parking attributes, wifi/alcohol/reservations/outdoor/kid-friendly flags, burgers category, late-night flag. City filter is active now and ready for country later.
  - Result count: default 5; accepts 1–10; requests above 10 return a polite notice and cap at 10; below 1 defaults to 5.
  - Output per item: place name and a Google Maps link (from latitude/longitude) in `features`; UI only shows these two fields.
  - Future-ready: hook left in filter stage for city/country columns once they are added.
- Tests: `pytest tests/recommender/test_recommender_v2.py` (covers counts, category/attribute filters, late night, parking, map link format, and no-match handling).
