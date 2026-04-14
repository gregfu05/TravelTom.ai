"""Tests for the chat endpoint orchestration and persistence flow."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.errors import ApiError
from app.db.models.message import Message
from app.db.models.recommendation import Recommendation
from app.db.models.session import Session
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.schemas.orchestrator import OrchestratorResponse, TranscriptMessage
from app.services.chat_persistence import session_pk
from app.services.travel_tom_agent import get_travel_tom_agent
from fastapi.testclient import TestClient


class _FakeResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalars(self) -> list[Any]:
        if isinstance(self._value, list):
            return self._value
        return []


class _FakeAsyncSession:
    def __init__(
        self,
        existing_session: Session | None = None,
        existing_user: User | None = None,
        existing_messages: list[Message] | None = None,
        existing_recommendations: list[Recommendation] | None = None,
    ) -> None:
        self.existing_session = existing_session
        self.existing_user = existing_user
        self.existing_messages = existing_messages or []
        self.existing_recommendations = existing_recommendations or []
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
        if entity is Message:
            if getattr(statement, "_limit_clause", None) is None:
                return _FakeResult(list(self.existing_messages))
            return _FakeResult(list(reversed(self.existing_messages)))
        if entity is Recommendation:
            if not self.existing_recommendations:
                return _FakeResult(None)
            return _FakeResult(self.existing_recommendations[-1])
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


class _FakeTravelTomAgent:
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
        self.recent_messages_seen: list[TranscriptMessage] | None = None

    @property
    def recent_history_limit(self) -> int:
        return 6

    def handle_chat(
        self,
        *,
        user_message: str,
        session_state: Any,
        recent_messages: list[TranscriptMessage] | None = None,
    ) -> OrchestratorResponse:
        del user_message
        del session_state
        self.recent_messages_seen = recent_messages
        return OrchestratorResponse.model_validate(
            {
                "session_id": self.state["session_id"],
                "assistant_message": self.assistant_message,
                "recommendations": self.recommendations,
                "itinerary": {"days": []},
                "state": self.state,
            }
        )


class _FailingTravelTomAgent:
    @property
    def recent_history_limit(self) -> int:
        return 6

    def handle_chat(
        self,
        *,
        user_message: str,
        session_state: Any,
        recent_messages: list[TranscriptMessage] | None = None,
    ) -> OrchestratorResponse:
        del user_message
        del session_state
        del recent_messages
        raise RuntimeError("orchestrator failure")


class _ProviderRateLimitedAgent:
    @property
    def recent_history_limit(self) -> int:
        return 6

    def handle_chat(
        self,
        *,
        user_message: str,
        session_state: Any,
        recent_messages: list[TranscriptMessage] | None = None,
    ) -> OrchestratorResponse:
        del user_message
        del session_state
        del recent_messages
        raise ApiError(
            status_code=429,
            code="provider_rate_limited",
            message="Upstream chat provider is rate limited",
            details={
                "provider": "openai",
                "retry_after_seconds": 17,
                "source": "provider",
                "upstream_error_type": "RateLimitError",
                "upstream_status_code": 429,
            },
            headers={"Retry-After": "17"},
        )


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
    fake_db = _FakeAsyncSession(
        existing_messages=[
            Message(role="user", content="I want a city break."),
            Message(role="assistant", content="Which destination should I focus on?"),
        ]
    )
    fake_agent = _FakeTravelTomAgent(
        assistant_message="I found 1 strong option for Lisbon.",
        recommendations=[
            {
                "item_id": "restaurant-lisbon",
                "item_type": "restaurant",
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
            "conversation": {
                "last_requested_slots": ["budget"],
                "last_user_intent": "recommend",
                "last_recommendation_item_type": "restaurant",
                "last_recommendation_query": "recommend a beach trip",
            },
            "shortlist": [],
            "itinerary": {"days": []},
            "status": "refine",
            "last_recommendation_version": "heuristic-v1",
            "last_message_at": "2026-02-12T10:00:00Z",
        },
    )
    app.dependency_overrides[get_db] = _override_db(fake_db)
    app.dependency_overrides[get_travel_tom_agent] = lambda: fake_agent

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
    assert fake_agent.recent_messages_seen is not None
    assert [message.content for message in fake_agent.recent_messages_seen] == [
        "I want a city break.",
        "Which destination should I focus on?",
    ]
    assert fake_db.flushed is True
    assert fake_db.committed is True

    sessions = [item for item in fake_db.added if isinstance(item, Session)]
    assert len(sessions) == 1
    assert sum(isinstance(item, Message) for item in fake_db.added) == 2
    assert sum(isinstance(item, Recommendation) for item in fake_db.added) == 1
    assert sessions[0].user_id is None
    assert sessions[0].state_json["user_id"] is None
    assert sessions[0].state_json["conversation"]["last_user_intent"] == "recommend"
    assert (
        sessions[0].state_json["conversation"]["last_recommendation_query"]
        == "recommend a beach trip"
    )


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
    fake_agent = _FakeTravelTomAgent(
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
    app.dependency_overrides[get_travel_tom_agent] = lambda: fake_agent

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
    app.dependency_overrides[get_travel_tom_agent] = lambda: _FailingTravelTomAgent()

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
    fake_agent = _FakeTravelTomAgent(
        assistant_message="I found options, but state is malformed.",
        recommendations=[],
        state={"session_id": "session-123", "status": "invalid-status"},
    )
    app.dependency_overrides[get_db] = _override_db(fake_db)
    app.dependency_overrides[get_travel_tom_agent] = lambda: fake_agent

    try:
        client = TestClient(app)
        response = client.post("/api/v1/chat", json=_chat_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Invalid session state payload"
    assert fake_db.committed is False
    assert fake_db.rolled_back is True


def test_chat_endpoint_returns_structured_provider_rate_limit_error() -> None:
    fake_db = _FakeAsyncSession()
    app.dependency_overrides[get_db] = _override_db(fake_db)
    app.dependency_overrides[get_travel_tom_agent] = lambda: _ProviderRateLimitedAgent()

    try:
        client = TestClient(app)
        response = client.post("/api/v1/chat", json=_chat_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "17"
    body = response.json()
    assert body["error"]["code"] == "provider_rate_limited"
    assert body["error"]["details"]["provider"] == "openai"
    assert body["error"]["details"]["retry_after_seconds"] == 17
    assert body["error"]["details"]["source"] == "provider"
    assert body["error"]["trace_id"]
    assert fake_db.committed is False
    assert fake_db.rolled_back is True


def test_get_chat_session_returns_persisted_transcript_and_recommendations() -> None:
    created_at = datetime(2026, 3, 23, 12, 0, tzinfo=timezone.utc)
    fake_db = _FakeAsyncSession(
        existing_session=Session(
            id=session_pk("session-123"),
            user_id=None,
            state_json={
                "state_version": "v1",
                "session_id": "session-123",
                "constraints": {},
                "preferences": {"weighted_interests": {}, "dislikes": []},
                "entities": {"destinations": []},
                "conversation": {
                    "last_requested_slots": ["budget"],
                    "last_user_intent": "recommend",
                    "last_recommendation_item_type": "restaurant",
                    "last_recommendation_query": "recommend a beach trip",
                    "last_recommendation_result_ids": ["restaurant-lisbon"],
                },
                "shortlist": [],
                "itinerary": {"days": []},
                "status": "refine",
                "last_recommendation_version": "heuristic-v1",
                "last_message_at": "2026-03-23T12:00:00Z",
            },
        ),
        existing_messages=[
            Message(
                id=uuid.uuid4(),
                role="user",
                content="Recommend me a trip to Lisbon",
                created_at=created_at,
            ),
            Message(
                id=uuid.uuid4(),
                role="assistant",
                content="I found 1 strong option for Lisbon.",
                created_at=created_at,
            ),
        ],
        existing_recommendations=[
            Recommendation(
                id=uuid.uuid4(),
                session_id=session_pk("session-123"),
                query_hash="abc",
                ranking_version="heuristic-v1",
                created_at=created_at,
                results_json={
                    "results": [
                        {
                            "item_id": "restaurant-lisbon",
                            "item_type": "restaurant",
                            "score": 0.93,
                            "rank": 1,
                            "features": {"name": "Lisbon"},
                            "explanation": "Excellent match for culture and food.",
                        }
                    ]
                },
            )
        ],
    )
    app.dependency_overrides[get_db] = _override_db(fake_db)

    try:
        client = TestClient(app)
        response = client.get("/api/v1/chat/session-123")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "session-123"
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][1]["role"] == "assistant"
    assert body["recommendations"][0]["item_id"] == "dest-lisbon"
    assert body["recommendations"][0]["metadata"] == {"name": "Lisbon"}


def test_get_chat_session_returns_not_found_for_unknown_session() -> None:
    fake_db = _FakeAsyncSession()
    app.dependency_overrides[get_db] = _override_db(fake_db)

    try:
        client = TestClient(app)
        response = client.get("/api/v1/chat/session-123")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "session_not_found"
