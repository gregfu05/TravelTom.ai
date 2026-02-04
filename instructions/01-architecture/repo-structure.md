# Repository Structure

Expected top-level layout (new additions only; existing folders are preserved):

```
/apps
  /api
  /web
  /worker  (optional, final)
/infra
  /docker
    /db
  /azure
/scripts
/tests
/instructions
/traveltom  (existing experimentation; keep as-is)
```

## Folder purposes

- `apps/api`: FastAPI app, Pydantic models, services, and DB access.
- `apps/web`: React app with chat UI and related views.
- `apps/worker`: Optional background jobs for final (feature pipelines, batch eval).
- `infra/docker`: Docker Compose and local dev infrastructure.
- `infra/azure`: Bicep/Terraform or deployment scripts for Azure.
- `scripts`: Data ingestion, evaluation harness, and local tooling.
- `tests`: Unit, integration, and contract tests across services.
- `instructions`: This documentation set.
- `traveltom`: Existing prototypes and experiments. Do not refactor.

