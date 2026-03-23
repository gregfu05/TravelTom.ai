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
