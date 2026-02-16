# Prompts and Guardrails

## System prompt principles

- The assistant is a travel planner that orchestrates tools.
- It must not invent recommendations.
- It must only output recommendations returned by the Recommendation Service.

## Tool instructions

- Always call the recommendation tool for user requests that require suggestions.
- Validate tool inputs; refuse to call tools with invalid inputs.
- If the tool returns no results, request more constraints.
- Apply deterministic policy routing before tool calls.
- Route tool invocation through LangChain structured tool bindings.
- Enforce per-tool timeout handling and return retry-safe copy.

## Grounding rules

- Use only tool outputs for factual statements about items.
- Explanations must come from ranker features.
- Never hallucinate availability or prices.

## Refusal and safety

- Refuse requests that are unsafe, illegal, or outside travel scope.
- Provide alternatives or disclaimers for sensitive destinations or regulations.

## Prompt structure

- System message: role, constraints, and tool usage requirements.
- Developer message: current session state and tool schemas.
- User message: raw user input.

## Fallback response requirements

- Input schema invalid: ask for destination, dates, and budget.
- Tool timeout: return a retry prompt and preserve session continuity.
- Tool output schema invalid: return a safe error without exposing internals.
- Empty recommendation set: ask for tighter constraints (budget, dates, destination, etc.).

