# Docs

Purpose: supporting notes, investigations, and planning artifacts that sit alongside the main architecture and implementation docs.

Ownership: Mixed.

## What Lives Here

- `azure-deployment-readiness-ticket.md`: repo-native execution ticket for the current Azure dev-first deployment readiness pass, including required owner-provided env/config inputs.
- `chat-production-usability-epic.md`: master epic for bringing the chat feature to a production-usable state, with release gates and child-ticket sequencing.
- `chat-feature-audit.md`: scenario matrix for chat behavior, slot/state expectations, current automated coverage, and residual manual release checks.
- `chat-contract-alignment-ticket.md`: ticket for aligning chat docs, tests, smoke expectations, and the supported scenario matrix.
- `chat-state-integrity-ticket.md`: ticket for fixing extraction, slot persistence, and session-state integrity defects.
- `chat-conversation-policy-ticket.md`: ticket for fixing clarification order, repair handling, and conversation naturalness.
- `chat-provider-reliability-ticket.md`: ticket for hardening planner/composer runtime reliability and operational behavior.
- `chat-release-verification-ticket.md`: ticket for expanding automated coverage and release verification for chat.
- `ollama-remote-deployment.md`: deployment notes for running Ollama remotely with env-driven backend configuration.
- `azure-mlops-ranking-plan.md`: planning document for future Azure-based MLOps of the ranking model lifecycle.

## How This Folder Differs From `instructions/`

- Use `instructions/` for architecture rules, implementation guidance, and project standards.
- Use `docs/` for narrower investigations, exploratory plans, or support material that should not become the primary source of truth for the whole repo.

## Related Docs

- `../README.md`
- `../instructions/README.md`
