"""Tests for the chat endpoint orchestration and persistence flow."""

from __future__ import annotations

import uuid
from typing import Any

from app.api.v1.chat import get_orchestrator_service
from app.db.models.message import Message
from app.db.models.recommendation import Recommendation
from app.db.models.session import Session
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.schemas.orchestrator import OrchestratorResponse
from fastapi.testclient import TestClient


class _FakeResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


class _FakeAsyncSession:
    def __init__(
        self,
        existing_session: Session | None = None,
        existing_user: User | None = None,
    ) -> None:
        self.existing_session = existing_session
        self.existing_user = existing_user
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False
        self.flushed = False

    async def execute(self, statement: Any) -> _FakeResult:
        entity = statement.column_descriptions[0].get("entity")
        if entity is Session:
            return _FakeResult(self.existing_session)
        if entity is User:
            return _FakeResult(self.existing_user)
        return _FakeResult(None)

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        if isinstance(obj, Session):
            self.existing_session = obj
        if isinstance(obj, User):
            self.existing_user = obj

    async def commit(self) -> None:
        self.committed = True

    async def flush(self) -> None:
        self.flushed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class _FakeOrchestratorService:
    def __init__(
        self,
        *,
        assistant_message: str,
        recommendations: list[dict[str, Any]],
        state: dict[str, Any],
    ) -> None:
        self.assistant_message = assistant_message
        self.recommendations = recommendations
        self.state = state

    def handle_message(
        self,
        *,
        user_message: str,
        session_state: Any,
    ) -> OrchestratorResponse:
        del user_message
        del session_state
        return OrchestratorResponse.model_validate(
            {
                "session_id": self.state["session_id"],
                "assistant_message": self.assistant_message,
                "recommendations": self.recommendations,
                "itinerary": {"days": []},
                "state": self.state,
            }
        )


class _FailingOrchestratorService:
    def handle_message(
        self,
        *,
        user_message: str,
        session_state: Any,
    ) -> OrchestratorResponse:
        del user_message
        del session_state
        raise RuntimeError("orchestrator failure")


def _override_db(fake_db: _FakeAsyncSession):
    async def _dependency():
        yield fake_db

    return _dependency


def _chat_payload() -> dict[str, Any]:
    return {
        "session_id": "session-123",
        "message_id": "msg-001",
        "user_id": str(uuid.uuid4()),
        "message": "recommend me a trip to Lisbon",
        "client_context": {
            "timezone": "UTC",
            "locale": "en-US",
            "currency": "USD",
        },
    }


def test_chat_endpoint_returns_expected_shape_and_persists_records() -> None:
    fake_db = _FakeAsyncSession()
    fake_orchestrator = _FakeOrchestratorService(
        assistant_message="I found 1 strong option for Lisbon.",
        recommendations=[
            {
                "item_id": "dest-lisbon",
                "item_type": "destination",
                "score": 0.93,
                "rank": 1,
                "features": {"interest_match": 0.9},
                "explanation": "Excellent match for culture and food.",
            }
        ],
        state={
            "state_version": "v1",
            "session_id": "session-123",
            "user_id": None,
            "constraints": {},
            "preferences": {"weighted_interests": {}, "dislikes": []},
            "entities": {"destinations": []},
            "shortlist": [],
            "itinerary": {"days": []},
            "status": "refine",
            "last_recommendation_version": "heuristic-v1",
            "last_message_at": "2026-02-12T10:00:00Z",
        },
    )
    app.dependency_overrides[get_db] = _override_db(fake_db)
    app.dependency_overrides[get_orchestrator_service] = lambda: fake_orchestrator

    try:
        client = TestClient(app)
        response = client.post("/api/v1/chat", json=_chat_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "session-123"
    assert body["message_id"] == "msg-001"
    assert body["assistant_message"] == "I found 1 strong option for Lisbon."
    assert len(body["recommendations"]) == 1
    assert body["recommendations"][0]["metadata"] == {"interest_match": 0.9}
    assert fake_db.flushed is True
    assert fake_db.committed is True

    sessions = [item for item in fake_db.added if isinstance(item, Session)]
    assert len(sessions) == 1
    assert sum(isinstance(item, Message) for item in fake_db.added) == 2
    assert sum(isinstance(item, Recommendation) for item in fake_db.added) == 1
    assert sessions[0].user_id is None
    assert sessions[0].state_json["user_id"] is None


def test_chat_endpoint_rejects_invalid_payload() -> None:
    fake_db = _FakeAsyncSession()
    app.dependency_overrides[get_db] = _override_db(fake_db)

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "session_id": "session-123",
                "message_id": "msg-001",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert fake_db.committed is False


def test_chat_endpoint_allows_empty_recommendations() -> None:
    fake_db = _FakeAsyncSession()
    fake_orchestrator = _FakeOrchestratorService(
        assistant_message="I need more detail to find strong matches.",
        recommendations=[],
        state={
            "state_version": "v1",
            "session_id": "session-123",
            "user_id": None,
            "constraints": {},
            "preferences": {"weighted_interests": {}, "dislikes": []},
            "entities": {"destinations": []},
            "shortlist": [],
            "itinerary": {"days": []},
            "status": "explore",
            "last_recommendation_version": "heuristic-v1",
            "last_message_at": "2026-02-12T10:00:00Z",
        },
    )
    app.dependency_overrides[get_db] = _override_db(fake_db)
    app.dependency_overrides[get_orchestrator_service] = lambda: fake_orchestrator

    try:
        client = TestClient(app)
        response = client.post("/api/v1/chat", json=_chat_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["recommendations"] == []
    assert body["assistant_message"] == "I need more detail to find strong matches."
    assert fake_db.committed is True
    snapshots = [item for item in fake_db.added if isinstance(item, Recommendation)]
    assert len(snapshots) == 1
    assert snapshots[0].results_json == {"results": []}


def test_chat_endpoint_rolls_back_on_orchestrator_failure() -> None:
    fake_db = _FakeAsyncSession()
    app.dependency_overrides[get_db] = _override_db(fake_db)
    app.dependency_overrides[get_orchestrator_service] = (
        lambda: _FailingOrchestratorService()
    )

    try:
        client = TestClient(app)
        response = client.post("/api/v1/chat", json=_chat_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json()["error"]["message"] == "Failed to process chat message"
    assert fake_db.committed is False
    assert fake_db.rolled_back is True


def test_chat_endpoint_rolls_back_on_invalid_state_payload() -> None:
    fake_db = _FakeAsyncSession()
    fake_orchestrator = _FakeOrchestratorService(
        assistant_message="I found options, but state is malformed.",
        recommendations=[],
        state={"session_id": "session-123", "status": "invalid-status"},
    )
    app.dependency_overrides[get_db] = _override_db(fake_db)
    app.dependency_overrides[get_orchestrator_service] = lambda: fake_orchestrator

    try:
        client = TestClient(app)
        response = client.post("/api/v1/chat", json=_chat_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Invalid session state payload"
    assert fake_db.committed is False
    assert fake_db.rolled_back is True
