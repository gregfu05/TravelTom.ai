"""Tests for deterministic session-state extraction from user messages."""

from __future__ import annotations

from datetime import date

import pytest
from app.schemas.state import SessionState
from app.services.orchestrator.extraction import (
    apply_message_state_updates,
    apply_structured_state_patch,
    build_effective_recommendation_query_text,
    has_conversational_recommendation_signal,
    is_follow_up_refinement,
    is_vague_acceptance_reply,
    resolve_effective_item_type,
)
from pydantic import ValidationError


def test_extracts_core_constraints_from_message() -> None:
    state = SessionState(session_id="sess-1")
    updated = apply_message_state_updates(
        message=(
            "Plan a trip from NYC to Lisbon from 2026-06-10 to 2026-06-17 "
            "with budget between 1500 and 2500 USD for 2 adults and 1 child. "
            "We love food and nightlife."
        ),
        session_state=state,
        today=date(2026, 2, 23),
    )

    assert updated.constraints.destination == "Lisbon"
    assert updated.constraints.dates is not None
    assert updated.constraints.dates.start.isoformat() == "2026-06-10"
    assert updated.constraints.dates.end.isoformat() == "2026-06-17"
    assert updated.constraints.trip_length_days == 8
    assert updated.constraints.budget is not None
    assert updated.constraints.budget.min == 1500.0
    assert updated.constraints.budget.max == 2500.0
    assert updated.constraints.budget.currency == "USD"
    assert updated.constraints.party_size is not None
    assert updated.constraints.party_size.adults == 2
    assert updated.constraints.party_size.children == 1
    assert "Lisbon" in updated.entities.destinations
    assert updated.preferences.weighted_interests["food"] == 0.8
    assert updated.preferences.weighted_interests["nightlife"] == 0.8


def test_preserves_existing_constraints_when_message_has_no_new_values() -> None:
    state = SessionState.model_validate(
        {
            "session_id": "sess-1",
            "constraints": {
                "destination": "Lisbon",
                "budget": {"min": 1000, "max": 2200, "currency": "USD"},
            },
            "entities": {"destinations": ["Lisbon"]},
        }
    )

    updated = apply_message_state_updates(
        message="Suggest another option with more nightlife.",
        session_state=state,
        today=date(2026, 2, 23),
    )

    assert updated.constraints.destination == "Lisbon"
    assert updated.constraints.budget is not None
    assert updated.constraints.budget.min == 1000.0
    assert updated.constraints.budget.max == 2200.0
    assert updated.preferences.weighted_interests["nightlife"] == 0.8
    assert updated.entities.destinations == ["Lisbon"]


def test_extracts_relative_dates_and_qualitative_budget() -> None:
    state = SessionState(session_id="sess-1")
    updated = apply_message_state_updates(
        message="Recommend bars in Tokyo next weekend with medium budget for 3 people.",
        session_state=state,
        today=date(2026, 2, 23),
    )

    assert updated.constraints.destination == "Tokyo"
    assert updated.constraints.dates is not None
    assert updated.constraints.dates.start.isoformat() == "2026-03-07"
    assert updated.constraints.dates.end.isoformat() == "2026-03-08"
    assert updated.constraints.budget is not None
    assert updated.constraints.budget.min == 1500.0
    assert updated.constraints.budget.max == 3500.0
    assert updated.constraints.party_size is not None
    assert updated.constraints.party_size.adults == 3
    assert updated.constraints.party_size.children == 0


def test_extracts_day_first_month_date_ranges_with_ordinals() -> None:
    state = SessionState(session_id="sess-day-first-dates")
    updated = apply_message_state_updates(
        message="Let's go for something like 10th of May to 20th of May.",
        session_state=state,
        today=date(2026, 3, 23),
    )

    assert updated.constraints.dates is not None
    assert updated.constraints.dates.start.isoformat() == "2026-05-10"
    assert updated.constraints.dates.end.isoformat() == "2026-05-20"
    assert updated.constraints.trip_length_days == 11


def test_day_first_date_reply_does_not_overwrite_existing_destination() -> None:
    state = SessionState.model_validate(
        {
            "session_id": "sess-day-first-destination",
            "constraints": {"destination": "Santa Barbara"},
            "entities": {"destinations": ["Santa Barbara"]},
        }
    )

    updated = apply_message_state_updates(
        message="Let's do something like 10th May to 20th may",
        session_state=state,
        today=date(2026, 3, 23),
    )

    assert updated.constraints.destination == "Santa Barbara"
    assert updated.constraints.dates is not None
    assert updated.constraints.dates.start.isoformat() == "2026-05-10"
    assert updated.constraints.dates.end.isoformat() == "2026-05-20"


def test_shared_month_day_first_date_reply_fills_dates_without_overwriting_destination(
) -> None:
    state = SessionState.model_validate(
        {
            "session_id": "sess-day-first-shared-month",
            "constraints": {"destination": "Milan"},
            "entities": {"destinations": ["Milan"]},
            "conversation": {
                "last_requested_slots": ["dates"],
                "last_user_intent": "recommend",
            },
        }
    )

    updated = apply_message_state_updates(
        message="from the 20th to the 25th of April",
        session_state=state,
        today=date(2026, 4, 17),
    )

    assert updated.constraints.destination == "Milan"
    assert updated.constraints.dates is not None
    assert updated.constraints.dates.start.isoformat() == "2026-04-20"
    assert updated.constraints.dates.end.isoformat() == "2026-04-25"


@pytest.mark.parametrize(
    ("message",),
    [
        ("from the 20th to the 25th of April",),
        ("to the",),
    ],
)
def test_low_confidence_fragments_do_not_persist_as_destinations(message: str) -> None:
    state = SessionState(session_id="sess-low-confidence-destination")

    updated = apply_message_state_updates(
        message=message,
        session_state=state,
        today=date(2026, 4, 17),
    )

    assert updated.constraints.destination is None
    assert updated.entities.destinations == []


def test_extracts_bare_budget_reply_with_symbol_when_budget_slot_requested() -> None:
    state = SessionState.model_validate(
        {
            "session_id": "sess-budget-symbol",
            "conversation": {
                "last_requested_slots": ["budget"],
                "last_user_intent": "recommend",
            },
        }
    )
    updated = apply_message_state_updates(
        message="2000$",
        session_state=state,
        today=date(2026, 3, 23),
    )

    assert updated.constraints.budget is not None
    assert updated.constraints.budget.min == 0.0
    assert updated.constraints.budget.max == 2000.0
    assert updated.constraints.budget.currency == "USD"


def test_extracts_bare_budget_reply_with_currency_word_when_budget_slot_requested() -> (
    None
):
    state = SessionState.model_validate(
        {
            "session_id": "sess-budget-word",
            "conversation": {
                "last_requested_slots": ["budget"],
                "last_user_intent": "recommend",
            },
        }
    )
    updated = apply_message_state_updates(
        message="2000 euros",
        session_state=state,
        today=date(2026, 3, 23),
    )

    assert updated.constraints.budget is not None
    assert updated.constraints.budget.min == 0.0
    assert updated.constraints.budget.max == 2000.0
    assert updated.constraints.budget.currency == "EUR"


@pytest.mark.parametrize(
    ("message", "expected_min", "expected_max", "expected_currency"),
    [
        ("starting from 700 euros", 700.0, 10000.0, "EUR"),
        ("from 700", 700.0, 10000.0, "USD"),
        ("at least 700", 700.0, 10000.0, "USD"),
        ("700 and up", 700.0, 10000.0, "USD"),
        ("under 700", 0.0, 700.0, "USD"),
        ("up to 700", 0.0, 700.0, "USD"),
        ("max 700", 0.0, 700.0, "USD"),
        ("less than 700", 0.0, 700.0, "USD"),
        ("not more than 700", 0.0, 700.0, "USD"),
        ("500 to 800", 500.0, 800.0, "USD"),
        ("between 500 and 800", 500.0, 800.0, "USD"),
        ("around 700", 0.0, 700.0, "USD"),
    ],
)
def test_extracts_flexible_budget_expressions(
    message: str,
    expected_min: float,
    expected_max: float,
    expected_currency: str,
) -> None:
    state = SessionState(session_id="sess-flex-budget")

    updated = apply_message_state_updates(
        message=message,
        session_state=state,
        today=date(2026, 3, 23),
    )

    assert updated.constraints.budget is not None
    assert updated.constraints.budget.min == expected_min
    assert updated.constraints.budget.max == expected_max
    assert updated.constraints.budget.currency == expected_currency


def test_santa_barbara_does_not_false_match_bar_nightlife_interest() -> None:
    state = SessionState(session_id="sess-santa-barbara")

    updated = apply_message_state_updates(
        message="recommend something in santa barbara",
        session_state=state,
        today=date(2026, 2, 23),
    )

    assert updated.constraints.destination == "Santa Barbara"
    assert "nightlife" not in updated.preferences.weighted_interests


def test_bars_in_santa_barbara_still_capture_nightlife_interest() -> None:
    state = SessionState(session_id="sess-santa-barbara-bars")

    updated = apply_message_state_updates(
        message="recommend bars in santa barbara",
        session_state=state,
        today=date(2026, 2, 23),
    )

    assert updated.constraints.destination == "Santa Barbara"
    assert updated.preferences.weighted_interests["nightlife"] == 0.8


def test_extracts_one_shot_trip_without_budget_year_collision() -> None:
    state = SessionState(session_id="sess-one-shot")

    updated = apply_message_state_updates(
        message="Santa Barbara 10th May to 20th May 2000 euros",
        session_state=state,
        today=date(2026, 3, 23),
    )

    assert updated.constraints.destination == "Santa Barbara"
    assert updated.constraints.dates is not None
    assert updated.constraints.dates.start.isoformat() == "2026-05-10"
    assert updated.constraints.dates.end.isoformat() == "2026-05-20"
    assert updated.constraints.trip_length_days == 11
    assert updated.constraints.budget is not None
    assert updated.constraints.budget.max == 2000.0
    assert updated.constraints.budget.currency == "EUR"


def test_negated_restaurant_repair_does_not_add_food_interest() -> None:
    state = SessionState.model_validate(
        {
            "session_id": "sess-repair",
            "constraints": {"destination": "Santa Barbara"},
            "entities": {"destinations": ["Santa Barbara"]},
        }
    )

    updated = apply_message_state_updates(
        message="not restaurants, more like sightseeing",
        session_state=state,
        today=date(2026, 2, 23),
    )

    assert updated.constraints.destination == "Santa Barbara"
    assert "food" not in updated.preferences.weighted_interests


def test_extracts_bare_destination_reply() -> None:
    state = SessionState(session_id="sess-1")

    updated = apply_message_state_updates(
        message="Lisbon",
        session_state=state,
        today=date(2026, 2, 23),
    )

    assert updated.constraints.destination == "Lisbon"
    assert updated.entities.destinations == ["Lisbon"]


def test_extracts_go_to_destination_reply() -> None:
    state = SessionState(session_id="sess-go-to-destination")

    updated = apply_message_state_updates(
        message="I want to go to Santa Barbara",
        session_state=state,
        today=date(2026, 3, 23),
    )

    assert updated.constraints.destination == "Santa Barbara"
    assert updated.entities.destinations == ["Santa Barbara"]


@pytest.mark.parametrize(
    ("message",),
    [
        ("Hello Tommy",),
        ("How do you have my destination what do you mean",),
    ],
)
def test_greetings_and_meta_turns_do_not_persist_destination(message: str) -> None:
    state = SessionState(session_id="sess-1")

    updated = apply_message_state_updates(
        message=message,
        session_state=state,
        today=date(2026, 2, 23),
    )

    assert updated.constraints.destination is None
    assert updated.entities.destinations == []


def test_assignment_style_destination_still_extracts_destination() -> None:
    state = SessionState(session_id="sess-1")

    updated = apply_message_state_updates(
        message="destination: Lisbon",
        session_state=state,
        today=date(2026, 2, 23),
    )

    assert updated.constraints.destination == "Lisbon"
    assert updated.entities.destinations == ["Lisbon"]


@pytest.mark.parametrize(
    ("message",),
    [
        ("Beach + relax",),
        ("City break",),
        ("recommend a beach trip",),
        ("I'm flexible",),
    ],
)
def test_broad_vibe_prompts_do_not_persist_as_destinations(message: str) -> None:
    state = SessionState(session_id="sess-1")

    updated = apply_message_state_updates(
        message=message,
        session_state=state,
        today=date(2026, 2, 23),
    )

    assert updated.constraints.destination is None
    assert updated.entities.destinations == []


@pytest.mark.parametrize(
    ("message",),
    [
        ("show me more",),
        ("another option",),
        ("cheaper",),
        ("lower cost",),
    ],
)
def test_follow_up_refinements_do_not_overwrite_destination(message: str) -> None:
    state = SessionState.model_validate(
        {
            "session_id": "sess-1",
            "constraints": {"destination": "Lisbon"},
            "entities": {"destinations": ["Lisbon"]},
        }
    )

    updated = apply_message_state_updates(
        message=message,
        session_state=state,
        today=date(2026, 2, 23),
    )

    assert updated.constraints.destination == "Lisbon"
    assert updated.entities.destinations == ["Lisbon"]


def test_item_type_selection_does_not_overwrite_existing_destination() -> None:
    state = SessionState.model_validate(
        {
            "session_id": "sess-item-type-follow-up",
            "constraints": {"destination": "Santa Barbara"},
            "entities": {"destinations": ["Santa Barbara"]},
            "conversation": {
                "last_clarification_kind": "search_type",
                "last_user_intent": "recommend",
            },
        }
    )

    updated = apply_message_state_updates(
        message="I want hotels to be honest",
        session_state=state,
        today=date(2026, 3, 23),
    )

    assert updated.constraints.destination == "Santa Barbara"
    assert updated.entities.destinations == ["Santa Barbara"]


def test_lower_cost_without_destination_does_not_persist_destination() -> None:
    state = SessionState(session_id="sess-lower-cost")

    updated = apply_message_state_updates(
        message="lower cost",
        session_state=state,
        today=date(2026, 3, 23),
    )

    assert updated.constraints.destination is None
    assert updated.entities.destinations == []


def test_apply_structured_state_patch_merges_llm_payload() -> None:
    state = SessionState.model_validate(
        {
            "session_id": "sess-1",
            "constraints": {
                "destination": "Lisbon",
                "budget": {"min": 1000, "max": 2200, "currency": "USD"},
            },
            "entities": {"destinations": ["Lisbon"]},
        }
    )

    updated = apply_structured_state_patch(
        session_state=state,
        state_patch={
            "constraints": {
                "origin": "NYC",
                "dates": {"start": "2026-06-10", "end": "2026-06-17"},
            },
            "preferences": {"weighted_interests": {"food": 0.9}},
        },
    )

    assert updated.constraints.origin == "NYC"
    assert updated.constraints.destination == "Lisbon"
    assert updated.constraints.dates is not None
    assert updated.constraints.trip_length_days == 8
    assert updated.preferences.weighted_interests["food"] == 0.9
    assert updated.entities.destinations == ["Lisbon"]


def test_apply_structured_state_patch_rejects_invalid_payload() -> None:
    state = SessionState(session_id="sess-1")

    with pytest.raises(ValidationError):
        apply_structured_state_patch(
            session_state=state,
            state_patch={"constraints": {"budget": {"min": 100, "max": 10}}},
        )


def test_follow_up_refinement_reuses_prior_item_type_and_query_terms() -> None:
    state = SessionState.model_validate(
        {
            "session_id": "sess-1",
            "constraints": {"destination": "Lisbon"},
            "preferences": {"weighted_interests": {"nightlife": 0.8}},
            "conversation": {
                "last_recommendation_item_type": "hotel",
                "last_recommendation_query": "hotel Lisbon nightlife",
            },
        }
    )

    assert is_follow_up_refinement("show me more") is True
    assert (
        resolve_effective_item_type(message="show me more", session_state=state)
        == "hotel"
    )
    assert (
        build_effective_recommendation_query_text(
            message="show me more",
            session_state=state,
        )
        == "show me more hotel Lisbon nightlife"
    )


def test_clarification_slot_fill_turn_reuses_prior_item_type_and_query_terms() -> None:
    state = SessionState.model_validate(
        {
            "session_id": "sess-1",
            "conversation": {
                "last_requested_slots": ["destination"],
                "last_user_intent": "recommend",
                "last_recommendation_item_type": "hotel",
                "last_recommendation_query": "recommend hotels with nightlife",
            },
        }
    )

    assert resolve_effective_item_type(message="Lisbon", session_state=state) == "hotel"
    assert (
        build_effective_recommendation_query_text(
            message="Lisbon",
            session_state=state,
        )
        == "Lisbon recommend hotels with nightlife"
    )


def test_unsupported_flight_request_does_not_override_carried_item_type() -> None:
    state = SessionState.model_validate(
        {
            "session_id": "sess-1",
            "conversation": {"last_recommendation_item_type": "hotel"},
        }
    )

    assert (
        resolve_effective_item_type(message="actually flights", session_state=state)
        is None
    )
    assert (
        build_effective_recommendation_query_text(
            message="actually flights",
            session_state=state,
        )
        == "actually flights"
    )


def test_search_type_reply_reuses_prior_query_context_without_defaulting_item_type():
    state = SessionState.model_validate(
        {
            "session_id": "sess-search-type-reply",
            "constraints": {
                "destination": "Santa Barbara",
                "dates": {"start": "2026-05-10", "end": "2026-05-20"},
                "budget": {"min": 0, "max": 2000, "currency": "EUR"},
            },
            "conversation": {
                "last_user_intent": "recommend",
                "last_clarification_kind": "search_type",
                "last_recommendation_query": (
                    "Santa Barbara 10th May to 20th May 2000 euros"
                ),
            },
        }
    )

    assert (
        resolve_effective_item_type(message="Anything works", session_state=state)
        is None
    )
    assert is_vague_acceptance_reply("Anything works") is True
    assert (
        build_effective_recommendation_query_text(
            message="Anything works",
            session_state=state,
        )
        == "Anything works Santa Barbara 10th May to 20th May 2000 euros"
    )


@pytest.mark.parametrize(
    ("message", "expected_item_type"),
    [
        ("I want chicken", "restaurant"),
        ("something fun tonight", "activity"),
        ("I need a room", "hotel"),
    ],
)
def test_conversational_item_type_inference_resolves_likely_domain(
    message: str, expected_item_type: str
) -> None:
    state = SessionState(session_id="sess-conversational-intent")

    assert resolve_effective_item_type(message=message, session_state=state) == (
        expected_item_type
    )


@pytest.mark.parametrize(
    ("message",),
    [
        ("I want somewhere nice",),
        ("not too expensive",),
    ],
)
def test_conversational_recommendation_signal_detects_vague_preference_requests(
    message: str,
) -> None:
    assert has_conversational_recommendation_signal(message) is True


def test_natural_hotel_phrase_extracts_destination_dates_and_budget() -> None:
    state = SessionState(session_id="sess-natural-hotel-phrase")

    updated = apply_message_state_updates(
        message="Hotels in Santa Barbara May 10th to May 20th under 2000 euros",
        session_state=state,
        today=date(2026, 3, 23),
    )

    assert updated.constraints.destination == "Santa Barbara"
    assert updated.constraints.dates is not None
    assert updated.constraints.dates.start.isoformat() == "2026-05-10"
    assert updated.constraints.dates.end.isoformat() == "2026-05-20"
    assert updated.constraints.budget is not None
    assert updated.constraints.budget.max == 2000.0
    assert updated.constraints.budget.currency == "EUR"


def test_inline_trailing_budget_phrase_extracts_budget_for_complete_hotel_request() -> (
    None
):
    state = SessionState(session_id="sess-inline-budget")

    updated = apply_message_state_updates(
        message="Santa Barbara May 10-20, 2000 EUR, hotels",
        session_state=state,
        today=date(2026, 3, 23),
    )

    assert updated.constraints.destination == "Santa Barbara"
    assert updated.constraints.dates is not None
    assert updated.constraints.budget is not None
    assert updated.constraints.budget.max == 2000.0
    assert updated.constraints.budget.currency == "EUR"


def test_shorthand_relative_dates_do_not_pollute_destination() -> None:
    state = SessionState(session_id="sess-shorthand-typos")

    updated = apply_message_state_updates(
        message="need smth chill in lisbn nxt wknd",
        session_state=state,
        today=date(2026, 3, 23),
    )

    assert updated.constraints.destination == "Lisbn"
    assert updated.constraints.dates is not None
    assert updated.constraints.dates.start.isoformat() == "2026-04-04"
    assert updated.constraints.dates.end.isoformat() == "2026-04-05"


def test_unsupported_flight_request_does_not_capture_trip_constraints() -> None:
    updated = apply_message_state_updates(
        message="Find me flights from Paris to Lisbon next weekend",
        session_state=SessionState(session_id="sess-unsupported-flight"),
        today=date(2026, 3, 23),
    )

    assert updated.constraints.origin is None
    assert updated.constraints.destination is None
    assert updated.constraints.dates is None


def test_unsupported_flight_route_reply_does_not_capture_origin_or_item_type() -> None:
    state = SessionState.model_validate(
        {
            "session_id": "sess-unsupported-route",
            "conversation": {
                "last_requested_slots": ["origin", "destination"],
                "last_user_intent": "recommend",
                "last_recommendation_item_type": "hotel",
            },
        }
    )

    updated = apply_message_state_updates(
        message="Madrid to Lisbon",
        session_state=state,
        today=date(2026, 3, 23),
    )

    assert updated.constraints.origin is None
    assert updated.constraints.destination is None


def test_vague_empty_results_reply_preserves_prior_query_context() -> None:
    state = SessionState.model_validate(
        {
            "session_id": "sess-empty-vague",
            "constraints": {
                "destination": "Santa Barbara",
                "dates": {"start": "2026-05-10", "end": "2026-05-20"},
                "budget": {"min": 0, "max": 2000, "currency": "USD"},
            },
            "conversation": {
                "last_user_intent": "recommend",
                "last_clarification_kind": "refine_preference",
                "last_search_outcome": "empty_results",
                "last_recommendation_item_type": "hotel",
                "last_recommendation_query": (
                    "Hotels in Santa Barbara from 2026-05-10 to 2026-05-20 "
                    "under 2000 USD"
                ),
            },
        }
    )

    assert (
        build_effective_recommendation_query_text(
            message="anything works",
            session_state=state,
        )
        == (
            "anything works Hotels in Santa Barbara from 2026-05-10 to "
            "2026-05-20 under 2000 USD"
        )
    )
