"""Deterministic orchestration guardrails and prompt-context builders."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from app.schemas.orchestrator import (
    Intent,
    LLMOrchestrationPlan,
    RecommendationQueryControls,
)
from app.schemas.state import SessionState
from app.schemas.tools.recommendations import RecommendationResult

_RECOMMEND_KEYWORDS = (
    "recommend",
    "suggest",
    "plan",
    "trip",
    "vacation",
    "holiday",
    "where should",
)
_REFINE_KEYWORDS = (
    "cheaper",
    "budget",
    "closer",
    "better",
    "refine",
    "filter",
    "compare",
    "another option",
)


@dataclass(frozen=True)
class OrchestratorPolicyConfig:
    """Static policy settings for orchestrator runtime behavior."""

    recommendation_timeout_seconds: float = 4.0
    max_recommendation_results: int = 5


@dataclass(frozen=True)
class OrchestrationDecision:
    """Output of deterministic guardrail logic before tool execution."""

    intent: Intent
    should_call_recommendation_tool: bool
    reason: str


def classify_intent(message: str) -> Intent:
    """Classify user intent with deterministic keyword matching."""

    lowered = message.casefold()
    if any(keyword in lowered for keyword in _REFINE_KEYWORDS):
        return "refine"
    if any(keyword in lowered for keyword in _RECOMMEND_KEYWORDS):
        return "recommend"
    return "clarify"


def decide_next_action(message: str, state: SessionState) -> OrchestrationDecision:
    """Deterministic guardrail for routing when LLM planning is unavailable."""

    intent = classify_intent(message)
    if intent in {"recommend", "refine"}:
        return OrchestrationDecision(
            intent=intent,
            should_call_recommendation_tool=True,
            reason=f"{intent} intent detected",
        )

    if state.status in {"refine", "itinerary", "booking"}:
        return OrchestrationDecision(
            intent="refine",
            should_call_recommendation_tool=True,
            reason="continuation of an active planning session",
        )

    return OrchestrationDecision(
        intent="clarify",
        should_call_recommendation_tool=False,
        reason="insufficient recommendation intent",
    )


def missing_core_constraints(state: SessionState) -> list[str]:
    """Return human-readable missing constraints for guidance prompts."""

    missing: list[str] = []
    if not state.constraints.destination:
        missing.append("destination")
    if not state.constraints.dates:
        missing.append("travel dates")
    if not state.constraints.budget:
        missing.append("budget range")
    return missing


def build_clarification_message(session_state: SessionState) -> str:
    """Build deterministic clarification copy from missing constraints."""

    missing = missing_core_constraints(session_state)
    if not missing:
        return "Tell me what to optimize for, like cheaper options or fewer layovers."
    if len(missing) == 1:
        return f"Please share your {missing[0]} so I can suggest options."
    joined = ", ".join(missing[:-1]) + f", and {missing[-1]}"
    return f"Please share your {joined} so I can suggest options."


def build_guardrail_plan(
    *,
    message: str,
    session_state: SessionState,
    max_results: int,
) -> LLMOrchestrationPlan:
    """Build a deterministic plan when LLM planning fails."""

    decision = decide_next_action(message=message, state=session_state)
    clarification_message = None
    if not decision.should_call_recommendation_tool:
        clarification_message = build_clarification_message(session_state)
    return LLMOrchestrationPlan(
        intent=decision.intent,
        should_call_recommendation_tool=decision.should_call_recommendation_tool,
        clarification_message=clarification_message,
        query_controls=RecommendationQueryControls(max_results=max_results),
    )


def build_planning_prompt_context(
    *,
    session_state: SessionState,
    user_message: str,
    max_results: int,
) -> str:
    """Build prompt context for LLM planning."""

    state_payload = json.dumps(session_state.model_dump(mode="json"), sort_keys=True)
    return (
        "You are the TravelTom orchestration planner.\n"
        "Return JSON only.\n"
        "Primary duties: interpret intent, choose whether to call recommendation tool, "
        "and propose structured state updates.\n"
        "Never fabricate recommendation items.\n"
        f"Recommendation max_results hard limit for this turn: {max_results}.\n"
        "Valid JSON shape:\n"
        "{\n"
        '  "intent": "recommend|refine|clarify",\n'
        '  "should_call_recommendation_tool": true|false,\n'
        '  "clarification_message": "required when tool call is false",\n'
        '  "state_patch": {\n'
        '    "constraints": {\n'
        '      "origin": "string|null",\n'
        '      "destination": "string|null",\n'
        '      "dates": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}|null,\n'
        '      "trip_length_days": 1|null,\n'
        '      "budget": {"min": 0, "max": 0, "currency": "USD"}|null,\n'
        '      "party_size": {"adults": 1, "children": 0}|null\n'
        "    },\n"
        '    "preferences": {"weighted_interests": {"key": 0.8}, '
        '"dislikes": ["text"]},\n'
        '    "entities": {"destinations": ["string"]},\n'
        '    "status": "explore|refine|itinerary|booking"\n'
        "  },\n"
        '  "query_controls": {\n'
        '    "query": "string|null",\n'
        '    "filters": {"item_type": "destination|hotel|flight"},\n'
        '    "max_results": 1\n'
        "  }\n"
        "}\n"
        f"Current session state JSON: {state_payload}\n"
        f"Latest user message: {user_message}"
    )


def build_response_prompt_context(
    *,
    session_state: SessionState,
    user_message: str,
    recommendations: list[RecommendationResult],
    fallback_message: str,
    outcome: Literal["results", "empty_results"],
) -> str:
    """Build prompt context for grounded response composition."""

    state_payload = json.dumps(session_state.model_dump(mode="json"), sort_keys=True)

    def _display_name(item: RecommendationResult) -> str:
        name = item.features.get("name")
        if isinstance(name, str):
            normalized = name.strip()
            if normalized:
                return normalized
        return item.item_id

    if recommendations:
        recommendation_lines = [
            (
                f"rank={item.rank}; name={_display_name(item)}; "
                f"type={item.item_type}; item_id={item.item_id}; "
                f"score={item.score:.4f}; explanation={item.explanation}"
            )
            for item in recommendations
        ]
        recommendation_block = "\n".join(recommendation_lines)
    else:
        recommendation_block = "NO_RESULTS"

    return (
        "You are the TravelTom response composer.\n"
        'Return JSON only in the form {"assistant_message": "..."}.\n'
        "Grounding rules:\n"
        "- Use only the recommendation list provided below.\n"
        "- Prefer recommendation names in user-facing text.\n"
        "- Do not invent item ids, prices, or availability.\n"
        "- If no recommendations exist, ask for tighter constraints.\n"
        f"- If you are uncertain, use this exact fallback message: {fallback_message}\n"
        f"Outcome: {outcome}\n"
        f"Current session state JSON: {state_payload}\n"
        f"Latest user message: {user_message}\n"
        f"Recommendation records:\n{recommendation_block}"
    )
