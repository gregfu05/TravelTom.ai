# Code Standards

## Python

- Formatter: Black
- Linter: Ruff
- Type checking: Mypy
- Docstrings: Google style

### Zen of Python enforcement (PEP 20)

All Python changes must follow these principles:

- Explicit is better than implicit:
  - Use clear variable names, explicit return values, and type hints on public functions.
  - Avoid hidden side effects and implicit global state.
- Simple is better than complex:
  - Prefer straightforward control flow and small composable functions.
  - Use early returns to reduce unnecessary nesting.
- Complex is better than complicated:
  - Avoid clever tricks, metaprogramming, or one-liners that reduce readability.
  - If complexity is required, isolate it behind a well-named function and short docstring.
- Flat is better than nested:
  - Keep branching depth shallow where practical (target depth <= 3).
- Readability counts:
  - Prioritize clarity over terseness.
  - Keep error messages actionable and specific.
- Errors should never pass silently:
  - Do not use bare `except:`.
  - Catch specific exceptions and either handle with context or re-raise.
- In the face of ambiguity, refuse the temptation to guess:
  - Validate external inputs at boundaries (API, events, configs) and fail fast on invalid data.
- There should be one obvious way to do it:
  - Reuse shared utilities and service patterns instead of introducing parallel patterns.
- Namespaces are one honking great idea:
  - Keep module boundaries clean and place code in the existing service/domain package.

### Python review checklist

For PRs touching Python code, reviewers must verify:

- Logic is explicit and readable without reverse engineering.
- Exception handling is specific and test-covered.
- Input validation and failure behavior are defined.
- New abstractions are necessary and align with existing module boundaries.

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
