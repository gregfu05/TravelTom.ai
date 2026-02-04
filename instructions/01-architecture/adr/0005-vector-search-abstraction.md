# ADR: Retrieval abstraction for pgvector and Azure AI Search

- Status: Accepted
- Date: 2026-02-04

## Context

MVP uses pgvector for retrieval; final uses Azure AI Search. We need a shared interface so the rest of the system remains stable.

## Decision

Introduce a retrieval interface with a common query and response schema. Provide two implementations: `PgVectorRetriever` and `AzureSearchRetriever`, selectable via configuration.

## Alternatives considered

- Direct integration with pgvector only: Blocks migration to Azure AI Search.
- Dual-path logic scattered across services: Risky and hard to test.

## Consequences

- Positive: Clean swap of retrieval backends, testable isolation.
- Negative: Slightly more boilerplate upfront.
- Risks: Feature mismatch between backends; mitigate by limiting the interface to common capabilities.

## Notes

See `03-recommender/recommender-overview.md`.

