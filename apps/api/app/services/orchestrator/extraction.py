"""Deterministic extraction of session-state updates from user messages."""

from __future__ import annotations

import re
from datetime import date, timedelta

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
    "food": ("food", "restaurant", "dining", "cafe"),
    "nightlife": ("nightlife", "bar", "club", "cocktail", "pub"),
    "shopping": ("shopping", "shop", "boutique", "mall", "fashion"),
    "beaches": ("beach", "coast", "seaside"),
    "culture": ("museum", "art", "history", "gallery"),
    "nature": ("nature", "hiking", "mountain", "park", "outdoors"),
}

_ROUTE_PATTERN = re.compile(
    r"\bfrom\s+(?P<origin>[a-z][a-z .'-]{1,64}?)\s+to\s+"
    r"(?P<destination>[a-z][a-z .'-]{1,64}?)(?=(?:\s+(?:for|with|on|between|"
    r"under|over|budget|from|starting|start|end|in|at|by)\b)|[,.!?;]|$)",
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
        r"\bdestination(?:\s+is)?\s*[:\-]?\s*"
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

_ISO_DATE_PATTERN = re.compile(
    r"\b(?P<year>\d{4})[-/](?P<month>\d{1,2})[-/](?P<day>\d{1,2})\b"
)
_MONTH_WORD = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|"
    r"nov(?:ember)?|dec(?:ember)?"
)
_MONTH_NAME_DATE_PATTERN = re.compile(
    rf"\b(?P<month>{_MONTH_WORD})\.?\s+(?P<day>\d{{1,2}})"
    rf"(?:,\s*|\s+)?(?P<year>\d{{4}})?\b",
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
        r"\bdestination\b",
        r"\bdestinations\b",
        r"\bwhere should i go\b",
        r"\bplaces to visit\b",
    ),
}


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

    origin, destination = _extract_route(normalized_message)
    if origin is None:
        origin = _extract_origin(normalized_message)
    if destination is None:
        destination = _extract_destination(normalized_message)

    if origin is not None:
        next_state.constraints.origin = origin
    if destination is not None:
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
            (parsed_dates.end - parsed_dates.start).days + 1
        )
    else:
        trip_length_days = _extract_trip_length_days(normalized_message)
        if trip_length_days is not None:
            next_state.constraints.trip_length_days = trip_length_days

    fallback_currency = (
        next_state.constraints.budget.currency
        if next_state.constraints.budget is not None
        else None
    )
    parsed_budget = _extract_budget(
        normalized_message, fallback_currency=fallback_currency
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


def _extract_route(message: str) -> tuple[str | None, str | None]:
    match = _ROUTE_PATTERN.search(message)
    if match is None:
        return None, None
    origin = _normalize_location(match.group("origin"))
    destination = _normalize_location(match.group("destination"))
    return origin, destination


def _extract_origin(message: str) -> str | None:
    match = _ORIGIN_PATTERN.search(message)
    if match is None:
        return None
    return _normalize_location(match.group("origin"))


def _extract_destination(message: str) -> str | None:
    for pattern in _DESTINATION_PATTERNS:
        match = pattern.search(message)
        if match is None:
            continue
        destination = _normalize_location(match.group("destination"))
        if destination is not None:
            return destination
    return None


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

    for match in _MONTH_NAME_DATE_PATTERN.finditer(message):
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
    for code in ("usd", "eur", "gbp", "cad", "aud", "jpy", "inr"):
        if re.search(rf"\b{code}\b", lowered):
            return code.upper()
    if "$" in message:
        return "USD"
    if "\u20ac" in message:
        return "EUR"
    if "\u00a3" in message:
        return "GBP"
    return None


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
    lowered = message.casefold()
    weights: dict[str, float] = {}
    for interest, keywords in _INTEREST_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            weights[interest] = 0.8
    return weights
