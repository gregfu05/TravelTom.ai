# Open Questions

This file tracks ambiguities or missing details from the design document. Each item includes a recommended default and alternatives.

## 1. Coverage requirement ("Coverage >= N candidates")

Question: What is the exact minimum coverage per category and total results?
Recommended default: At least 5 per requested category and 20 total.
Alternatives: Per category only, or total only.
Decision needed: Confirm thresholds for evaluation and ranking.

## 2. Flight data realism in MVP

Question: Should flight data be fully dummy or partially realistic (e.g., real carriers and schedules but static prices)?
Recommended default: Dummy flights with realistic-looking metadata but static pricing.
Alternatives: Partial realism or omit flights from MVP UI.
Decision needed: Confirm data source and required fidelity.

## 3. Personalization persistence

Question: Should user preferences persist across sessions?
Recommended default: Session-level only for MVP; optional account-level for final.
Alternatives: Immediate account-level persistence.
Decision needed: Confirm storage and privacy implications.

