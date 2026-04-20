"""Deterministic orchestration guardrails and prompt-context builders."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from typing import Any, Literal

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
    has_conversational_recommendation_signal,
    is_follow_up_refinement,
    is_unsupported_flight_request,
    is_unsupported_flight_route_reply,
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
    "destination": "destination",
    "dates": "travel dates",
    "budget": "budget range",
}
_CORE_SLOT_QUESTION_VARIANTS = {
    "destination": (
        "Which destination should I focus on?",
        "What destination should I focus on?",
    ),
    "dates": (
        "What travel dates should I plan around?",
        "Which travel dates should I plan around?",
    ),
    "budget": (
        "What budget range should I use?",
        "Which budget range should I use?",
    ),
}
_ITEM_TYPE_REQUIRED_SLOT_ORDER = {
    "hotel": ("destination", "dates"),
    "restaurant": ("destination",),
    "activity": ("destination",),
}
_ITEM_TYPE_LABELS = {
    "hotel": "hotel recommendations",
    "restaurant": "restaurant recommendations",
    "activity": "activity recommendations",
}
_SEARCH_TYPE_QUESTION_VARIANTS = (
    "Sure - do you mean a hotel, a restaurant, or an activity?",
    "Got it - are you looking for a hotel, a restaurant, or an activity?",
)
_SEARCH_TYPE_QUESTION_WITH_DESTINATION_VARIANTS = (
    "Sure - for that destination, do you want a hotel, a restaurant, or an activity?",
    "Got it - for that destination, are you looking for a hotel, a restaurant, or an activity?",
)
_TRANSCRIPT_MESSAGE_MAX_CHARS = 240
_UNSUPPORTED_FLIGHT_MESSAGE = (
    "Flights are not supported. I can help with hotels, restaurants, or activities."
)
_GREETING_MESSAGE_VARIANTS = (
    "Hi, I'm Tom. Tell me where you want to go, or share destination, dates, and budget and I'll turn that into grounded recommendations.",
    "Hi, I'm Tom. Share where you want to go, or send destination, dates, and budget and I'll turn that into grounded recommendations.",
)
_REFINE_PREFERENCE_MESSAGE_VARIANTS = (
    "I can help narrow this down. Tell me what you want to optimize for, like lower cost, a different neighborhood, cuisine, or vibe.",
    "I can narrow this down with one more preference, like lower cost, a different neighborhood, cuisine, or vibe.",
)
_EMPTY_MESSAGE_VARIANTS = (
    "I can help plan this trip. Share where you want to go, when you want to travel, and your budget, and I will take it from there.",
    "I can help plan this trip. Share your destination, travel timing, and budget, and I'll take it from there.",
)
_EMPTY_RESULTS_WITH_SLOT_VARIANTS = (
    "I did not find grounded matches with those constraints yet. {question}",
    "I do not have grounded matches with those constraints yet. {question}",
)
_EMPTY_RESULTS_VARIANTS = (
    "I did not find grounded matches with those constraints{destination_clause}. Try adjusting your budget, changing the travel dates, or switching the location.",
    "I do not have grounded matches with those constraints{destination_clause}. Try adjusting your budget, changing the travel dates, or trying a different location.",
)
_NO_NEW_RESULTS_WITH_SLOT_VARIANTS = (
    "I do not have new grounded options to show yet from that same search. {question}",
    "I still do not have new grounded options to show from that same search. {question}",
)
_NO_NEW_RESULTS_VARIANTS = (
    "I do not have new grounded options to show yet from that same search. Tell me what to change, like budget, vibe, neighborhood, or activity.",
    "I still do not have new grounded options from that same search. Tell me what to change, like budget, vibe, neighborhood, or activity.",
)
_TOOL_TIMEOUT_MESSAGE_VARIANTS = (
    "I could not finish the search in time. Please try again in a moment and I will pick up from the same trip details.",
    "I ran out of time while finishing that search. Please try again in a moment and I will continue from the same trip details.",
)
_INVALID_TOOL_PAYLOAD_MESSAGE_VARIANTS = (
    "I received an invalid recommendation payload, so I stopped rather than guess. Please retry and I will fetch the results again.",
    "I received an invalid recommendation payload, so I stopped instead of guessing. Please retry and I will fetch the results again.",
)
_TOOL_FAILURE_MESSAGE_VARIANTS = (
    "I hit a temporary search issue. Please retry in a moment and I will continue from the same plan.",
    "I ran into a temporary search issue. Please retry in a moment and I will continue from the same plan.",
)


def select_copy_variant(
    variants: Sequence[str],
    *,
    category: str,
    session_state: SessionState | None = None,
    message: str | None = None,
    extra_seed: str | None = None,
) -> str:
    """Pick a stable copy variant without introducing runtime randomness."""

    if not variants:
        raise ValueError("variants must not be empty")
    if len(variants) == 1:
        return variants[0]

    seed_parts = [category]
    if session_state is not None:
        seed_parts.append(session_state.session_id)
    if message:
        seed_parts.append(message.strip().casefold())
    if extra_seed:
        seed_parts.append(extra_seed)

    seed = "|".join(seed_parts)
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return variants[int.from_bytes(digest[:4], byteorder="big") % len(variants)]


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


# Lightweight social turns that should not enter slot-filling or tool flows.
_THANKS_PATTERNS = (
    r"^\s*(thanks|thank\s+you|thx|ty)\b",
    r"\bappreciate\s+it\b",
)
_GOODBYE_PATTERNS = (
    r"^\s*(bye|goodbye|see\s+you|see\s+ya|cya|take\s+care)\b",
    r"^\s*(talk\s+to\s+you\s+later|ttyl)\b",
)
_SMALLTALK_PATTERNS = (
    r"^\s*(how\s+are\s+you|how\s+are\s+you\s+doing|how's\s+it\s+going)\b",
    r"^\s*(what's\s+up|whats\s+up)\b",
)


def is_social_turn(message: str) -> bool:
    """Return whether the message is a pure social turn (no trip planning)."""

    stripped_message = message.strip()
    if not stripped_message:
        return False

    lowered = stripped_message.casefold()
    if any(keyword in lowered for keyword in _RECOMMEND_KEYWORDS + _REFINE_KEYWORDS):
        return False
    if extract_query_filters(stripped_message):
        return False

    return any(
        re.search(pattern, stripped_message, flags=re.IGNORECASE)
        for pattern in _THANKS_PATTERNS + _GOODBYE_PATTERNS + _SMALLTALK_PATTERNS
    )


def build_social_turn_message(message: str) -> str:
    """Build deterministic copy for social turns before orchestration."""

    stripped = message.strip()

    if any(
        re.search(pattern, stripped, flags=re.IGNORECASE)
        for pattern in _THANKS_PATTERNS
    ):
        return (
            "You're welcome. If you'd like, tell me destination, dates, "
            "and budget and I'll help plan it."
        )

    if any(
        re.search(pattern, stripped, flags=re.IGNORECASE)
        for pattern in _GOODBYE_PATTERNS
    ):
        return (
            "Bye for now. If you come back with destination, dates, and "
            "budget, I'll pick up right where we left off."
        )

    if any(
        re.search(pattern, stripped, flags=re.IGNORECASE)
        for pattern in _SMALLTALK_PATTERNS
    ):
        return (
            "Doing well—happy to help. What trip are you planning "
            "(destination, dates, and budget)?"
        )

    return "Got it. Tell me what trip you're planning and I'll help."


def build_greeting_message() -> str:
    """Build deterministic copy for greeting/opening turns."""

    return select_copy_variant(
        _GREETING_MESSAGE_VARIANTS,
        category="greeting",
    )


def decide_next_action(message: str, state: SessionState) -> OrchestrationDecision:
    """Deterministic guardrail for routing when LLM planning is unavailable."""

    if is_social_turn(message):
        return OrchestrationDecision(
            intent="clarify",
            should_call_recommendation_tool=False,
            reason="social turn should stay conversational",
        )

    if is_unsupported_flight_request(message):
        return OrchestrationDecision(
            intent="clarify",
            should_call_recommendation_tool=False,
            reason="flight requests are unsupported",
        )
    if is_unsupported_flight_route_reply(message=message, session_state=state):
        return OrchestrationDecision(
            intent="clarify",
            should_call_recommendation_tool=False,
            reason="flight route replies are unsupported",
        )

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
        prefix = ""
        if not (message and has_conversational_recommendation_signal(message)):
            prefix = _build_acknowledgement_prefix(acknowledged_slots or [])
        if not prefix:
            return build_search_type_question(session_state)
        return prefix + build_search_type_question(session_state)

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
        return select_copy_variant(
            _REFINE_PREFERENCE_MESSAGE_VARIANTS,
            category="clarification:refine_preference",
            session_state=session_state,
            message=message,
        )

    prefix = _build_acknowledgement_prefix(acknowledged_slots or [])
    if (
        message is not None
        and has_conversational_recommendation_signal(message)
        and session_state.constraints.destination is None
        and requested_slots_for_clarification(session_state) == ["destination"]
    ):
        prefix = ""
    return prefix + _build_contextual_slot_question(
        session_state,
        requested_slots_for_clarification(session_state),
        message=message,
    )


def build_empty_message(session_state: SessionState) -> str:
    """Build deterministic copy for an empty user message."""

    return select_copy_variant(
        _EMPTY_MESSAGE_VARIANTS,
        category="empty_message",
        session_state=session_state,
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
        return select_copy_variant(
            _EMPTY_RESULTS_WITH_SLOT_VARIANTS,
            category=f"empty_results:{next_slot}",
            session_state=session_state,
        ).format(question=build_core_slot_question(session_state, next_slot))

    destination = session_state.constraints.destination
    destination_clause = f" for {destination}" if destination else ""

    return select_copy_variant(
        _EMPTY_RESULTS_VARIANTS,
        category="empty_results:generic",
        session_state=session_state,
        extra_seed=destination_clause,
    ).format(destination_clause=destination_clause)


def build_no_new_results_message(session_state: SessionState) -> str:
    """Build deterministic copy when a follow-up search yields only duplicates."""

    next_slot = next_missing_core_constraint_slot(session_state)
    if next_slot is None:
        return select_copy_variant(
            _NO_NEW_RESULTS_VARIANTS,
            category="no_new_results:generic",
            session_state=session_state,
        )
    return select_copy_variant(
        _NO_NEW_RESULTS_WITH_SLOT_VARIANTS,
        category=f"no_new_results:{next_slot}",
        session_state=session_state,
    ).format(question=build_core_slot_question(session_state, next_slot))


def build_tool_timeout_message(session_state: SessionState | None = None) -> str:
    """Build deterministic copy for recommendation timeouts."""

    return select_copy_variant(
        _TOOL_TIMEOUT_MESSAGE_VARIANTS,
        category="tool_timeout",
        session_state=session_state,
    )


def build_invalid_tool_payload_message(
    session_state: SessionState | None = None,
) -> str:
    """Build deterministic copy for invalid recommendation payloads."""

    return select_copy_variant(
        _INVALID_TOOL_PAYLOAD_MESSAGE_VARIANTS,
        category="invalid_tool_payload",
        session_state=session_state,
    )


def build_tool_failure_message(session_state: SessionState | None = None) -> str:
    """Build deterministic copy for unexpected recommendation failures."""

    return select_copy_variant(
        _TOOL_FAILURE_MESSAGE_VARIANTS,
        category="tool_failure",
        session_state=session_state,
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
        if is_social_turn(message):
            clarification_message = build_social_turn_message(message)
        elif is_greeting(message):
            clarification_message = build_greeting_message()
        elif is_unsupported_flight_request(
            message
        ) or is_unsupported_flight_route_reply(
            message=message,
            session_state=session_state,
        ):
            clarification_message = _UNSUPPORTED_FLIGHT_MESSAGE
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
        _prompt_state_snapshot(session_state),
        sort_keys=True,
        separators=(",", ":"),
    )
    deterministic_hint_payload = json.dumps(
        {
            "hint_constraints": deterministic_hint_state.constraints.model_dump(
                mode="json",
                exclude_none=True,
            ),
            "hint_interests": _top_weighted_interests(deterministic_hint_state),
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
        "Return a single compact JSON object only.\n"
        "Use state_patch for grounded state updates from the latest user turn.\n"
        "Use query_controls only for safe backend hints like item_type or a "
        "normalized query.\n"
        "Backend owns recommendation execution and validation.\n"
        "Rules:\n"
        "- Never invent recommendations, prices, or availability.\n"
        "- Supported item types are hotel, restaurant, and activity.\n"
        "- Flights are unsupported.\n"
        "- Greetings, meta questions, and repair turns should usually stay "
        "clarification-only and must not fill trip constraints "
        "without strong support.\n"
        "- If tool call is false, provide one short next-best clarification message.\n"
        "- Avoid unsupported keys; invalid JSON will be discarded.\n"
        f"Recommendation max_results hard limit: {max_results}.\n"
        f"Current session state JSON: {state_payload}\n"
        "Deterministic extraction and carry-forward hints JSON: "
        f"{deterministic_hint_payload}\n"
        f"Recent transcript:\n{recent_transcript}\n"
        f"Latest user message: {user_message}"
    )


def _build_acknowledgement_prefix(acknowledged_slots: list[str]) -> str:
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
    *,
    message: str | None = None,
) -> str:
    if not requested_slots:
        return ""

    next_slot = requested_slots[0]
    lowered = message.casefold() if message is not None else ""
    resolved_item_type = (
        resolve_effective_item_type(
            message=message,
            session_state=session_state,
        )
        if message is not None
        else session_state.conversation.last_recommendation_item_type
    )
    if (
        next_slot == "destination"
        and session_state.constraints.destination is None
        and resolved_item_type == "restaurant"
    ):
        return "Sure - that sounds like food. What city should I look in?"
    if (
        next_slot == "destination"
        and session_state.constraints.destination is None
        and resolved_item_type == "activity"
    ):
        if "tonight" in lowered or "this evening" in lowered:
            return "Sounds fun - what city should I look in tonight?"
        return "Sounds fun - what city should I look in?"
    if (
        next_slot == "destination"
        and session_state.constraints.destination is None
        and resolved_item_type == "hotel"
    ):
        return "Sure - what city do you need a place to stay in?"
    if (
        next_slot == "destination"
        and session_state.constraints.destination is None
        and message is not None
        and resolved_item_type is None
        and has_conversational_recommendation_signal(message)
    ):
        return build_search_type_question(session_state)

    question = build_core_slot_question(session_state, next_slot)
    item_type = session_state.conversation.last_recommendation_item_type
    if (
        session_state.conversation.last_user_intent not in {"recommend", "refine"}
        or item_type not in _ITEM_TYPE_LABELS
    ):
        return question

    item_label = _ITEM_TYPE_LABELS[item_type]
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

    state_payload = json.dumps(
        _prompt_state_snapshot(session_state),
        sort_keys=True,
    )

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
        "- If you mention recommendation names, keep them in the same surfaced order and do not skip within the named subset.\n"
        "- Do not invent item ids, prices, or availability.\n"
        "- Do not mention scores, rankings, or matching rationale unless it is directly stated in the recommendation explanation.\n"
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


def _prompt_state_snapshot(session_state: SessionState) -> dict[str, Any]:
    return {
        "constraints": session_state.constraints.model_dump(
            mode="json",
            exclude_none=True,
        ),
        "preferences": {
            "weighted_interests": _top_weighted_interests(session_state),
            "dislikes": list(session_state.preferences.dislikes),
        },
        "conversation": {
            "last_requested_slots": list(
                session_state.conversation.last_requested_slots
            ),
            "last_user_intent": session_state.conversation.last_user_intent,
            "last_clarification_kind": (
                session_state.conversation.last_clarification_kind
            ),
            "last_search_outcome": session_state.conversation.last_search_outcome,
            "last_recommendation_item_type": (
                session_state.conversation.last_recommendation_item_type
            ),
            "last_recommendation_query": (
                session_state.conversation.last_recommendation_query
            ),
        },
        "status": session_state.status,
    }


def _top_weighted_interests(session_state: SessionState) -> dict[str, float]:
    weighted_interests = sorted(
        session_state.preferences.weighted_interests.items(),
        key=lambda item: (-item[1], item[0]),
    )
    return {interest: weight for interest, weight in weighted_interests[:3]}


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
    if has_conversational_recommendation_signal(message):
        return "recommend"

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
) -> str | None:
    explicit_item_type = extract_query_filters(message).get("item_type")
    if explicit_item_type is not None:
        return explicit_item_type

    remembered_item_type = resolve_effective_item_type(
        message=message,
        session_state=state,
    )
    if remembered_item_type is not None:
        return remembered_item_type
    return None


def needs_search_type_clarification(state: SessionState) -> bool:
    """Return whether the conversation is waiting for a recommendation type."""

    if state.conversation.last_recommendation_item_type is not None:
        return False
    if state.conversation.last_user_intent not in {"recommend", "refine"}:
        return False
    if state.conversation.last_clarification_kind == "search_type":
        return True
    return (
        state.constraints.destination is not None
        and state.constraints.dates is not None
    )


def requested_slots_for_clarification(session_state: SessionState) -> list[str]:
    """Return the slot or slot group the assistant should ask for next."""

    if needs_search_type_clarification(session_state):
        return []

    missing_slots = missing_core_constraint_slots(session_state)
    if not missing_slots:
        return []

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
        return select_copy_variant(
            _SEARCH_TYPE_QUESTION_WITH_DESTINATION_VARIANTS,
            category="search_type:destination",
            session_state=session_state,
        )
    return select_copy_variant(
        _SEARCH_TYPE_QUESTION_VARIANTS,
        category="search_type:generic",
        session_state=session_state,
    )


def build_core_slot_question(session_state: SessionState, slot: str) -> str:
    """Build deterministic core-slot clarification copy with controlled variety."""

    variants = _CORE_SLOT_QUESTION_VARIANTS.get(slot)
    if variants is None:
        raise ValueError(f"Unsupported core slot: {slot}")
    return select_copy_variant(
        variants,
        category=f"core_slot:{slot}",
        session_state=session_state,
    )


def build_no_preference_after_empty_results_message(session_state: SessionState) -> str:
    """Build deterministic copy when the user has no further refinement preference."""

    item_type = session_state.conversation.last_recommendation_item_type
    if item_type == "hotel":
        destination = session_state.constraints.destination or "that destination"
        date_clause = (
            " with the current dates" if session_state.constraints.dates else ""
        )
        budget_clause = (
            " and budget" if session_state.constraints.budget is not None else ""
        )
        return (
            "I still do not have grounded hotel matches for "
            f"{destination}{date_clause}{budget_clause}. Try widening the "
            "budget, changing the dates, or trying a nearby area."
        )
    if item_type == "restaurant":
        destination = session_state.constraints.destination or "that destination"
        return (
            "I still do not have grounded restaurant matches for "
            f"{destination}. Try a different neighborhood, cuisine, or budget."
        )
    if item_type == "activity":
        destination = session_state.constraints.destination or "that destination"
        return (
            "I still do not have grounded activity matches for "
            f"{destination}. Try a different vibe, neighborhood, or budget."
        )
    return (
        "I still do not have strong grounded matches with the current trip details. "
        "Try changing the destination, dates, budget, or whether you want hotels, "
        "restaurants, or activities."
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
    if is_unsupported_flight_request(message):
        return False
    if not any(re.search(pattern, lowered) for pattern in _REPAIR_PATTERNS):
        return False
    if re.search(
        (
            r"\b(?:under|below|less than|max(?:imum)?|up to|not more than|"
            r"starting from|at least|around|about|roughly|approximately)\b"
        ),
        lowered,
    ):
        return False
    if re.search(r"^\s*not\s+(?:too\s+|very\s+)?(?:expensive|pricey)\b", lowered):
        return False
    if re.search(r"\b\d[\d,]*(?:\.\d+)?k?\b", lowered) and "budget" in lowered:
        return False
    return True


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
