"""Tests for API startup behavior."""

from __future__ import annotations

from app.core.config import get_settings
from app.main import create_app
from fastapi.testclient import TestClient


def test_startup_preloads_recommendation_catalog_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("RECOMMENDER_PRELOAD_ON_STARTUP", "true")
    get_settings.cache_clear()
    preload_calls = {"count": 0}

    def fake_preload(_settings) -> None:
        preload_calls["count"] += 1

    monkeypatch.setattr("app.main.preload_recommendation_catalog", fake_preload)

    app = create_app()
    with TestClient(app):
        pass

    assert preload_calls["count"] == 1


def test_startup_skips_preload_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("RECOMMENDER_PRELOAD_ON_STARTUP", "false")
    get_settings.cache_clear()
    preload_calls = {"count": 0}

    def fake_preload(_settings) -> None:
        preload_calls["count"] += 1

    monkeypatch.setattr("app.main.preload_recommendation_catalog", fake_preload)

    app = create_app()
    with TestClient(app):
        pass

    assert preload_calls["count"] == 0
