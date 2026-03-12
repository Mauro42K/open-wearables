"""Resolve the authenticated user context."""

from datetime import datetime, timezone
from typing import Any, Mapping

from fastmcp.server.dependencies import get_access_token

from app.config import settings
from app.schemas.auth import AuthenticatedUser


class SessionResolverError(Exception):
    """Raised when no authenticated user can be resolved."""


def _from_session_payload(payload: Mapping[str, Any]) -> AuthenticatedUser:
    """Build an authenticated user from session payload."""
    return AuthenticatedUser.model_validate(payload)


def resolve_authenticated_user_from_access_token() -> AuthenticatedUser:
    """Resolve the authenticated user from a FastMCP bearer token."""
    access_token = get_access_token()
    if access_token is None:
        raise SessionResolverError

    claims = access_token.claims or {}
    google_user_id = claims.get("sub")
    google_email = claims.get("email")
    if not google_user_id or not google_email:
        raise SessionResolverError

    now = datetime.now(timezone.utc)
    return AuthenticatedUser(
        google_user_id=str(google_user_id),
        google_email=str(google_email),
        session_id=f"bearer-{access_token.client_id}",
        authenticated_at=now,
    )


def resolve_authenticated_user_from_headers(headers: Mapping[str, str]) -> AuthenticatedUser:
    """Development-only fallback for local testing."""
    google_user_id = headers.get("x-debug-google-user-id")
    google_email = headers.get("x-debug-google-email")

    if settings.allow_debug_session_headers and google_user_id and google_email:
        now = datetime.now(timezone.utc)
        return AuthenticatedUser(
            google_user_id=google_user_id,
            google_email=google_email,
            session_id=f"debug-{google_user_id}",
            authenticated_at=now,
        )

    raise SessionResolverError


def resolve_authenticated_user_from_request(request: Any) -> AuthenticatedUser:
    """Resolve the authenticated user from bearer token, session, or debug headers."""
    try:
        return resolve_authenticated_user_from_access_token()
    except (RuntimeError, SessionResolverError):
        pass

    session = getattr(request, "session", None) or {}
    session_payload = session.get("authenticated_user")
    if isinstance(session_payload, Mapping):
        try:
            return _from_session_payload(session_payload)
        except Exception as exc:  # noqa: BLE001
            raise SessionResolverError from exc

    headers = getattr(request, "headers", {}) or {}
    return resolve_authenticated_user_from_headers(headers)


async def resolve_authenticated_user(request: Any) -> AuthenticatedUser:
    """Resolve the authenticated user from the current request."""
    return resolve_authenticated_user_from_request(request)
