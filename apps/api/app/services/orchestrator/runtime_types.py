"""Internal typed orchestration contracts used across runtime phases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from app.schemas.orchestrator import LLMOrchestrationPlan
from app.schemas.state import SessionState
from app.schemas.tools.recommendations import (
    RecommendationQuery,
    RecommendationResult,
    RecommendationToolResponse,
)


@dataclass(frozen=True)
class PreparedTurn:
    """Validated pre-agent state plus normalized planning metadata."""

    session_state: SessionState
    plan: LLMOrchestrationPlan
    acknowledged_slots: list[str]
    planner_used: bool


@dataclass(frozen=True)
class RecommendationExecutionResult:
    """Validated deterministic recommendation execution output."""

    query: RecommendationQuery
    response: RecommendationToolResponse


@dataclass(frozen=True)
class RecommendationOutcome:
    """Normalized recommendation outcome before API response mapping."""

    next_state: SessionState
    recommendations: list[RecommendationResult]
    fallback_message: str
    outcome: str
    candidate_message: str | None = None
    retry_with_expanded_results: bool = False


@dataclass(frozen=True)
class AgentRunResult:
    """Typed accessors for LangChain agent results."""

    messages: list[BaseMessage]

    @classmethod
    def from_raw(cls, agent_result: dict[str, Any]) -> "AgentRunResult":
        raw_messages = agent_result.get("messages")
        if not isinstance(raw_messages, list):
            return cls(messages=[])
        return cls(
            messages=[
                message for message in raw_messages if isinstance(message, BaseMessage)
            ]
        )

    def last_final_ai_message(self) -> AIMessage | None:
        for message in reversed(self.messages):
            if not isinstance(message, AIMessage):
                continue
            if message.tool_calls:
                continue
            return message
        return None

    def last_recommendation_tool_message(self) -> ToolMessage | None:
        for message in reversed(self.messages):
            if not isinstance(message, ToolMessage):
                continue
            if message.name == "recommendation_query":
                return message
        return None

    def last_recommendation_tool_call(self) -> dict[str, Any] | None:
        for message in reversed(self.messages):
            if not isinstance(message, AIMessage):
                continue
            for tool_call in reversed(message.tool_calls):
                if tool_call.get("name") == "recommendation_query":
                    return dict(tool_call)
        return None
