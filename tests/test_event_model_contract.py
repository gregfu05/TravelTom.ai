"""Contract tests for the event ORM model."""

from typing import cast

from app.db.models.event import Event
from sqlalchemy import Table


def test_event_idempotency_index_is_scoped_by_session_and_type() -> None:
    table = cast(Table, Event.__table__)
    scoped_index = next(
        (
            index
            for index in table.indexes
            if str(index.name) == "idx_events_idempotency"
        ),
        None,
    )
    assert scoped_index is not None
    scoped_columns = [column.name for column in scoped_index.columns]

    assert scoped_index.unique is True
    assert scoped_columns == ["session_id", "event_type", "idempotency_key"]


def test_event_session_id_is_required() -> None:
    assert Event.__table__.c.session_id.nullable is False
