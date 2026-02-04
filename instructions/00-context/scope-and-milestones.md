# Scope and Milestones

This document defines MVP (midterm) vs final (production-grade demo) scope per the design document.

## MVP (midterm)

Deliverables:
- Chat-based web app.
- Recommendation API.
- Shortlist interactions.
- Local Postgres + vector store (pgvector).
- Basic catalog ingestion.
- Deterministic heuristic re-ranking.
- Event logging in DB.

Explicit non-goals:
- Real booking integrations.
- ML training pipelines.
- Event streaming systems.

## Final (production-grade demo)

Deliverables:
- Azure-deployed frontend and backend.
- Managed Postgres and vector store (Azure AI Search preferred).
- Offline feature pipelines.
- Trained ML ranker with versioned model registry.
- Scheduled offline evaluation.
- Event streaming via Event Hub.
- Improved LLM routing and guardrails.

Non-goals:
- Full commercial booking engine.
- Dynamic pricing or real-time inventory.

