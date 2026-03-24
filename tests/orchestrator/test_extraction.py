"""Tests for deterministic session-state extraction from user messages."""

from __future__ import annotations

from datetime import date

import pytest
from app.schemas.state import SessionState
from app.services.orchestrator.extraction import (
    apply_message_state_updates,
    apply_structured_state_patch,
    build_effective_recommendation_query_text,
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

    assert updated.constraints.origin == "NYC"
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


def test_extracts_one_shot_destination_dates_and_budget_without_treating_budget_as_year(
) -> None:
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


def test_explicit_item_type_override_beats_carried_type() -> None:
    state = SessionState.model_validate(
        {
            "session_id": "sess-1",
            "conversation": {"last_recommendation_item_type": "hotel"},
        }
    )

    assert (
        resolve_effective_item_type(message="actually flights", session_state=state)
        == "flight"
    )
    assert (
        build_effective_recommendation_query_text(
            message="actually flights",
            session_state=state,
        )
        == "actually flights"
    )


def test_search_type_reply_reuses_prior_query_context() -> None:
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
        == "hotel"
    )
    assert is_vague_acceptance_reply("Anything works") is True
    assert (
        build_effective_recommendation_query_text(
            message="Anything works",
            session_state=state,
        )
        == "Anything works Santa Barbara 10th May to 20th May 2000 euros"
    )


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


def test_flight_context_extracts_bare_route_reply() -> None:
    state = SessionState.model_validate(
        {
            "session_id": "sess-flight-route",
            "conversation": {
                "last_requested_slots": ["origin", "destination"],
                "last_user_intent": "recommend",
                "last_recommendation_item_type": "flight",
            },
        }
    )

    updated = apply_message_state_updates(
        message="Madrid to Lisbon",
        session_state=state,
        today=date(2026, 3, 23),
    )

    assert updated.constraints.origin == "Madrid"
    assert updated.constraints.destination == "Lisbon"
