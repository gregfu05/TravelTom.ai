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

## Minimal recommender v1 (temporary)

- Location: `traveltom/recommendor/recommendor_v1.py`
- API integration: `apps/api/app/api/v1/recommendations.py` imports `recommendation_tool` and exposes it via `/api/v1/recommendations/query`.
- Behavior: single-result lookup from `business_SB_cleaned.parquet`, selecting the highest `stars` item for the inferred `cat_*` category (shopping, restaurants, bars, nightlife). Falls back to the overall top-rated business when no category matches. Tie-breakers use `review_count` then `popularity`.
- Tests: `pytest tests/recommender/` (covers category routing, fallback, and tie-breaking).
