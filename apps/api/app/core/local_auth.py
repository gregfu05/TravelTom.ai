"""Local auth helpers for email normalization and TravelTom-issued JWTs."""

from __future__ import annotations

import re
import uuid

import jwt
from fastapi_users.password import PasswordHelper
from jwt import ExpiredSignatureError, InvalidTokenError

from app.schemas.auth import LocalAccessTokenClaims

LOCAL_AUTH_ISSUER = "traveltom-local"
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PASSWORD_HELPER = PasswordHelper()


class LocalAuthError(ValueError):
    """Base error for local authentication helpers."""


class InvalidLocalTokenError(LocalAuthError):
    """Raised when a local bearer token cannot be trusted."""


class NotLocalTokenError(LocalAuthError):
    """Raised when a bearer token is not a TravelTom local-auth token."""


def normalize_email(email: str) -> str:
    """Normalize user emails to a canonical lookup form."""

    return email.strip().lower()


def is_valid_email(email: str) -> bool:
    """Return whether the email has a minimally valid structure."""

    return bool(_EMAIL_PATTERN.fullmatch(normalize_email(email)))


def hash_password(password: str) -> str:
    """Hash a password using the configured library-backed password helper."""

    return _PASSWORD_HELPER.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    """Return whether the password matches the stored library-managed hash."""

    verified, _ = _PASSWORD_HELPER.verify_and_update(password, stored_hash)
    return verified


def create_access_token(
    *,
    subject: str,
    email: str,
    secret: str,
    ttl_seconds: int,
    token_id: str | None = None,
    issued_at: int | None = None,
) -> str:
    """Return a signed bearer token for a local-authenticated user."""

    current_issued_at = issued_at if issued_at is not None else _utc_timestamp()
    claims = LocalAccessTokenClaims(
        jti=token_id or str(uuid.uuid4()),
        sub=subject,
        iss=LOCAL_AUTH_ISSUER,
        email=normalize_email(email),
        iat=current_issued_at,
        exp=current_issued_at + ttl_seconds,
    )
    return jwt.encode(
        claims.model_dump(mode="json"),
        secret,
        algorithm="HS256",
    )


def decode_access_token(*, token: str, secret: str) -> LocalAccessTokenClaims:
    """Validate and decode a local bearer token."""

    try:
        unverified_payload = jwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": False},
        )
    except InvalidTokenError as exc:
        raise InvalidLocalTokenError("Invalid bearer token") from exc

    issuer = unverified_payload.get("iss")
    if issuer != LOCAL_AUTH_ISSUER:
        raise NotLocalTokenError("Bearer token issuer is not local auth")

    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        claims = LocalAccessTokenClaims.model_validate(payload)
    except ExpiredSignatureError as exc:
        raise InvalidLocalTokenError("Expired bearer token") from exc
    except (InvalidTokenError, ValueError) as exc:
        raise InvalidLocalTokenError("Invalid bearer token") from exc
    return claims


def _utc_timestamp() -> int:
    from time import time

    return int(time())
