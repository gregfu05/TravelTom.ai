# Instructions Changelog

## 2026-02-11

- Updated deployment documentation to require frontend validation gates (`npm run typecheck` and `npm run build`) alongside backend checks before blue-green rollout.
- Updated CI/CD guidance with explicit backend + frontend command checklist for pre-deploy validation.
- Updated testing strategy to include frontend static quality checks as merge gates when frontend code changes.
- Updated local development docs with a concrete pre-deploy check list for Python and frontend commands.

## 2026-02-10

- Added `05-frontend/ui-design-skill.md` as a dedicated agent-facing UI quality skill for visually strong, consistent frontend work.
- Updated `05-frontend/frontend-architecture.md` to require using the frontend UI design skill during UI implementation.
- Documented the homepage-first frontend baseline in `05-frontend/frontend-architecture.md` (Vite scaffold, app shell, health indicator, and API client behavior).
- Updated `05-frontend/ux-flows.md` to include homepage entry flow and homepage-specific states.
- Updated Step 14 in `09-implementation-plan/implementation-plan.md` to explicitly require homepage implementation before chat flow work.
- Updated frontend docs for standalone `Why TravelTom` and `How It Works` route pages in the MVP baseline.
- Added Step 15 frontend documentation updates for `/planner` chat flow, Zustand session state, `/api/v1/chat` integration, and retry-oriented error states.

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
