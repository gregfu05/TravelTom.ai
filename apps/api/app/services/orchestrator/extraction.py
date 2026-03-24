"""Deterministic extraction of session-state updates from user messages."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from app.schemas.state import BudgetRange, DateRange, PartySize, SessionState

_MONTH_NAME_TO_NUMBER = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_DESTINATION_STOPWORDS = {
    "trip",
    "travel",
    "vacation",
    "holiday",
    "week",
    "weeks",
    "weekend",
    "day",
    "days",
    "budget",
    "cheap",
    "expensive",
    "family",
    "adults",
    "adult",
    "children",
    "child",
    "kids",
    "people",
    "person",
    "tomorrow",
    "today",
    "next",
    "this",
    "summer",
    "winter",
    "spring",
    "autumn",
    "fall",
} | set(_MONTH_NAME_TO_NUMBER.keys())

_BARE_DESTINATION_DISALLOWED_TOKENS = {
    "another",
    "break",
    "cheaper",
    "cheapest",
    "explore",
    "family",
    "family-friendly",
    "find",
    "flexible",
    "friendly",
    "getaway",
    "greetings",
    "hello",
    "help",
    "hey",
    "holiday",
    "how",
    "idea",
    "ideas",
    "i",
    "i'm",
    "hi",
    "im",
    "me",
    "mean",
    "more",
    "option",
    "options",
    "plan",
    "please",
    "let's",
    "lets",
    "do",
    "something",
    "like",
    "recommend",
    "relax",
    "show",
    "suggest",
    "suggestion",
    "suggestions",
    "thank",
    "thanks",
    "tommy",
    "trip",
    "trips",
    "traveltom",
    "vacation",
    "what",
    "when",
    "where",
    "who",
    "why",
    "destination",
}
_CURRENCY_ALIASES = {
    "usd": "USD",
    "dollar": "USD",
    "dollars": "USD",
    "eur": "EUR",
    "euro": "EUR",
    "euros": "EUR",
    "gbp": "GBP",
    "pound": "GBP",
    "pounds": "GBP",
    "cad": "CAD",
    "aud": "AUD",
    "jpy": "JPY",
    "yen": "JPY",
    "inr": "INR",
    "rupee": "INR",
    "rupees": "INR",
}
_CURRENCY_WORD_GROUP = "|".join(
    re.escape(token)
    for token in sorted(_CURRENCY_ALIASES.keys(), key=len, reverse=True)
)
_LOCATION_JOINER_WORDS = {
    "and",
    "da",
    "de",
    "del",
    "do",
    "dos",
    "la",
    "las",
    "los",
    "of",
    "the",
}
_BARE_DESTINATION_WORD_PATTERN = re.compile(r"^[a-z][a-z.'-]*$", flags=re.IGNORECASE)

_TRAILING_LOCATION_WORDS = {
    "for",
    "with",
    "on",
    "between",
    "under",
    "over",
    "budget",
    "from",
    "starting",
    "start",
    "end",
    "in",
    "at",
    "by",
    "around",
    "next",
    "this",
    "weekend",
    "week",
    "month",
    "year",
    "summer",
    "winter",
    "spring",
    "autumn",
    "fall",
}

_INTEREST_KEYWORDS: dict[str, tuple[str, ...]] = {
    "food": ("food", "restaurant", "restaurants", "dining", "cafe", "cafes"),
    "nightlife": (
        "nightlife",
        "bar",
        "bars",
        "club",
        "clubs",
        "cocktail",
        "cocktails",
        "pub",
        "pubs",
    ),
    "shopping": ("shopping", "shop", "shops", "boutique", "boutiques", "mall", "fashion"),
    "beaches": ("beach", "beaches", "coast", "seaside"),
    "culture": ("museum", "museums", "art", "history", "gallery", "galleries"),
    "nature": ("nature", "hiking", "mountain", "mountains", "park", "parks", "outdoors"),
}

_ROUTE_PATTERN = re.compile(
    r"\bfrom\s+(?P<origin>[a-z][a-z .'-]{1,64}?)\s+to\s+"
    r"(?P<destination>[a-z][a-z .'-]{1,64}?)(?=(?:\s+(?:for|with|on|between|"
    r"under|over|budget|from|starting|start|end|in|at|by)\b)|[,.!?;]|$)",
    flags=re.IGNORECASE,
)
_BARE_ROUTE_PATTERN = re.compile(
    r"^\s*(?P<origin>[a-z][a-z .'-]{1,64}?)\s+to\s+"
    r"(?P<destination>[a-z][a-z .'-]{1,64}?)\s*$",
    flags=re.IGNORECASE,
)
_ORIGIN_PATTERN = re.compile(
    r"\bfrom\s+(?P<origin>[a-z][a-z .'-]{1,64}?)(?=(?:\s+(?:to|for|with|on|"
    r"between|under|over|budget|in|at|by)\b)|[,.!?;]|$)",
    flags=re.IGNORECASE,
)
_DESTINATION_PATTERNS = (
    re.compile(
        r"\bto\s+(?P<destination>[a-z][a-z .'-]{1,64}?)(?=(?:\s+(?:for|with|on|"
        r"between|under|over|budget|from|starting|start|end|in|at|by)\b)|[,.!?;]|$)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\bin\s+(?P<destination>[a-z][a-z .'-]{1,64}?)(?=(?:\s+(?:for|with|on|"
        r"between|under|over|budget|from|starting|start|end|at|by)\b)|[,.!?;]|$)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\bdestination\s+(?:is|will be|would be|should be)\s+"
        r"(?P<destination>[a-z][a-z .'-]{1,64}?)(?=(?:\s+(?:for|with|on|between|"
        r"under|over|budget|from|starting|start|end|in|at|by)\b)|[,.!?;]|$)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\bdestination\s*[:=\-]\s*"
        r"(?P<destination>[a-z][a-z .'-]{1,64}?)(?=(?:\s+(?:for|with|on|between|"
        r"under|over|budget|from|starting|start|end|in|at|by)\b)|[,.!?;]|$)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\bvisit(?:ing)?\s+(?P<destination>[a-z][a-z .'-]{1,64}?)(?=(?:\s+(?:for|"
        r"with|on|between|under|over|budget|from|starting|start|end|in|at|by)\b)"
        r"|[,.!?;]|$)",
        flags=re.IGNORECASE,
    ),
)

_NON_DESTINATION_PREFIX_PATTERN = re.compile(
    r"^(?:(?:want\s+to\s+)?go|travel(?:ing|ling)?|fly(?:ing)?|"
    r"head(?:ing)?|stay(?:ing)?)\s+to\s+",
    flags=re.IGNORECASE,
)
_NON_DESTINATION_PHRASES = {
    "be honest",
    "to be honest",
    "lower cost",
    "lower price",
    "more affordable",
    "less expensive",
}

_ISO_DATE_PATTERN = re.compile(
    r"\b(?P<year>\d{4})[-/](?P<month>\d{1,2})[-/](?P<day>\d{1,2})\b"
)
_MONTH_WORD = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|"
    r"nov(?:ember)?|dec(?:ember)?"
)
_DESTINATION_DATE_AWARE_PATTERNS = (
    re.compile(
        rf"\bto\s+(?P<destination>[a-z][a-z .'-]{{1,64}}?)(?=(?:\s+(?:for|with|on|"
        rf"between|under|over|budget|from|starting|start|end|in|at|by|{_MONTH_WORD})\b|\s+\d)|[,.!?;]|$)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        rf"\bin\s+(?P<destination>[a-z][a-z .'-]{{1,64}}?)(?=(?:\s+(?:for|with|on|"
        rf"between|under|over|budget|from|starting|start|end|at|by|{_MONTH_WORD})\b|\s+\d)|[,.!?;]|$)",
        flags=re.IGNORECASE,
    ),
)
_DESTINATION_DATE_SUFFIX_PATTERN = re.compile(
    rf"\s+(?:(?:next|this)\s+weekend\b|{_MONTH_WORD}\b|\d)",
    flags=re.IGNORECASE,
)
_MONTH_NAME_DATE_PATTERN = re.compile(
    rf"\b(?P<month>{_MONTH_WORD})\.?\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?"
    rf"(?:(?:,\s*|\s+)(?P<year>\d{{4}})(?!\s*(?:{_CURRENCY_WORD_GROUP})\b))?\b",
    flags=re.IGNORECASE,
)
_DAY_FIRST_MONTH_NAME_DATE_PATTERN = re.compile(
    rf"\b(?P<day>\d{{1,2}})(?:st|nd|rd|th)?(?:\s+of)?\s+(?P<month>{_MONTH_WORD})\.?"
    rf"(?:(?:,\s*|\s+)(?P<year>\d{{4}})(?!\s*(?:{_CURRENCY_WORD_GROUP})\b))?\b",
    flags=re.IGNORECASE,
)

_TRIP_DAYS_PATTERN = re.compile(
    r"\b(?:for\s+)?(?P<days>\d{1,2})\s*(?:day|days)\b", flags=re.IGNORECASE
)
_TRIP_WEEKS_PATTERN = re.compile(
    r"\b(?:for\s+)?(?P<weeks>\d{1,2})\s*(?:week|weeks)\b", flags=re.IGNORECASE
)

_CURRENCY_SYMBOL_CLASS = r"$\u20ac\u00a3"

_BUDGET_RANGE_PATTERN = re.compile(
    rf"\b(?:budget\s*(?:between|from)|(?:between|from)\s*[{_CURRENCY_SYMBOL_CLASS}])\s*"
    r"(?P<minimum>\d[\d,]*(?:\.\d+)?k?)\s*(?:usd|eur|gbp|cad|aud|jpy|inr)?\s*"
    rf"(?:and|to|-)\s*[{_CURRENCY_SYMBOL_CLASS}]?\s*(?P<maximum>\d[\d,]*(?:\.\d+)?k?)\s*"
    r"(?P<currency>usd|eur|gbp|cad|aud|jpy|inr)?\b",
    flags=re.IGNORECASE,
)
_BUDGET_DASH_RANGE_PATTERN = re.compile(
    rf"\bbudget(?:\s+is)?\s*[{_CURRENCY_SYMBOL_CLASS}]?\s*(?P<minimum>\d[\d,]*(?:\.\d+)?k?)\s*"
    rf"-\s*[{_CURRENCY_SYMBOL_CLASS}]?\s*(?P<maximum>\d[\d,]*(?:\.\d+)?k?)\s*"
    r"(?P<currency>usd|eur|gbp|cad|aud|jpy|inr)?\b",
    flags=re.IGNORECASE,
)
_BUDGET_MAX_PATTERN = re.compile(
    rf"\b(?:under|below|less than|max(?:imum)?|up to)\s*[{_CURRENCY_SYMBOL_CLASS}]?\s*"
    r"(?P<maximum>\d[\d,]*(?:\.\d+)?k?)\s*(?P<currency>usd|eur|gbp|cad|aud|jpy|inr)?\b",
    flags=re.IGNORECASE,
)
_BUDGET_SINGLE_PATTERN = re.compile(
    rf"\bbudget(?:\s+is|\s+around|\s+about|\s+of)?\s*[{_CURRENCY_SYMBOL_CLASS}]?\s*"
    r"(?P<amount>\d[\d,]*(?:\.\d+)?k?)\s*(?P<currency>usd|eur|gbp|cad|aud|jpy|inr)?\b",
    flags=re.IGNORECASE,
)
_BARE_BUDGET_REPLY_PATTERN = re.compile(
    rf"^\s*(?:budget(?:\s+is|\s+around|\s+about|\s+of)?\s+)?"
    r"(?:(?:about|around|roughly|approximately|something like)\s+)?"
    rf"[{_CURRENCY_SYMBOL_CLASS}]?\s*(?P<amount>\d[\d,]*(?:\.\d+)?k?)"
    r"\s*(?P<currency>usd|eur|euro|euros|gbp|pound|pounds|cad|aud|jpy|yen|inr|rupee|rupees|dollar|dollars)?"
    rf"\s*[{_CURRENCY_SYMBOL_CLASS}]?\s*[.!?]?\s*$",
    flags=re.IGNORECASE,
)
_TRAILING_BUDGET_REPLY_PATTERN = re.compile(
    rf"(?:^|[\s,;:])"
    rf"[{_CURRENCY_SYMBOL_CLASS}]?\s*(?P<amount>\d[\d,]*(?:\.\d+)?k?)"
    r"\s*(?P<currency>usd|eur|euro|euros|gbp|pound|pounds|cad|aud|jpy|yen|inr|rupee|rupees|dollar|dollars)"
    rf"\s*[{_CURRENCY_SYMBOL_CLASS}]?\s*[.!?]?\s*$",
    flags=re.IGNORECASE,
)

_PARTY_ADULTS_CHILDREN_PATTERN = re.compile(
    r"\b(?P<adults>\d+)\s*adults?(?:\s*(?:and|,)\s*"
    r"(?P<children>\d+)\s*(?:children|child|kids?|kid))?\b",
    flags=re.IGNORECASE,
)
_PARTY_CHILDREN_ADULTS_PATTERN = re.compile(
    r"\b(?P<children>\d+)\s*(?:children|child|kids?|kid)\s*(?:and|with)\s*"
    r"(?P<adults>\d+)\s*adults?\b",
    flags=re.IGNORECASE,
)
_PARTY_TOTAL_PATTERN = re.compile(
    r"\b(?:for|party of|family of)\s+(?P<total>\d+)\s*"
    r"(?:people|persons|travelers|travellers|guests)?\b",
    flags=re.IGNORECASE,
)

_ITEM_TYPE_PATTERNS: dict[str, tuple[str, ...]] = {
    "hotel": (
        r"\bhotel\b",
        r"\bhotels\b",
        r"\bhostel\b",
        r"\bhostels\b",
        r"\bresort\b",
        r"\bresorts\b",
        r"\blodging\b",
        r"\baccommodation\b",
        r"\bplace to stay\b",
        r"\bstay\b",
    ),
    "flight": (
        r"\bflight\b",
        r"\bflights\b",
        r"\bairline\b",
        r"\bairlines\b",
        r"\bairport\b",
        r"\bairports\b",
    ),
    "destination": (
        r"\bdestinations\b",
        r"\bdestination\s+(?:ideas|options|recommendations?|suggestions?)\b",
        r"\bwhere should i go\b",
        r"\bplaces to visit\b",
    ),
}

_FOLLOW_UP_PATTERNS = (
    r"\banother option\b",
    r"\banother one\b",
    r"\bshow me more\b",
    r"\bmore options\b",
    r"\bmore please\b",
    r"\bwhat else\b",
    r"\bsomething else\b",
    r"\bany others\b",
    r"\bother options\b",
    r"\bmore like this\b",
    r"\bcheaper\b",
    r"\bcheapest\b",
    r"\bless expensive\b",
    r"\blower cost\b",
    r"\blower price\b",
    r"\bmore affordable\b",
    r"\bbudget option\b",
    r"\bsimilar\b",
)
_VAGUE_ACCEPTANCE_PATTERNS = (
    r"\banything works\b",
    r"\bwhatever works\b",
    r"\beither is fine\b",
    r"\bany is fine\b",
    r"\bi am flexible\b",
    r"\bi'm flexible\b",
    r"\bno preference\b",
    r"\bwhatever\b",
    r"\bany(?:thing)? is okay\b",
)


def apply_message_state_updates(
    *,
    message: str,
    session_state: SessionState,
    today: date | None = None,
) -> SessionState:
    """Apply deterministic state extraction for a single user message."""

    normalized_message = " ".join(message.strip().split())
    if not normalized_message:
        return session_state.model_copy(deep=True)

    extraction_day = today or date.today()
    next_state = session_state.model_copy(deep=True)

    destination_source: str | None = None
    origin, destination = _extract_route(
        normalized_message,
        session_state=session_state,
    )
    if destination is not None:
        destination_source = "route"
    if origin is None:
        origin = _extract_origin(normalized_message)
    if destination is None:
        destination = _extract_destination(normalized_message)
        if destination is not None:
            destination_source = "pattern"
    if destination is None:
        destination = _extract_bare_destination(normalized_message)
        if destination is not None:
            destination_source = "bare"
    if destination is None:
        destination = _extract_leading_destination_fragment(normalized_message)
        if destination is not None:
            destination_source = "leading"

    if origin is not None:
        next_state.constraints.origin = origin
    if destination is not None and _should_persist_destination_update(
        session_state=session_state,
        destination=destination,
        source=destination_source or "pattern",
    ):
        next_state.constraints.destination = destination
        if all(
            existing.casefold() != destination.casefold()
            for existing in next_state.entities.destinations
        ):
            next_state.entities.destinations.append(destination)

    parsed_dates = _extract_dates(normalized_message, today=extraction_day)
    if parsed_dates is not None:
        next_state.constraints.dates = parsed_dates
        next_state.constraints.trip_length_days = (
            parsed_dates.end - parsed_dates.start
        ).days + 1
    else:
        trip_length_days = _extract_trip_length_days(normalized_message)
        if trip_length_days is not None:
            next_state.constraints.trip_length_days = trip_length_days

    fallback_currency = (
        next_state.constraints.budget.currency
        if next_state.constraints.budget is not None
        else None
    )
    allow_bare_budget_amount = (
        "budget" in session_state.conversation.last_requested_slots
        or (
            _extract_currency(normalized_message) is not None
            and (
                destination is not None
                or parsed_dates is not None
                or (
                    session_state.constraints.destination is not None
                    and session_state.constraints.dates is not None
                )
            )
        )
    )
    parsed_budget = _extract_budget(
        normalized_message,
        fallback_currency=fallback_currency,
        allow_bare_amount=allow_bare_budget_amount,
    )
    if parsed_budget is not None:
        next_state.constraints.budget = parsed_budget

    parsed_party_size = _extract_party_size(normalized_message)
    if parsed_party_size is not None:
        next_state.constraints.party_size = parsed_party_size

    extracted_interests = _extract_weighted_interests(normalized_message)
    if extracted_interests:
        merged_interests = dict(next_state.preferences.weighted_interests)
        for key, value in extracted_interests.items():
            merged_interests[key] = max(merged_interests.get(key, 0.0), value)
        next_state.preferences.weighted_interests = merged_interests

    return next_state


def extract_query_filters(message: str) -> dict[str, str]:
    """Extract per-request recommendation filters from user text."""

    lowered = message.casefold()
    for item_type in ("hotel", "flight", "destination"):
        patterns = _ITEM_TYPE_PATTERNS[item_type]
        if any(re.search(pattern, lowered) for pattern in patterns):
            return {"item_type": item_type}
    return {}


def is_follow_up_refinement(message: str) -> bool:
    """Return whether the user message looks like an underspecified follow-up."""

    lowered = message.casefold()
    return any(re.search(pattern, lowered) for pattern in _FOLLOW_UP_PATTERNS)


def is_vague_acceptance_reply(message: str) -> bool:
    """Return whether the user is giving a non-specific acceptance reply."""

    lowered = message.casefold()
    return any(re.search(pattern, lowered) for pattern in _VAGUE_ACCEPTANCE_PATTERNS)


def resolve_search_type_reply(
    *,
    message: str,
    session_state: SessionState,
) -> str | None:
    """Resolve a reply to a pending search-type clarification."""

    explicit_item_type = extract_query_filters(message).get("item_type")
    if explicit_item_type is not None:
        return explicit_item_type

    route_origin, route_destination = _extract_route(
        message,
        session_state=session_state,
    )
    if route_origin is not None and route_destination is not None:
        return "flight"

    if _extract_origin(message) is not None:
        return "flight"

    if not is_vague_acceptance_reply(message):
        return None

    if session_state.constraints.destination:
        return "hotel"
    return "destination"


def resolve_effective_item_type(
    *,
    message: str,
    session_state: SessionState,
) -> str | None:
    """Resolve the effective recommendation item type for this turn."""

    explicit_item_type = extract_query_filters(message).get("item_type")
    if explicit_item_type is not None:
        return explicit_item_type

    if session_state.conversation.last_clarification_kind == "search_type":
        resolved_search_type = resolve_search_type_reply(
            message=message,
            session_state=session_state,
        )
        if resolved_search_type is not None:
            return resolved_search_type

    remembered_item_type = session_state.conversation.last_recommendation_item_type
    if is_follow_up_refinement(message):
        return remembered_item_type

    if (
        remembered_item_type is not None
        and session_state.conversation.last_requested_slots
        and session_state.conversation.last_user_intent in {"recommend", "refine"}
    ):
        return remembered_item_type
    return None


def build_effective_recommendation_query_text(
    *,
    message: str,
    session_state: SessionState,
) -> str:
    """Build deterministic carry-forward query text for recommendation turns."""

    normalized_message = " ".join(message.strip().split())
    if not normalized_message:
        return normalized_message

    prior_query = (session_state.conversation.last_recommendation_query or "").strip()
    explicit_item_type = extract_query_filters(normalized_message).get("item_type")

    if not is_follow_up_refinement(normalized_message):
        if (
            prior_query
            and session_state.conversation.last_clarification_kind == "search_type"
        ):
            return _merge_query_fragments(normalized_message, prior_query)
        if (
            prior_query
            and explicit_item_type is None
            and session_state.conversation.last_requested_slots
            and session_state.conversation.last_user_intent in {"recommend", "refine"}
        ):
            return _merge_query_fragments(normalized_message, prior_query)
        return normalized_message

    if prior_query:
        return _merge_query_fragments(normalized_message, prior_query)

    fragments: list[str] = [normalized_message]
    effective_item_type = resolve_effective_item_type(
        message=normalized_message,
        session_state=session_state,
    )
    if effective_item_type is not None:
        fragments.append(effective_item_type)

    if session_state.constraints.destination:
        fragments.append(session_state.constraints.destination)

    weighted_interests = sorted(
        session_state.preferences.weighted_interests.items(),
        key=lambda item: (-item[1], item[0]),
    )
    for interest, _weight in weighted_interests[:3]:
        fragments.append(interest)

    normalized_fragments = [
        fragment.strip() for fragment in fragments if fragment and fragment.strip()
    ]
    return " ".join(dict.fromkeys(normalized_fragments))


def apply_structured_state_patch(
    *,
    session_state: SessionState,
    state_patch: Mapping[str, Any] | None,
) -> SessionState:
    """Merge an LLM state patch into `SessionState` with strict validation."""

    if not state_patch:
        return session_state.model_copy(deep=True)

    base_payload = session_state.model_dump(mode="python")
    merged_payload = _deep_merge_payload(base_payload, state_patch)
    next_state = SessionState.model_validate(merged_payload)

    destination = next_state.constraints.destination
    if destination and all(
        existing.casefold() != destination.casefold()
        for existing in next_state.entities.destinations
    ):
        next_state.entities.destinations.append(destination)

    if next_state.constraints.dates is not None:
        next_state.constraints.trip_length_days = (
            next_state.constraints.dates.end - next_state.constraints.dates.start
        ).days + 1

    return next_state


def _extract_route(
    message: str,
    *,
    session_state: SessionState | None = None,
) -> tuple[str | None, str | None]:
    match = _ROUTE_PATTERN.search(message)
    if match is not None:
        origin = _normalize_location(match.group("origin"))
        destination = _normalize_destination_candidate(match.group("destination"))
        return origin, destination

    if not _should_try_bare_route(message=message, session_state=session_state):
        return None, None

    bare_match = _BARE_ROUTE_PATTERN.search(message)
    if bare_match is None:
        return None, None

    origin = _normalize_location(bare_match.group("origin"))
    destination = _normalize_destination_candidate(bare_match.group("destination"))
    if origin is None or destination is None:
        return None, None
    return origin, destination


def _extract_origin(message: str) -> str | None:
    match = _ORIGIN_PATTERN.search(message)
    if match is None:
        return None
    return _normalize_location(match.group("origin"))


def _extract_destination(message: str) -> str | None:
    for pattern in _DESTINATION_PATTERNS + _DESTINATION_DATE_AWARE_PATTERNS:
        match = pattern.search(message)
        if match is None:
            continue
        destination = _normalize_destination_candidate(match.group("destination"))
        if destination is not None:
            return destination
    return None


def _extract_bare_destination(message: str) -> str | None:
    if any(character.isdigit() for character in message):
        return None
    if re.search(r"\b(?:from|to|in|between|under|over|budget|for|with)\b", message):
        return None
    if re.search(r"[,.!?;:]", message):
        return None
    if is_follow_up_refinement(message):
        return None
    if is_vague_acceptance_reply(message):
        return None
    if extract_query_filters(message):
        return None

    destination = _normalize_destination_candidate(message)
    if destination is None:
        return None
    if not _looks_like_bare_destination(destination):
        return None
    return destination


def _extract_leading_destination_fragment(message: str) -> str | None:
    first_digit_index = next(
        (index for index, character in enumerate(message) if character.isdigit()),
        None,
    )
    if first_digit_index is None or first_digit_index <= 0:
        return None

    leading_fragment = message[:first_digit_index].strip()
    if not leading_fragment:
        return None
    if re.search(r"\b(?:from|to|in|between|under|over|budget|for|with)\b", leading_fragment):
        return None
    if is_vague_acceptance_reply(leading_fragment):
        return None
    if extract_query_filters(leading_fragment):
        return None

    destination = _normalize_destination_candidate(leading_fragment)
    if destination is None or not _looks_like_bare_destination(destination):
        return None
    return destination


def _normalize_destination_candidate(value: str) -> str | None:
    cleaned = value.strip(" ,.;:!?")
    cleaned = _NON_DESTINATION_PREFIX_PATTERN.sub("", cleaned)
    suffix_match = _DESTINATION_DATE_SUFFIX_PATTERN.search(cleaned)
    if suffix_match is not None:
        cleaned = cleaned[: suffix_match.start()]

    destination = _normalize_location(cleaned)
    if destination is None:
        return None
    if destination.casefold() in _NON_DESTINATION_PHRASES:
        return None
    return destination


def _should_persist_destination_update(
    *,
    session_state: SessionState,
    destination: str,
    source: str,
) -> bool:
    existing_destination = session_state.constraints.destination
    if existing_destination is None:
        return True
    if existing_destination.casefold() == destination.casefold():
        return True
    if source in {"route", "pattern"}:
        return True
    if "destination" in session_state.conversation.last_requested_slots:
        return True
    return False


def _normalize_location(value: str) -> str | None:
    cleaned = value.strip(" ,.;:!?")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"^(?:the)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[\"`]", "", cleaned)

    words = cleaned.split()
    while words and words[-1].casefold() in _TRAILING_LOCATION_WORDS:
        words.pop()
    if not words:
        return None

    if len(words) > 4:
        return None

    joined = " ".join(words)
    if any(character.isdigit() for character in joined):
        return None

    lower_joined = joined.casefold()
    if lower_joined in _DESTINATION_STOPWORDS:
        return None

    if re.fullmatch(r"[A-Z]{2,4}", joined):
        return joined

    formatted_words: list[str] = []
    for word in words:
        if re.fullmatch(r"[A-Z]{2,4}", word):
            formatted_words.append(word)
            continue
        formatted_words.append(word.capitalize())
    return " ".join(formatted_words)


def _extract_dates(message: str, *, today: date) -> DateRange | None:
    explicit_dates = _collect_explicit_dates(message, today=today)
    trip_length_days = _extract_trip_length_days(message)

    if len(explicit_dates) >= 2:
        start, end = explicit_dates[0], explicit_dates[1]
        return _build_date_range(start=start, end=end)

    if len(explicit_dates) == 1 and trip_length_days is not None:
        start = explicit_dates[0]
        end = start + timedelta(days=trip_length_days - 1)
        return _build_date_range(start=start, end=end)

    return _extract_relative_date_range(message, today=today)


def _collect_explicit_dates(message: str, *, today: date) -> list[date]:
    candidates: list[tuple[int, date]] = []

    for match in _ISO_DATE_PATTERN.finditer(message):
        parsed_date = _safe_date(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
        )
        if parsed_date is not None:
            candidates.append((match.start(), parsed_date))

    for pattern in (_MONTH_NAME_DATE_PATTERN, _DAY_FIRST_MONTH_NAME_DATE_PATTERN):
        for match in pattern.finditer(message):
            month_key = match.group("month").casefold().rstrip(".")
            month = _MONTH_NAME_TO_NUMBER.get(month_key)
            if month is None:
                continue

            parsed_year_text = match.group("year")
            year = int(parsed_year_text) if parsed_year_text else today.year
            parsed_date = _safe_date(year, month, int(match.group("day")))
            if parsed_date is None:
                continue

            if parsed_year_text is None and parsed_date < today:
                parsed_date = _safe_date(year + 1, month, int(match.group("day")))
                if parsed_date is None:
                    continue

            candidates.append((match.start(), parsed_date))

    candidates.sort(key=lambda item: item[0])
    unique_dates: list[date] = []
    for _, parsed_date in candidates:
        if parsed_date in unique_dates:
            continue
        unique_dates.append(parsed_date)
    return unique_dates


def _extract_relative_date_range(message: str, *, today: date) -> DateRange | None:
    lowered = message.casefold()
    if "next weekend" in lowered:
        upcoming_saturday = _next_weekday(today=today, weekday=5, include_today=False)
        start = upcoming_saturday + timedelta(days=7)
        end = start + timedelta(days=1)
        return DateRange(start=start, end=end)

    if "this weekend" in lowered:
        start = _next_weekday(today=today, weekday=5, include_today=True)
        end = start + timedelta(days=1)
        return DateRange(start=start, end=end)

    return None


def _next_weekday(*, today: date, weekday: int, include_today: bool) -> date:
    delta_days = (weekday - today.weekday()) % 7
    if delta_days == 0 and not include_today:
        delta_days = 7
    return today + timedelta(days=delta_days)


def _build_date_range(*, start: date, end: date) -> DateRange:
    if end < start:
        start, end = end, start
    return DateRange(start=start, end=end)


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _extract_trip_length_days(message: str) -> int | None:
    day_match = _TRIP_DAYS_PATTERN.search(message)
    if day_match is not None:
        return int(day_match.group("days"))

    week_match = _TRIP_WEEKS_PATTERN.search(message)
    if week_match is not None:
        return int(week_match.group("weeks")) * 7

    return None


def _extract_budget(
    message: str,
    *,
    fallback_currency: str | None,
    allow_bare_amount: bool = False,
) -> BudgetRange | None:
    currency = _extract_currency(message) or fallback_currency or "USD"

    range_match = _BUDGET_RANGE_PATTERN.search(message)
    if range_match is not None:
        minimum = _parse_amount(range_match.group("minimum"))
        maximum = _parse_amount(range_match.group("maximum"))
        if minimum is not None and maximum is not None:
            if maximum < minimum:
                minimum, maximum = maximum, minimum
            return BudgetRange(min=minimum, max=maximum, currency=currency.upper())

    dash_range_match = _BUDGET_DASH_RANGE_PATTERN.search(message)
    if dash_range_match is not None:
        minimum = _parse_amount(dash_range_match.group("minimum"))
        maximum = _parse_amount(dash_range_match.group("maximum"))
        if minimum is not None and maximum is not None:
            if maximum < minimum:
                minimum, maximum = maximum, minimum
            return BudgetRange(min=minimum, max=maximum, currency=currency.upper())

    max_match = _BUDGET_MAX_PATTERN.search(message)
    if max_match is not None:
        maximum = _parse_amount(max_match.group("maximum"))
        if maximum is not None:
            return BudgetRange(min=0.0, max=maximum, currency=currency.upper())

    single_amount_match = _BUDGET_SINGLE_PATTERN.search(message)
    if single_amount_match is not None:
        amount = _parse_amount(single_amount_match.group("amount"))
        if amount is not None:
            return BudgetRange(min=0.0, max=amount, currency=currency.upper())

    if allow_bare_amount:
        bare_amount_match = _BARE_BUDGET_REPLY_PATTERN.search(message)
        if bare_amount_match is None:
            bare_amount_match = _TRAILING_BUDGET_REPLY_PATTERN.search(message)
        if bare_amount_match is not None:
            amount = _parse_amount(bare_amount_match.group("amount"))
            if amount is not None:
                bare_currency = (
                    _normalize_currency_code(bare_amount_match.group("currency"))
                    or currency.upper()
                )
                return BudgetRange(min=0.0, max=amount, currency=bare_currency)

    lowered = message.casefold()
    if any(token in lowered for token in ("cheap", "budget-friendly", "low budget")):
        return BudgetRange(min=0.0, max=1500.0, currency=currency.upper())
    if any(token in lowered for token in ("mid-range", "medium budget", "moderate")):
        return BudgetRange(min=1500.0, max=3500.0, currency=currency.upper())
    if any(token in lowered for token in ("luxury", "high-end", "premium")):
        return BudgetRange(min=3500.0, max=10000.0, currency=currency.upper())

    return None


def _extract_currency(message: str) -> str | None:
    lowered = message.casefold()
    for token, code in _CURRENCY_ALIASES.items():
        if re.search(rf"\b{token}\b", lowered):
            return code
    if "$" in message:
        return "USD"
    if "\u20ac" in message:
        return "EUR"
    if "\u00a3" in message:
        return "GBP"
    return None


def _normalize_currency_code(raw_currency: str | None) -> str | None:
    if raw_currency is None:
        return None
    return _CURRENCY_ALIASES.get(raw_currency.strip().casefold())


def _parse_amount(raw_value: str) -> float | None:
    normalized = raw_value.strip().casefold().replace(",", "")
    multiplier = 1.0
    if normalized.endswith("k"):
        multiplier = 1000.0
        normalized = normalized[:-1]
    try:
        return float(normalized) * multiplier
    except ValueError:
        return None


def _extract_party_size(message: str) -> PartySize | None:
    adults_children_match = _PARTY_ADULTS_CHILDREN_PATTERN.search(message)
    if adults_children_match is not None:
        adults = int(adults_children_match.group("adults"))
        children_group = adults_children_match.group("children")
        children = int(children_group) if children_group is not None else 0
        return PartySize(adults=adults, children=children)

    children_adults_match = _PARTY_CHILDREN_ADULTS_PATTERN.search(message)
    if children_adults_match is not None:
        children = int(children_adults_match.group("children"))
        adults = int(children_adults_match.group("adults"))
        return PartySize(adults=adults, children=children)

    total_match = _PARTY_TOTAL_PATTERN.search(message)
    if total_match is not None:
        total = int(total_match.group("total"))
        if total >= 1:
            return PartySize(adults=total, children=0)

    return None


def _extract_weighted_interests(message: str) -> dict[str, float]:
    lowered = " ".join(message.casefold().split())
    weights: dict[str, float] = {}
    for interest, keywords in _INTEREST_KEYWORDS.items():
        if any(_has_positive_keyword_phrase(lowered, keyword) for keyword in keywords):
            weights[interest] = 0.8
    return weights


def _deep_merge_payload(
    base_payload: dict[str, Any],
    patch_payload: Mapping[str, Any],
) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base_payload)
    for key, raw_value in patch_payload.items():
        value = _normalize_patch_value(raw_value)
        if value is None:
            continue

        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(value, Mapping):
            merged[key] = _deep_merge_payload(base_value, value)
            continue

        merged[key] = value
    return merged


def _normalize_patch_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python")
    return value


def _merge_query_fragments(*fragments: str) -> str:
    normalized_fragments = [
        fragment.strip() for fragment in fragments if fragment and fragment.strip()
    ]
    return " ".join(dict.fromkeys(normalized_fragments))


def _contains_keyword_phrase(message: str, keyword: str) -> bool:
    normalized_keyword = " ".join(keyword.casefold().split())
    if not normalized_keyword:
        return False
    pattern = rf"(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])"
    return re.search(pattern, message) is not None


def _has_positive_keyword_phrase(message: str, keyword: str) -> bool:
    normalized_keyword = " ".join(keyword.casefold().split())
    if not normalized_keyword:
        return False
    pattern = rf"(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])"
    for match in re.finditer(pattern, message):
        if not _match_is_negated(message=message, start_index=match.start()):
            return True
    return False


def _match_is_negated(*, message: str, start_index: int) -> bool:
    prefix_tokens = re.findall(r"[a-z0-9]+", message[:start_index])
    if not prefix_tokens:
        return False

    if prefix_tokens[-1] in {"no", "not", "without", "avoid", "avoiding", "skip"}:
        return True

    if len(prefix_tokens) >= 2 and tuple(prefix_tokens[-2:]) in {
        ("rather", "than"),
        ("instead", "of"),
    }:
        return True

    return False


def _looks_like_bare_destination(value: str) -> bool:
    tokens = value.casefold().split()
    if not tokens:
        return False

    non_joiner_tokens = [
        token for token in tokens if token not in _LOCATION_JOINER_WORDS
    ]
    if not non_joiner_tokens:
        return False

    for token in non_joiner_tokens:
        if token in _BARE_DESTINATION_DISALLOWED_TOKENS:
            return False
        if token in _DESTINATION_STOPWORDS:
            return False
        if not _BARE_DESTINATION_WORD_PATTERN.fullmatch(token):
            return False

    return True


def _should_try_bare_route(
    *,
    message: str,
    session_state: SessionState | None,
) -> bool:
    if extract_query_filters(message).get("item_type") == "flight":
        return True
    if session_state is None:
        return False
    if session_state.conversation.last_recommendation_item_type == "flight":
        return True
    if "origin" in session_state.conversation.last_requested_slots:
        return True
    if (
        "destination" in session_state.conversation.last_requested_slots
        and session_state.conversation.last_recommendation_item_type == "flight"
    ):
        return True
    return False
