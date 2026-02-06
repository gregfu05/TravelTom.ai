"""Contract tests for the event ORM model."""

from app.db.models.event import Event


def test_event_idempotency_index_is_scoped_by_session_and_type() -> None:
    indexes = {index.name: index for index in Event.__table__.indexes}

    scoped_index = indexes["idx_events_idempotency"]
    scoped_columns = [column.name for column in scoped_index.columns]

    assert scoped_index.unique is True
    assert scoped_columns == ["session_id", "event_type", "idempotency_key"]


def test_event_session_id_is_required() -> None:
    assert Event.__table__.c.session_id.nullable is False
