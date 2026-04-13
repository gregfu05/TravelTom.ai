"""Deterministic orchestration guardrails and prompt-context builders."""

from __future__ import annotations

import json
import re
from typing import Literal

from app.schemas.orchestrator import (
    Intent,
    LLMOrchestrationPlan,
    OrchestrationDecision,
    RecommendationQueryControls,
    TranscriptMessage,
)
from app.schemas.state import SessionState
from app.schemas.tools.recommendations import RecommendationResult
from app.services.orchestrator.extraction import (
    build_effective_recommendation_query_text,
    extract_query_filters,
    is_follow_up_refinement,
    is_vague_acceptance_reply,
    resolve_effective_item_type,
)

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
    "closer",
    "better",
    "refine",
    "filter",
    "compare",
    "another option",
)
_DESTINATION_EXPLORATION_KEYWORDS = (
    "beach",
    "city break",
    "family friendly",
    "family-friendly",
    "food",
    "nature",
    "nightlife",
    "relax",
    "romantic",
    "weekend getaway",
)
_META_PATTERNS = (
    r"\bwhat do you mean\b",
    r"\bwhat do you mean by\b",
    r"\bwhy do you need\b",
    r"\bwhy are you asking\b",
    r"\bhow do you mean\b",
    r"\bhow do you have\b",
    r"\bwhat is a\b",
)
_GREETING_PATTERNS = (
    r"^\s*(hello|hi|hey|yo|howdy)\b",
    r"^\s*good\s+(morning|afternoon|evening)\b",
    r"^\s*bonjour\b",
)
_REPAIR_PATTERNS = (
    r"^\s*not\b",
    r"\bmore like\b",
    r"\binstead\b",
    r"\brather than\b",
    r"\bactually\b",
    r"^\s*no[, ]",
    r"\bi mean\b",
    r"\bi meant\b",
)
_TRAVELTOM_PERSONA = (
    "TravelTom is a warm, expert travel assistant: grounded, concise, and helpful. "
    "Sound natural and conversational without being chatty. Be proactive about "
    "missing details, but never overstate certainty."
)
_CORE_SLOT_ORDER = ("destination", "dates", "budget")
_CORE_SLOT_LABELS = {
    "origin": "departure city",
    "destination": "destination",
    "dates": "travel dates",
    "budget": "budget range",
}
_CORE_SLOT_QUESTIONS = {
    "origin": "Where are you flying from?",
    "destination": "Which destination should I focus on?",
    "dates": "What travel dates should I plan around?",
    "budget": "What budget range should I use?",
}
_ITEM_TYPE_REQUIRED_SLOT_ORDER = {
    "hotel": ("destination", "dates", "budget"),
    "flight": ("origin", "destination", "dates", "budget"),
    "destination": (),
}
_ITEM_TYPE_LABELS = {
    "destination": "destination ideas",
    "hotel": "hotel recommendations",
    "flight": "flight recommendations",
}
_SEARCH_TYPE_QUESTION = (
    "Do you want hotel recommendations, flight options, or destination ideas?"
)
_SEARCH_TYPE_QUESTION_WITH_DESTINATION = (
    "I have your destination, dates, and budget. Should I look for hotel "
    "recommendations or flights?"
)
_SEARCH_TYPE_FOLLOW_UP_QUESTION = (
    "Do you want hotel recommendations, flight options, or destination ideas?"
)
_SEARCH_TYPE_FOLLOW_UP_QUESTION_WITH_DESTINATION = (
    "Should I look for hotel recommendations or flights?"
)
_TRANSCRIPT_MESSAGE_MAX_CHARS = 240


def classify_intent(message: str) -> Intent:
    """Classify user intent with deterministic keyword matching."""

    lowered = message.casefold()
    if any(keyword in lowered for keyword in _REFINE_KEYWORDS):
        return "refine"
    if any(keyword in lowered for keyword in _RECOMMEND_KEYWORDS):
        return "recommend"
    return "clarify"


def is_greeting(message: str) -> bool:
    """Return whether the user message is a lightweight greeting."""

    stripped_message = message.strip()
    if not stripped_message:
        return False
    lowered = stripped_message.casefold()
    if any(keyword in lowered for keyword in _RECOMMEND_KEYWORDS + _REFINE_KEYWORDS):
        return False
    return any(
        re.search(pattern, stripped_message, flags=re.IGNORECASE)
        for pattern in _GREETING_PATTERNS
    )


def build_greeting_message() -> str:
    """Build deterministic copy for greeting/opening turns."""

    return (
        "Hi, I'm Tom. Tell me where you want to go, or share destination, dates, "
        "and budget and I'll turn that into grounded recommendations."
    )


def decide_next_action(message: str, state: SessionState) -> OrchestrationDecision:
    """Deterministic guardrail for routing when LLM planning is unavailable."""

    if is_greeting(message):
        return OrchestrationDecision(
            intent="clarify",
            should_call_recommendation_tool=False,
            reason="greeting should stay conversational",
        )

    if is_meta_question(message):
        return OrchestrationDecision(
            intent="clarify",
            should_call_recommendation_tool=False,
            reason="meta question should stay conversational",
        )

    if is_repair_turn(message):
        return OrchestrationDecision(
            intent="clarify",
            should_call_recommendation_tool=False,
            reason="repair turn needs clarification before another search",
        )

    if (
        state.conversation.last_clarification_kind == "refine_preference"
        and state.conversation.last_search_outcome
        in {"empty_results", "no_new_results"}
        and is_vague_acceptance_reply(message)
    ):
        return OrchestrationDecision(
            intent="clarify",
            should_call_recommendation_tool=False,
            reason="vague reply after empty results needs stronger guidance",
        )

    active_intent = _active_recommendation_intent(message=message, state=state)
    resolved_item_type = resolve_effective_item_type(
        message=message,
        session_state=state,
    )
    missing_slots = missing_core_constraint_slots(
        state,
        item_type_override=resolved_item_type,
    )
    needs_search_type = (
        needs_search_type_clarification(state) and resolved_item_type is None
    )

    if active_intent in {"recommend", "refine"}:
        if needs_search_type:
            return OrchestrationDecision(
                intent="clarify",
                should_call_recommendation_tool=False,
                reason="search type clarification is still needed",
            )
        if missing_slots:
            return OrchestrationDecision(
                intent="clarify",
                should_call_recommendation_tool=False,
                reason="required trip details are still missing",
            )
        return OrchestrationDecision(
            intent=active_intent,
            should_call_recommendation_tool=True,
            reason=f"{active_intent} intent detected",
        )

    effective_item_type = _effective_recommendation_item_type(
        message=message,
        state=state,
    )
    if effective_item_type == "destination" and _has_destination_exploration_signal(
        message=message, state=state
    ):
        return OrchestrationDecision(
            intent="recommend",
            should_call_recommendation_tool=True,
            reason="destination exploration can start from partial signal",
        )

    if state.status in {"refine", "itinerary", "booking"} and not missing_slots:
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


def missing_core_constraint_slots(
    state: SessionState,
    *,
    item_type_override: str | None = None,
) -> list[str]:
    """Return missing required slots for the current recommendation mode."""

    item_type = item_type_override or state.conversation.last_recommendation_item_type
    if item_type in _ITEM_TYPE_REQUIRED_SLOT_ORDER:
        required_slots = _ITEM_TYPE_REQUIRED_SLOT_ORDER[item_type]
    else:
        required_slots = _CORE_SLOT_ORDER
    missing: list[str] = []
    for slot in required_slots:
        value = getattr(state.constraints, slot, None)
        if value is None:
            missing.append(slot)
    return missing


def missing_core_constraints(state: SessionState) -> list[str]:
    """Return human-readable missing constraints for guidance prompts."""

    return [_CORE_SLOT_LABELS[slot] for slot in missing_core_constraint_slots(state)]


def next_missing_core_constraint_slot(session_state: SessionState) -> str | None:
    """Return the next most useful missing slot for clarification."""

    missing_slots = requested_slots_for_clarification(session_state)
    if not missing_slots:
        return None

    previously_requested = [
        slot
        for slot in session_state.conversation.last_requested_slots
        if slot in missing_slots
    ]
    if previously_requested:
        return previously_requested[0]
    return missing_slots[0]


def build_clarification_message(
    session_state: SessionState,
    *,
    acknowledged_slots: list[str] | None = None,
    message: str | None = None,
) -> str:
    """Build progressive clarification copy from the current session state."""

    clarification_kind = clarification_kind_for_state(session_state)
    if clarification_kind == "search_type":
        prefix = _build_acknowledgement_prefix(acknowledged_slots or [])
        if not prefix:
            return build_search_type_question(session_state)
        if session_state.constraints.destination:
            return prefix + _SEARCH_TYPE_FOLLOW_UP_QUESTION_WITH_DESTINATION
        return prefix + _SEARCH_TYPE_FOLLOW_UP_QUESTION

    if clarification_kind == "refine_preference":
        if (
            message is not None
            and is_vague_acceptance_reply(message)
            and session_state.conversation.last_search_outcome
            in {
                "empty_results",
                "no_new_results",
            }
        ):
            return build_no_preference_after_empty_results_message(session_state)
        return (
            "I can help narrow this down. Tell me what you want to optimize for, "
            "like lower cost, fewer layovers, or a different vibe."
        )

    prefix = _build_acknowledgement_prefix(acknowledged_slots or [])
    return prefix + _build_contextual_slot_question(
        session_state,
        requested_slots_for_clarification(session_state),
    )


def build_empty_message(session_state: SessionState) -> str:
    """Build deterministic copy for an empty user message."""

    del session_state
    return (
        "I can help plan this trip. Share where you want to go, when you want to "
        "travel, and your budget, and I will take it from there."
    )


def build_invalid_request_message(session_state: SessionState) -> str:
    """Build deterministic copy for requests that fail query validation."""

    if needs_search_type_clarification(session_state):
        return build_search_type_question(session_state)

    next_slot = next_missing_core_constraint_slot(session_state)
    if next_slot is None:
        return (
            "I still need one more concrete travel detail before I can run a safe "
            "search. Try sharing destination, dates, or budget in one message."
        )
    return (
        "I am not ready to run the search yet. Share your "
        f"{_CORE_SLOT_LABELS[next_slot]} and I will turn that into recommendations."
    )


def build_empty_results_message(session_state: SessionState) -> str:
    """Build deterministic copy for empty recommendation results."""

    next_slot = next_missing_core_constraint_slot(session_state)
    if next_slot is not None:
        return (
            "I did not find grounded matches with those constraints yet. "
            + _CORE_SLOT_QUESTIONS[next_slot]
        )

    destination = session_state.constraints.destination
    destination_clause = f" for {destination}" if destination else ""

    return (
        "I did not find grounded matches with those constraints"
        + destination_clause
        + ". Try adjusting your budget, changing the travel dates, or switching the location."
    )


def build_no_new_results_message(session_state: SessionState) -> str:
    """Build deterministic copy when a follow-up search yields only duplicates."""

    next_slot = next_missing_core_constraint_slot(session_state)
    if next_slot is None:
        return (
            "I do not have new grounded options to show yet from that same search. "
            "Tell me what to change, like budget, vibe, neighborhood, or activity."
        )
    return (
        "I do not have new grounded options to show yet from that same search. "
        + _CORE_SLOT_QUESTIONS[next_slot]
    )


def build_tool_timeout_message() -> str:
    """Build deterministic copy for recommendation timeouts."""

    return (
        "I could not finish the search in time. Please try again in a moment and "
        "I will pick up from the same trip details."
    )


def build_invalid_tool_payload_message() -> str:
    """Build deterministic copy for invalid recommendation payloads."""

    return (
        "I received an invalid recommendation payload, so I stopped rather than "
        "guess. Please retry and I will fetch the results again."
    )


def build_tool_failure_message() -> str:
    """Build deterministic copy for unexpected recommendation failures."""

    return (
        "I hit a temporary search issue. Please retry in a moment and I will "
        "continue from the same plan."
    )


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
        if is_greeting(message):
            clarification_message = build_greeting_message()
        elif is_meta_question(message):
            clarification_message = build_meta_turn_message(
                session_state=session_state,
                message=message,
            )
        elif is_repair_turn(message):
            clarification_message = build_repair_turn_message(
                session_state=session_state,
                message=message,
            )
        else:
            clarification_state = _state_with_resolved_search_type(
                session_state=session_state,
                message=message,
            )
            clarification_message = build_clarification_message(
                clarification_state,
                message=message,
            )
    return LLMOrchestrationPlan(
        intent=decision.intent,
        should_call_recommendation_tool=decision.should_call_recommendation_tool,
        clarification_message=clarification_message,
        query_controls=RecommendationQueryControls(max_results=max_results),
    )


def build_planning_prompt_context(
    *,
    session_state: SessionState,
    deterministic_hint_state: SessionState,
    recent_messages: list[TranscriptMessage],
    user_message: str,
    max_results: int,
) -> str:
    """Build prompt context for LLM planning."""

    state_payload = json.dumps(
        session_state.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    deterministic_hint_payload = json.dumps(
        {
            "hint_state": deterministic_hint_state.model_dump(mode="json"),
            "effective_query": build_effective_recommendation_query_text(
                message=user_message,
                session_state=deterministic_hint_state,
            ),
            "effective_item_type": resolve_effective_item_type(
                message=user_message,
                session_state=deterministic_hint_state,
            ),
            "follow_up_refinement": is_follow_up_refinement(user_message),
            "query_filters": extract_query_filters(user_message),
            "missing_core_constraints_after_hints": missing_core_constraint_slots(
                deterministic_hint_state
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    recent_transcript = _format_recent_transcript(recent_messages)
    return (
        "You are the TravelTom orchestration planner.\n"
        "Return JSON only.\n"
        "Use a single-line compact JSON object and omit optional keys you are "
        "not setting.\n"
        "Primary duties: interpret intent, extract grounded trip details from the "
        "latest user turn, choose whether to call recommendation tool, and propose "
        "structured state updates.\n"
        "Use the recent transcript to avoid re-asking for details already captured.\n"
        "For normal chat turns, you are the primary extractor. Use state_patch to "
        "capture destination, dates, budget, and preferences from natural language.\n"
        "Treat deterministic extraction hints as advisory only. If they conflict "
        "with the raw user message or transcript, prefer the conversational meaning "
        "from the user and transcript.\n"
        "Do not let greetings, meta questions, or repair turns mutate trip "
        "constraints without strong conversational support.\n"
        "If clarification is needed, ask for one next-most-useful missing detail.\n"
        "Strict validity rule: do not include conversation, shortlist, itinerary, "
        "last_message_at, last_recommendation_version, or any key not shown in the "
        "valid shape. Any extra key makes the response invalid.\n"
        "Natural examples you should handle with state_patch:\n"
        '- "I want to go to Santa Barbara" -> constraints.destination="Santa Barbara"\n'
        '- "Hotels in Santa Barbara May 10th to May 20th under 2000 euros" -> '
        "constraints.destination, constraints.dates, constraints.budget, "
        'query_controls.filters.item_type="hotel"\n'
        '- "I want hotels to be honest" after destination, dates, and budget are '
        'known -> query_controls.filters.item_type="hotel" and '
        "should_call_recommendation_tool=true\n"
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
        "Deterministic extraction and carry-forward hints JSON: "
        f"{deterministic_hint_payload}\n"
        f"Recent transcript:\n{recent_transcript}\n"
        f"Latest user message: {user_message}"
    )


def _build_acknowledgement_prefix(acknowledged_slots: list[str]) -> str:
    if {"origin", "destination"}.issubset(set(acknowledged_slots)):
        return "Got it, I have your route. "

    acknowledgements = [
        _CORE_SLOT_LABELS[slot]
        for slot in acknowledged_slots
        if slot in _CORE_SLOT_LABELS
    ]
    if not acknowledgements:
        return ""
    if len(acknowledgements) == 1:
        return f"Got it, I have your {acknowledgements[0]}. "
    return (
        "Got it, I have your "
        + ", ".join(acknowledgements[:-1])
        + f", and {acknowledgements[-1]}. "
    )


def _build_contextual_slot_question(
    session_state: SessionState,
    requested_slots: list[str],
) -> str:
    if not requested_slots:
        return ""

    if requested_slots == ["origin", "destination"]:
        return "Where are you flying from and where do you want to go?"

    next_slot = requested_slots[0]
    question = _CORE_SLOT_QUESTIONS[next_slot]
    item_type = session_state.conversation.last_recommendation_item_type
    if (
        session_state.conversation.last_user_intent not in {"recommend", "refine"}
        or item_type not in _ITEM_TYPE_LABELS
        or item_type == "destination"
    ):
        return question

    item_label = _ITEM_TYPE_LABELS[item_type]
    if item_type == "flight" and next_slot == "origin":
        return "Where are you flying from for these flight recommendations?"
    if item_type == "flight" and next_slot == "destination":
        return "Where do you want to fly to?"
    if next_slot == "destination":
        return f"Which destination should I use for these {item_label}?"
    if next_slot == "dates":
        return f"What travel dates should I use for these {item_label}?"
    if next_slot == "budget":
        return f"What budget range should I use for these {item_label}?"
    return question


def build_response_prompt_context(
    *,
    session_state: SessionState,
    recent_messages: list[TranscriptMessage],
    user_message: str,
    recommendations: list[RecommendationResult],
    fallback_message: str,
    outcome: Literal["clarification", "results", "empty_results", "invalid_request"],
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

    outcome_instructions = {
        "clarification": (
            "Ask for one next-most-useful missing travel detail in a warm, direct "
            "way. Acknowledge newly captured details when helpful. Do not claim that "
            "any recommendation search has been run."
        ),
        "results": (
            "Summarize the strongest matches naturally and mention only items from "
            "the recommendation records."
        ),
        "empty_results": (
            "Explain that there are no strong matches yet and guide the user toward "
            "tightening or adjusting constraints."
        ),
        "invalid_request": (
            "Explain that you need more concrete trip details before running a safe "
            "search, and ask for those details plainly."
        ),
    }

    return (
        "You are the TravelTom response composer.\n"
        f"{_TRAVELTOM_PERSONA}\n"
        'Return JSON only in the form {"assistant_message": "..."}.\n'
        "Grounding rules:\n"
        "- Use only the recommendation list provided below.\n"
        "- Prefer recommendation names in user-facing text.\n"
        "- Do not invent item ids, prices, or availability.\n"
        "- If no recommendations exist, ask for tighter constraints.\n"
        "- Use the recent transcript to avoid repeating the same clarification.\n"
        f"- If you are uncertain, use this exact fallback message: {fallback_message}\n"
        f"Outcome: {outcome}\n"
        f"Outcome guidance: {outcome_instructions[outcome]}\n"
        f"Current session state JSON: {state_payload}\n"
        f"Recent transcript:\n{_format_recent_transcript(recent_messages)}\n"
        f"Latest user message: {user_message}\n"
        f"Recommendation records:\n{recommendation_block}"
    )


def _format_recent_transcript(messages: list[TranscriptMessage]) -> str:
    if not messages:
        return "NO_RECENT_TRANSCRIPT"
    formatted_messages: list[str] = []
    for message in messages:
        normalized_content = " ".join(message.content.split())
        if len(normalized_content) > _TRANSCRIPT_MESSAGE_MAX_CHARS:
            normalized_content = (
                normalized_content[: _TRANSCRIPT_MESSAGE_MAX_CHARS - 3] + "..."
            )
        formatted_messages.append(f"{message.role}: {normalized_content}")
    return "\n".join(formatted_messages)


def _active_recommendation_intent(
    *,
    message: str,
    state: SessionState,
) -> Intent | None:
    if is_meta_question(message) or is_repair_turn(message):
        return None
    intent = classify_intent(message)
    if intent in {"recommend", "refine"}:
        return intent
    if is_follow_up_refinement(message):
        return "refine"

    remembered_intent = state.conversation.last_user_intent
    if remembered_intent in {"recommend", "refine"}:
        if state.conversation.last_clarification_kind == "search_type":
            return remembered_intent
        if state.conversation.last_requested_slots:
            return remembered_intent
        if not missing_core_constraint_slots(state):
            return remembered_intent
    return None


def _effective_recommendation_item_type(
    *,
    message: str,
    state: SessionState,
) -> str:
    explicit_item_type = extract_query_filters(message).get("item_type")
    if explicit_item_type is not None:
        return explicit_item_type

    remembered_item_type = resolve_effective_item_type(
        message=message,
        session_state=state,
    )
    if remembered_item_type is not None:
        return remembered_item_type
    return "destination"


def _has_destination_exploration_signal(
    *,
    message: str,
    state: SessionState,
) -> bool:
    if is_meta_question(message) or is_repair_turn(message):
        return False
    lowered = message.casefold()
    if any(keyword in lowered for keyword in _DESTINATION_EXPLORATION_KEYWORDS):
        return True
    if state.conversation.last_user_intent in {"recommend", "refine"}:
        return True
    return classify_intent(message) in {"recommend", "refine"}


def needs_search_type_clarification(state: SessionState) -> bool:
    """Return whether the conversation is waiting for a recommendation type."""

    if state.conversation.last_recommendation_item_type is not None:
        return False
    if state.conversation.last_user_intent not in {"recommend", "refine"}:
        return False
    if state.conversation.last_clarification_kind == "search_type":
        return True
    return not missing_core_constraint_slots(
        state.model_copy(
            update={
                "conversation": state.conversation.model_copy(
                    update={"last_recommendation_item_type": None}
                )
            }
        )
    )


def requested_slots_for_clarification(session_state: SessionState) -> list[str]:
    """Return the slot or slot group the assistant should ask for next."""

    if needs_search_type_clarification(session_state):
        return []

    missing_slots = missing_core_constraint_slots(session_state)
    if not missing_slots:
        return []

    item_type = session_state.conversation.last_recommendation_item_type
    if item_type == "flight":
        if "origin" in missing_slots and "destination" in missing_slots:
            return ["origin", "destination"]
    previously_requested = [
        slot
        for slot in session_state.conversation.last_requested_slots
        if slot in missing_slots
    ]
    if previously_requested:
        return previously_requested
    return [missing_slots[0]]


def clarification_kind_for_state(
    session_state: SessionState,
) -> Literal["core_slot", "search_type", "refine_preference"]:
    """Return the active clarification branch for the current state."""

    if needs_search_type_clarification(session_state):
        return "search_type"
    if requested_slots_for_clarification(session_state):
        return "core_slot"
    return "refine_preference"


def build_search_type_question(session_state: SessionState) -> str:
    """Build clarification copy asking what kind of recommendation to run."""

    if session_state.constraints.destination:
        return _SEARCH_TYPE_QUESTION_WITH_DESTINATION
    return _SEARCH_TYPE_QUESTION


def build_no_preference_after_empty_results_message(session_state: SessionState) -> str:
    """Build deterministic copy when the user has no further refinement preference."""

    item_type = session_state.conversation.last_recommendation_item_type
    if item_type == "flight":
        return (
            "I still do not have grounded flight matches with the current route, "
            "dates, and budget. Try widening the budget, changing the dates, or "
            "adjusting the route."
        )
    if item_type == "hotel":
        destination = session_state.constraints.destination or "that destination"
        return (
            "I still do not have grounded hotel matches for "
            f"{destination} with the current dates and budget. Try widening the "
            "budget, changing the dates, or switching to flights instead."
        )
    return (
        "I still do not have strong grounded matches with the current trip details. "
        "Try changing the destination, dates, budget, or whether you want hotels "
        "or flights."
    )


def _state_with_resolved_search_type(
    *,
    session_state: SessionState,
    message: str,
) -> SessionState:
    resolved_item_type = resolve_effective_item_type(
        message=message,
        session_state=session_state,
    )
    if resolved_item_type is None:
        return session_state
    return session_state.model_copy(
        update={
            "conversation": session_state.conversation.model_copy(
                update={"last_recommendation_item_type": resolved_item_type}
            )
        }
    )


def is_meta_question(message: str) -> bool:
    """Return whether the turn is asking about the chatbot's wording or process."""

    lowered = message.casefold()
    return any(re.search(pattern, lowered) for pattern in _META_PATTERNS)


def is_repair_turn(message: str) -> bool:
    """Return whether the user appears to be correcting the current interpretation."""

    lowered = message.casefold()
    if is_meta_question(message):
        return False
    if extract_query_filters(message):
        return False
    return any(re.search(pattern, lowered) for pattern in _REPAIR_PATTERNS)


def build_meta_turn_message(
    *,
    session_state: SessionState,
    message: str,
) -> str:
    """Build deterministic copy for meta clarification turns."""

    lowered = message.casefold()
    if "destination" in lowered:
        destination = session_state.constraints.destination
        if destination:
            return (
                "By destination, I mean the place you want me to focus on. "
                f"Right now I have {destination}. Tell me what kind of places or "
                "activities you want there."
            )
        return (
            "By destination, I mean the place you want me to focus on, like "
            "Santa Barbara. Tell me the place you want and I will narrow it down."
        )
    if "date" in lowered or "when" in lowered:
        return (
            "I mean the travel dates you want me to plan around. Share a weekend, "
            "month, or exact dates and I can use that."
        )
    if "budget" in lowered or "price" in lowered:
        return (
            "I mean the budget range you want me to use for the search. Share an "
            "amount or a max budget and I will use that."
        )
    return (
        "I am trying to understand the trip details you want me to use. Tell me "
        "what to change or what you want me to focus on next."
    )


def build_repair_turn_message(
    *,
    session_state: SessionState,
    message: str,
) -> str:
    """Build deterministic copy for correction and repair turns."""

    lowered = message.casefold()
    if "restaurant" in lowered and "sightseeing" in lowered:
        return (
            "Understood. I will not assume restaurants. Tell me what kind of "
            "sightseeing you want in "
            f"{session_state.constraints.destination or 'that destination'}, "
            "like scenic views, beaches, or walkable areas."
        )
    return (
        "Understood. Tell me what to change and I will refine the search without "
        "assuming the same options again."
    )
