"""Tests for DB engine/session factory behavior."""

from app.db.session import get_engine, get_session_factory


def test_engine_and_session_factory_are_cached() -> None:
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    first_engine = get_engine()
    second_engine = get_engine()
    assert first_engine is second_engine

    first_factory = get_session_factory()
    second_factory = get_session_factory()
    assert first_factory is second_factory

    get_session_factory.cache_clear()
    get_engine.cache_clear()
