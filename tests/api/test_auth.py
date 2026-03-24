"""Tests for auth, authorization, and rate limiting behavior."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.config import get_settings
from app.core.security import (
    get_azure_b2c_scheme,
    get_chat_rate_limiter,
    require_authenticated_principal,
)
from app.db.models.message import Message
from app.db.models.recommendation import Recommendation
from app.db.models.session import Session
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.schemas.auth import AuthenticatedPrincipal
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


def _override_db(fake_db: _FakeAsyncSession):
    async def _dependency():
        yield fake_db

    return _dependency


class _FakeTravelTomAgent:
    def __init__(
        self,
        *,
        assistant_message: str,
        state: dict[str, Any],
    ) -> None:
        self.assistant_message = assistant_message
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
                "recommendations": [],
                "itinerary": {"days": []},
                "state": self.state,
            }
        )


def _chat_payload() -> dict[str, Any]:
    return {
        "session_id": "session-auth",
        "message_id": "msg-auth-001",
        "user_id": str(uuid.uuid4()),
        "message": "plan a city break",
    }


def _principal(subject: str = "subject-123") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject=subject,
        issuer="https://traveltomtest.b2clogin.com/example.onmicrosoft.com/v2.0/",
        email="traveler@example.com",
        name="Traveler",
        scopes=["user_impersonation"],
        raw_claims={"sub": subject},
    )


def _enable_auth(monkeypatch, *, chat_rate_limit: str = "30/minute") -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_APP_CLIENT_ID", "traveltom-api-client")
    monkeypatch.setenv("AUTH_TENANT_NAME", "traveltomtest")
    monkeypatch.setenv("AUTH_POLICY_NAME", "B2C_1_signin")
    monkeypatch.setenv("AUTH_REQUIRED_SCOPES", "user_impersonation")
    monkeypatch.setenv("CHAT_RATE_LIMIT", chat_rate_limit)
    get_settings.cache_clear()
    get_azure_b2c_scheme.cache_clear()
    get_chat_rate_limiter().reset()


def test_chat_requires_bearer_token_when_auth_enabled(monkeypatch) -> None:
    _enable_auth(monkeypatch)

    client = TestClient(app)
    response = client.post("/api/v1/chat", json=_chat_payload())

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert response.json()["error"]["message"] == "Missing bearer token"


def test_get_chat_session_requires_bearer_token_when_auth_enabled(monkeypatch) -> None:
    _enable_auth(monkeypatch)

    client = TestClient(app)
    response = client.get("/api/v1/chat/session-auth")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert response.json()["error"]["message"] == "Missing bearer token"


def test_recommendations_require_bearer_token_when_auth_enabled(monkeypatch) -> None:
    _enable_auth(monkeypatch)

    client = TestClient(app)
    response = client.post(
        "/api/v1/recommendations/query",
        json={
            "session_id": "session-auth",
            "query": "weekend in lisbon",
            "constraints": {},
            "max_results": 5,
            "ranking_version": "heuristic-v1",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert response.json()["error"]["message"] == "Missing bearer token"


def test_chat_ignores_body_user_id_and_persists_authenticated_owner(
    monkeypatch,
) -> None:
    _enable_auth(monkeypatch)
    fake_db = _FakeAsyncSession()
    fake_agent = _FakeTravelTomAgent(
        assistant_message="Here are a few ideas.",
        state={
            "state_version": "v1",
            "session_id": "session-auth",
            "user_id": None,
            "constraints": {},
            "preferences": {"weighted_interests": {}, "dislikes": []},
            "entities": {"destinations": []},
            "shortlist": [],
            "itinerary": {"days": []},
            "status": "explore",
            "last_recommendation_version": "heuristic-v1",
            "last_message_at": "2026-03-07T19:15:00Z",
        },
    )

    app.dependency_overrides[get_db] = _override_db(fake_db)
    app.dependency_overrides[get_travel_tom_agent] = lambda: fake_agent
    app.dependency_overrides[require_authenticated_principal] = lambda: _principal()

    try:
        client = TestClient(app)
        response = client.post("/api/v1/chat", json=_chat_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert fake_db.existing_user is not None
    assert fake_db.existing_session is not None
    assert fake_db.existing_session.user_id == fake_db.existing_user.id
    assert fake_db.existing_session.state_json["user_id"] == str(
        fake_db.existing_user.id
    )


def test_chat_rejects_other_users_session(monkeypatch) -> None:
    _enable_auth(monkeypatch)
    existing_owner_id = uuid.uuid4()
    fake_db = _FakeAsyncSession(
        existing_session=Session(
            id=session_pk("session-auth"),
            user_id=existing_owner_id,
            state_json={"state_version": "v1", "session_id": "session-auth"},
        )
    )

    app.dependency_overrides[get_db] = _override_db(fake_db)
    app.dependency_overrides[require_authenticated_principal] = lambda: _principal(
        "different-subject"
    )

    try:
        client = TestClient(app)
        response = client.post("/api/v1/chat", json=_chat_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert (
        response.json()["error"]["message"]
        == "Session does not belong to the authenticated user"
    )


def test_get_chat_session_rejects_other_users_session(monkeypatch) -> None:
    _enable_auth(monkeypatch)
    existing_owner_id = uuid.uuid4()
    fake_db = _FakeAsyncSession(
        existing_session=Session(
            id=session_pk("session-auth"),
            user_id=existing_owner_id,
            state_json={"state_version": "v1", "session_id": "session-auth"},
        )
    )

    app.dependency_overrides[get_db] = _override_db(fake_db)
    app.dependency_overrides[require_authenticated_principal] = lambda: _principal(
        "different-subject"
    )

    try:
        client = TestClient(app)
        response = client.get("/api/v1/chat/session-auth")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert (
        response.json()["error"]["message"]
        == "Session does not belong to the authenticated user"
    )


def test_chat_rate_limit_is_enforced(monkeypatch) -> None:
    _enable_auth(monkeypatch, chat_rate_limit="2/minute")
    monkeypatch.setenv("CHAT_RATE_LIMIT_ENABLED", "true")
    get_settings.cache_clear()
    fake_db = _FakeAsyncSession()
    fake_agent = _FakeTravelTomAgent(
        assistant_message="Limited chat response.",
        state={
            "state_version": "v1",
            "session_id": "session-auth",
            "user_id": None,
            "constraints": {},
            "preferences": {"weighted_interests": {}, "dislikes": []},
            "entities": {"destinations": []},
            "shortlist": [],
            "itinerary": {"days": []},
            "status": "explore",
            "last_recommendation_version": "heuristic-v1",
            "last_message_at": "2026-03-07T19:15:00Z",
        },
    )

    app.dependency_overrides[get_db] = _override_db(fake_db)
    app.dependency_overrides[get_travel_tom_agent] = lambda: fake_agent
    app.dependency_overrides[require_authenticated_principal] = lambda: _principal()

    try:
        client = TestClient(app)
        first = client.post("/api/v1/chat", json=_chat_payload())
        second = client.post("/api/v1/chat", json=_chat_payload())
        third = client.post("/api/v1/chat", json=_chat_payload())
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "rate_limit_exceeded"
    details = third.json()["error"]["details"]
    assert details["source"] == "traveltom"
    assert isinstance(details["retry_after_seconds"], int)
    assert details["retry_after_seconds"] >= 0
    assert third.headers["Retry-After"] == str(details["retry_after_seconds"])


def test_local_environment_disables_chat_rate_limit_by_default(monkeypatch) -> None:
    _enable_auth(monkeypatch, chat_rate_limit="1/minute")
    monkeypatch.delenv("CHAT_RATE_LIMIT_ENABLED", raising=False)
    get_settings.cache_clear()
    fake_db = _FakeAsyncSession()
    fake_agent = _FakeTravelTomAgent(
        assistant_message="Local development response.",
        state={
            "state_version": "v1",
            "session_id": "session-auth",
            "user_id": None,
            "constraints": {},
            "preferences": {"weighted_interests": {}, "dislikes": []},
            "entities": {"destinations": []},
            "shortlist": [],
            "itinerary": {"days": []},
            "status": "explore",
            "last_recommendation_version": "heuristic-v1",
            "last_message_at": "2026-03-07T19:15:00Z",
        },
    )

    app.dependency_overrides[get_db] = _override_db(fake_db)
    app.dependency_overrides[get_travel_tom_agent] = lambda: fake_agent
    app.dependency_overrides[require_authenticated_principal] = lambda: _principal()

    try:
        client = TestClient(app)
        first = client.post("/api/v1/chat", json=_chat_payload())
        second = client.post("/api/v1/chat", json=_chat_payload())
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 200
