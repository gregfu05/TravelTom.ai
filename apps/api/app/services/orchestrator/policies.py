"""Deterministic routing policies for tool-first orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.schemas.state import SessionState

Intent = Literal["recommend", "refine", "clarify"]

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
    max_recommendation_results: int = 20


@dataclass(frozen=True)
class OrchestrationDecision:
    """Output of deterministic decision logic before tool execution."""

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
    """Decide whether to call tools or ask clarifying questions."""

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
