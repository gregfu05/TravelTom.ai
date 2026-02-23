"""Tests for deterministic session-state extraction from user messages."""

from __future__ import annotations

from datetime import date

from app.schemas.state import SessionState
from app.services.orchestrator.extraction import apply_message_state_updates


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
