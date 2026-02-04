# Design Summary

This document summarizes the TravelTom design and highlights non-negotiable requirements from `TravelTom_Final_Design_Document.pdf`.

## Product overview

TravelTom is an AI-powered travel agent that enables users to plan trips end-to-end through a conversational interface. The system captures intent, constraints, and preferences via chat, then produces ranked recommendations and itineraries that users can iteratively refine.

## Non-negotiables

- The LLM orchestrates only; it does not invent recommendations.
- All recommendations originate from a versioned, deterministic Recommendation Service.
- Two-stage recommender: retrieval then ranking.
- Strict schema validation for all LLM tool calls and responses.
- Event logging is mandatory (impressions, clicks, saves, dismissals, booking funnel events).
- P95 latency is tracked for chat and recommendation endpoints.
- Clear separation between experimentation (`traveltom/`), runtime services (`apps/`), and infrastructure (`infra/`).

## Functional requirements

- Conversational chat interface for constraint and preference capture.
- Recommendations for destinations, hotels, and flights.
- Shortlist management (save, dismiss, compare).
- Day-by-day itinerary draft generation.
- Booking workflow stubs (no real transactions in MVP).
- Event logging for impressions and user actions.

## MVP non-goals (midterm)

- Real booking integrations with external providers.
- End-to-end ML ranking training pipelines.
- Event streaming infrastructure beyond database logging.

