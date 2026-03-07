"""Local email/password authentication helpers."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from typing import Any

from app.schemas.auth import LocalAccessTokenClaims

LOCAL_AUTH_ISSUER = "traveltom-local"
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 64
_SCRYPT_SALT_BYTES = 16
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


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
    """Hash a password with ``scrypt`` and return a serialized digest."""

    salt = os.urandom(_SCRYPT_SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
    )
    return (
        "scrypt"
        f"${_SCRYPT_N}"
        f"${_SCRYPT_R}"
        f"${_SCRYPT_P}"
        f"${base64.urlsafe_b64encode(salt).decode('ascii')}"
        f"${base64.urlsafe_b64encode(digest).decode('ascii')}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Return whether the password matches the serialized ``scrypt`` hash."""

    try:
        algorithm, n, r, p, salt_b64, digest_b64 = stored_hash.split("$", maxsplit=5)
    except ValueError:
        return False

    if algorithm != "scrypt":
        return False

    try:
        salt = base64.urlsafe_b64decode(_with_padding(salt_b64))
        expected_digest = base64.urlsafe_b64decode(_with_padding(digest_b64))
        computed_digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected_digest),
        )
    except (ValueError, TypeError, binascii.Error):
        return False

    return secrets.compare_digest(computed_digest, expected_digest)


def create_access_token(
    *,
    subject: str,
    email: str,
    secret: str,
    ttl_seconds: int,
) -> str:
    """Return a signed bearer token for a local-authenticated user."""

    issued_at = int(time.time())
    claims = LocalAccessTokenClaims(
        sub=subject,
        iss=LOCAL_AUTH_ISSUER,
        email=normalize_email(email),
        iat=issued_at,
        exp=issued_at + ttl_seconds,
    )
    header_segment = _urlsafe_json({"alg": "HS256", "typ": "JWT"})
    payload_segment = _urlsafe_json(claims.model_dump(mode="json"))
    signing_input = f"{header_segment}.{payload_segment}"
    signature = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_urlsafe_b64encode(signature)}"


def decode_access_token(*, token: str, secret: str) -> LocalAccessTokenClaims:
    """Validate and decode a local bearer token."""

    try:
        _, payload_segment, signature_segment = token.split(".", maxsplit=2)
    except ValueError as exc:
        raise InvalidLocalTokenError("Invalid bearer token") from exc

    payload = _decode_segment(payload_segment)
    issuer = payload.get("iss")
    if issuer != LOCAL_AUTH_ISSUER:
        raise NotLocalTokenError("Bearer token issuer is not local auth")

    signing_input = ".".join(token.split(".")[:2])
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    actual_signature = _decode_b64(signature_segment)
    if not secrets.compare_digest(expected_signature, actual_signature):
        raise InvalidLocalTokenError("Invalid bearer token")

    try:
        claims = LocalAccessTokenClaims.model_validate(payload)
    except Exception as exc:  # pragma: no cover - pydantic error shape is not important
        raise InvalidLocalTokenError("Invalid bearer token") from exc

    if claims.exp <= int(time.time()):
        raise InvalidLocalTokenError("Expired bearer token")
    return claims


def _urlsafe_json(value: dict[str, Any]) -> str:
    return _urlsafe_b64encode(
        json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )


def _urlsafe_b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_segment(segment: str) -> dict[str, Any]:
    try:
        return json.loads(_decode_b64(segment))
    except (json.JSONDecodeError, UnicodeDecodeError, binascii.Error) as exc:
        raise InvalidLocalTokenError("Invalid bearer token") from exc


def _decode_b64(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(_with_padding(value))
    except binascii.Error as exc:
        raise InvalidLocalTokenError("Invalid bearer token") from exc


def _with_padding(value: str) -> str:
    return value + "=" * (-len(value) % 4)
