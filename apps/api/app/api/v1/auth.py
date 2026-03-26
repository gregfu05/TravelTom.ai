"""Authentication routes for local email/password accounts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.core.security import require_authenticated_principal
from app.db.session import get_db
from app.schemas.api.auth import (
    AuthTokenResponse,
    AuthUserResponse,
    LoginRequest,
    SignupRequest,
)
from app.schemas.auth import (
    AuthenticatedPrincipal,
    AuthSessionResult,
    LocalAccessTokenClaims,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth")


def get_auth_service(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    """Return the auth service bound to the request-scoped DB session."""

    return AuthService(session=db, settings=settings)


@router.post(
    "/signup",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup(
    request: SignupRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthTokenResponse:
    """Create a local account and return a bearer token."""

    result = await auth_service.signup(email=request.email, password=request.password)
    return _to_auth_response(result)


@router.post("/login", response_model=AuthTokenResponse)
async def login(
    request: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthTokenResponse:
    """Authenticate a local account and return a bearer token."""

    result = await auth_service.login(email=request.email, password=request.password)
    return _to_auth_response(result)


@router.get("/me", response_model=AuthUserResponse)
async def current_user(
    principal: AuthenticatedPrincipal | None = Depends(require_authenticated_principal),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthUserResponse:
    """Return the current authenticated user."""

    if principal is None:
        raise ApiError(
            status_code=401,
            code="unauthorized",
            message="Missing bearer token",
        )

    user = await auth_service.get_current_user(principal)
    return AuthUserResponse(id=str(user.id), email=user.email or "")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    principal: AuthenticatedPrincipal | None = Depends(require_authenticated_principal),
    auth_service: AuthService = Depends(get_auth_service),
) -> Response:
    """Revoke the current local bearer token."""

    if principal is None:
        raise ApiError(
            status_code=401,
            code="unauthorized",
            message="Missing bearer token",
        )

    claims = getattr(request.state, "local_auth_claims", None)
    if not isinstance(claims, LocalAccessTokenClaims):
        raise ApiError(
            status_code=400,
            code="bad_request",
            message="Logout is only available for local auth sessions",
        )

    await auth_service.logout_local_session(claims=claims)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _to_auth_response(result: AuthSessionResult) -> AuthTokenResponse:
    """Map an auth service result to the public API response contract."""

    return AuthTokenResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        idle_timeout_in=result.idle_timeout_in,
        user=AuthUserResponse(id=result.user_id, email=result.email),
    )
