"""Tests for local email/password authentication endpoints and bearer auth."""

from __future__ import annotations

import uuid
from typing import Any

from app.api.v1.chat import get_orchestrator_service
from app.core.config import get_settings
from app.core.local_auth import (
    LOCAL_AUTH_ISSUER,
    create_access_token,
    decode_access_token,
    hash_password,
)
from app.core.security import get_azure_b2c_scheme, get_chat_rate_limiter
from app.db.models.session import Session
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.services.chat_persistence import session_pk
from app.services.orchestrator.schemas import OrchestratorResponse
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
        self._users_by_email: dict[str, User] = {}
        self._users_by_identity: dict[tuple[str, str], User] = {}
        if existing_user is not None:
            self._index_user(existing_user)

    async def execute(self, statement: Any) -> _FakeResult:
        entity = statement.column_descriptions[0].get("entity")
        if entity is Session:
            return _FakeResult(self.existing_session)
        if entity is User:
            filters = self._filters(statement)
            if "email" in filters:
                return _FakeResult(self._users_by_email.get(str(filters["email"])))
            if "auth_issuer" in filters and "external_subject" in filters:
                key = (
                    str(filters["auth_issuer"]),
                    str(filters["external_subject"]),
                )
                return _FakeResult(self._users_by_identity.get(key))
            return _FakeResult(self.existing_user)
        return _FakeResult(None)

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        if isinstance(obj, Session):
            self.existing_session = obj
        if isinstance(obj, User):
            self.existing_user = obj
            self._index_user(obj)

    async def commit(self) -> None:
        self.committed = True

    async def flush(self) -> None:
        self.flushed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    @staticmethod
    def _filters(statement: Any) -> dict[str, Any]:
        filters: dict[str, Any] = {}
        for criterion in getattr(statement, "_where_criteria", ()):
            left = getattr(criterion, "left", None)
            right = getattr(criterion, "right", None)
            key = getattr(left, "key", None)
            value = getattr(right, "value", None)
            if value is None and hasattr(right, "effective_value"):
                value = right.effective_value
            if key is not None:
                filters[str(key)] = value
        return filters

    def _index_user(self, user: User) -> None:
        if user.email:
            self._users_by_email[user.email] = user
        if user.auth_issuer and user.external_subject:
            self._users_by_identity[(user.auth_issuer, user.external_subject)] = user


def _override_db(fake_db: _FakeAsyncSession):
    async def _dependency():
        yield fake_db

    return _dependency


class _FakeOrchestratorService:
    def __init__(
        self,
        *,
        assistant_message: str,
        state: dict[str, Any],
    ) -> None:
        self.assistant_message = assistant_message
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
                "recommendations": [],
                "itinerary": {"days": []},
                "state": self.state,
            }
        )


def _enable_local_auth(monkeypatch, *, auth_enabled: bool = False) -> str:
    secret = "traveltom-local-secret"
    monkeypatch.setenv("LOCAL_AUTH_TOKEN_SECRET", secret)
    monkeypatch.setenv("LOCAL_AUTH_TOKEN_TTL_SECONDS", "3600")
    monkeypatch.setenv("AUTH_ENABLED", "true" if auth_enabled else "false")
    get_settings.cache_clear()
    get_azure_b2c_scheme.cache_clear()
    get_chat_rate_limiter().reset()
    return secret


def test_signup_creates_local_account_and_returns_bearer_token(monkeypatch) -> None:
    secret = _enable_local_auth(monkeypatch)
    fake_db = _FakeAsyncSession()
    app.dependency_overrides[get_db] = _override_db(fake_db)

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/signup",
            json={
                "email": "Traveler@Example.com",
                "password": "VeryStrong123",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    assert body["user"]["email"] == "traveler@example.com"
    assert fake_db.existing_user is not None
    assert fake_db.existing_user.password_hash is not None
    assert fake_db.existing_user.password_hash != "VeryStrong123"
    claims = decode_access_token(token=body["access_token"], secret=secret)
    assert claims.sub == str(fake_db.existing_user.id)
    assert claims.email == "traveler@example.com"


def test_signup_rejects_duplicate_email(monkeypatch) -> None:
    _enable_local_auth(monkeypatch)
    existing_user = User(
        id=uuid.uuid4(),
        auth_issuer=LOCAL_AUTH_ISSUER,
        external_subject="existing-subject",
        email="traveler@example.com",
        password_hash=hash_password("VeryStrong123"),
    )
    fake_db = _FakeAsyncSession(existing_user=existing_user)
    app.dependency_overrides[get_db] = _override_db(fake_db)

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/signup",
            json={
                "email": "traveler@example.com",
                "password": "VeryStrong123",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert (
        response.json()["error"]["message"]
        == "An account with that email already exists"
    )


def test_login_returns_bearer_token_for_existing_local_user(monkeypatch) -> None:
    secret = _enable_local_auth(monkeypatch)
    existing_user = User(
        id=uuid.uuid4(),
        auth_issuer=LOCAL_AUTH_ISSUER,
        external_subject="existing-subject",
        email="traveler@example.com",
        password_hash=hash_password("VeryStrong123"),
    )
    fake_db = _FakeAsyncSession(existing_user=existing_user)
    app.dependency_overrides[get_db] = _override_db(fake_db)

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "traveler@example.com",
                "password": "VeryStrong123",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["id"] == str(existing_user.id)
    claims = decode_access_token(token=body["access_token"], secret=secret)
    assert claims.sub == str(existing_user.id)


def test_login_rejects_invalid_password(monkeypatch) -> None:
    _enable_local_auth(monkeypatch)
    existing_user = User(
        id=uuid.uuid4(),
        auth_issuer=LOCAL_AUTH_ISSUER,
        external_subject="existing-subject",
        email="traveler@example.com",
        password_hash=hash_password("VeryStrong123"),
    )
    fake_db = _FakeAsyncSession(existing_user=existing_user)
    app.dependency_overrides[get_db] = _override_db(fake_db)

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "traveler@example.com",
                "password": "WrongPassword",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password"


def test_auth_me_returns_current_user_for_local_token(monkeypatch) -> None:
    secret = _enable_local_auth(monkeypatch)
    existing_user = User(
        id=uuid.uuid4(),
        auth_issuer=LOCAL_AUTH_ISSUER,
        external_subject="existing-subject",
        email="traveler@example.com",
        password_hash=hash_password("VeryStrong123"),
    )
    fake_db = _FakeAsyncSession(existing_user=existing_user)
    token = create_access_token(
        subject="existing-subject",
        email=existing_user.email or "",
        secret=secret,
        ttl_seconds=3600,
    )
    app.dependency_overrides[get_db] = _override_db(fake_db)

    try:
        client = TestClient(app)
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "id": str(existing_user.id),
        "email": "traveler@example.com",
    }


def test_chat_accepts_local_bearer_token_when_auth_is_enabled(monkeypatch) -> None:
    secret = _enable_local_auth(monkeypatch, auth_enabled=True)
    existing_user = User(
        id=uuid.uuid4(),
        auth_issuer=LOCAL_AUTH_ISSUER,
        external_subject="local-chat-subject",
        email="traveler@example.com",
        password_hash=hash_password("VeryStrong123"),
    )
    fake_db = _FakeAsyncSession(existing_user=existing_user)
    fake_orchestrator = _FakeOrchestratorService(
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
    token = create_access_token(
        subject="local-chat-subject",
        email=existing_user.email or "",
        secret=secret,
        ttl_seconds=3600,
    )

    app.dependency_overrides[get_db] = _override_db(fake_db)
    app.dependency_overrides[get_orchestrator_service] = lambda: fake_orchestrator

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "session_id": "session-auth",
                "message_id": "msg-auth-001",
                "message": "plan a city break",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert fake_db.existing_session is not None
    assert fake_db.existing_session.id == session_pk("session-auth")
    assert fake_db.existing_session.user_id == existing_user.id
