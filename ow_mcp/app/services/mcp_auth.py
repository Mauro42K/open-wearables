"""FastMCP OAuth provider configuration for remote clients."""

from fastmcp.server.auth.providers.google import GoogleProvider

from app.config import settings

MCP_OAUTH_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


def create_mcp_auth_provider() -> GoogleProvider | None:
    """Build the FastMCP OAuth provider when Google OAuth is configured."""
    client_id = settings.google_client_id
    client_secret = settings.google_client_secret

    if not client_id or client_secret is None:
        return None

    base_url = f"{settings.app_base_url.rstrip('/')}/mcp"
    return GoogleProvider(
        client_id=client_id,
        client_secret=client_secret.get_secret_value(),
        base_url=base_url,
        issuer_url=base_url,
        required_scopes=MCP_OAUTH_SCOPES,
        timeout_seconds=int(settings.request_timeout),
        jwt_signing_key=settings.session_secret_key.get_secret_value(),
    )
