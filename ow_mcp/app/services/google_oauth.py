"""Google OAuth helpers."""

from datetime import datetime, timezone

from authlib.integrations.base_client import OAuthError
from authlib.integrations.starlette_client import OAuth
from fastapi import Request
from starlette.responses import RedirectResponse

from app.config import settings
from app.schemas.auth import AuthenticatedUser


class OAuthConfigurationError(Exception):
    """Raised when Google OAuth is not configured."""


class OAuthAuthenticationError(Exception):
    """Raised when Google OAuth login cannot be completed."""


def _require_google_config() -> tuple[str, str]:
    if not settings.google_client_id or settings.google_client_secret is None:
        raise OAuthConfigurationError
    return settings.google_client_id, settings.google_client_secret.get_secret_value()


def _build_oauth() -> OAuth:
    client_id, client_secret = _require_google_config()
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url=settings.google_metadata_url,
        client_kwargs={"scope": "openid email profile"},
    )
    return oauth


async def begin_google_oauth(request: Request) -> RedirectResponse:
    """Start Google OAuth."""
    oauth = _build_oauth()
    client = oauth.create_client("google")
    if client is None:
        raise OAuthConfigurationError
    redirect_uri = str(request.url_for("google_oauth_callback"))
    return await client.authorize_redirect(request, redirect_uri)


async def complete_google_oauth(request: Request) -> AuthenticatedUser:
    """Complete Google OAuth and return the authenticated session context."""
    oauth = _build_oauth()
    client = oauth.create_client("google")
    if client is None:
        raise OAuthConfigurationError

    try:
        token = await client.authorize_access_token(request)
    except OAuthError as exc:
        raise OAuthAuthenticationError from exc

    userinfo = token.get("userinfo") if isinstance(token, dict) else None
    if not isinstance(userinfo, dict):
        try:
            userinfo = dict(await client.userinfo(token=token))
        except Exception as exc:  # noqa: BLE001
            raise OAuthAuthenticationError from exc

    google_user_id = userinfo.get("sub") if isinstance(userinfo, dict) else None
    google_email = userinfo.get("email") if isinstance(userinfo, dict) else None
    if not google_user_id or not google_email:
        raise OAuthAuthenticationError

    return AuthenticatedUser(
        google_user_id=google_user_id,
        google_email=google_email,
        session_id=f"google-{google_user_id}",
        authenticated_at=datetime.now(timezone.utc),
    )
