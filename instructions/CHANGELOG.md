# Instructions Changelog

## 2026-02-12

- Added `04-llm-orchestrator/chatbot-orchestration-skill.md` defining the chatbot/orchestration implementation skill and quality bar.
- Updated `04-llm-orchestrator/session-state-schema.md` to match implemented Pydantic models in `apps/api/app/schemas/state.py`.
- Updated `04-llm-orchestrator/tool-schemas.md` to match implemented tool contracts in `apps/api/app/schemas/tools/*`.
- Linked the new skill doc from `04-llm-orchestrator/orchestrator-overview.md`.
- Updated orchestrator instructions for Step 10 with implemented policy routing, timeout handling, and placeholder recommendation behavior.
- Updated prompt/guardrail instructions with explicit fallback requirements for invalid inputs, tool timeouts, invalid tool payloads, and empty results.
- Updated `02-backend/api-design.md` with Step 11 chat endpoint implementation notes, persistence behavior, and FastAPI 422 validation status.
- Added Step 12 recommendation query endpoint notes in `02-backend/api-design.md`, including schema-validation behavior and placeholder-mode empty results.

## 2026-02-06

- Converted `OPEN_QUESTIONS.md` to active provisional decisions with a lock timestamp.
- Fixed recommender decisions: in-process runtime, LightGBM model family, Azure AI Search primary with pgvector fallback, Azure ML Registry.
- Added explicit evaluation gates, retraining cadence, retraining triggers, and required training artifacts.
- Locked final deployment target to Azure Container Apps and documented blue-green rollout and rollback behavior.
- Added budget-mode constraints with a USD 10/month cloud spend cap.
- Added model drift checks, thresholds, and alert ownership in observability docs.
- Added ML CI/CD promotion gates, manifest requirements, and reviewer approvals.
- Fixed event pipeline and taxonomy ambiguity (mandatory final dual-write, explicit `message_id` requirements, deletion SLA).
- Locked final auth provider path to Azure AD B2C and added secret rotation and access rules.
- Updated implementation plan wording to LightGBM and Azure AD B2C.
- Added explicit Zen of Python enforcement rules and Python PR checklist in `08-quality/code-standards.md`.
- Added Zen of Python compliance requirement to coding-agent rules and quality gates in `README.md`.
- Updated event data-model documentation to require `session_id` and scoped idempotency uniqueness.

## 2026-02-04

- Updated documentation to align with `TravelTom_Final_Design_Document.pdf` (requirements, architecture, recommender, orchestrator, events, and plan).
- Adjusted repo structure to `apps/api` and `apps/web` and updated paths across the plan.
- Refined recommender specs with retrieval sizes, ranking signals, and flight penalties.
- Reduced open questions to those explicitly listed in the design doc.
- Noted runtime README placeholders in `repo-structure.md`.
- Added health endpoint to backend docs and layout.
- Documented Alembic config path usage in migrations guide.
- Added guidance to use `.env` for configuration and avoid hard-coded env vars.
- Noted ORM model location in data model documentation.
- Documented CI security automation (CodeQL, Gitleaks, Dependabot).
- Added Ruff, Black, and mypy tooling references in CI/CD docs.
- Added quality checks workflow for all branches and PRs to main.
- Scoped CodeQL to Python until frontend code is present.

## 2026-02-04

- Initial creation of instructions folder and documentation set.
