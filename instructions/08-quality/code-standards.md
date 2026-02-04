# Code Standards

## Python

- Formatter: Black
- Linter: Ruff
- Type checking: Mypy
- Docstrings: Google style

## TypeScript

- Linter: ESLint
- Formatter: Prettier
- Type checking: tsc

## API schema conventions

- Pydantic models for all request/response bodies.
- JSON field names use snake_case in backend and are mapped to camelCase in frontend.
- All responses include `trace_id` in error cases.

## Documentation

- Update related docs for any public API, schema, or ranking change.
- Add or update ADRs for significant architectural decisions.

