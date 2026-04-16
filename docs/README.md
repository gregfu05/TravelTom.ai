# Docs

Purpose: supporting notes, investigations, and planning artifacts that sit alongside the main architecture and implementation docs.

Ownership: Mixed.

## What Lives Here

- `azure-deployment-readiness-ticket.md`: repo-native execution ticket for the current Azure dev-first deployment readiness pass, including required owner-provided env/config inputs.
- `chat-feature-investigation-ticket.md`: investigation ticket for chat latency, naturalness, context persistence, and recommendation continuity.
- `ollama-remote-deployment.md`: deployment notes for running Ollama remotely with env-driven backend configuration.
- `azure-mlops-ranking-plan.md`: planning document for future Azure-based MLOps of the ranking model lifecycle.

## How This Folder Differs From `instructions/`

- Use `instructions/` for architecture rules, implementation guidance, and project standards.
- Use `docs/` for narrower investigations, exploratory plans, or support material that should not become the primary source of truth for the whole repo.

## Related Docs

- `../README.md`
- `../instructions/README.md`
