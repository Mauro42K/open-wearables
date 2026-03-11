"""Guard logic for remote MCP tool execution."""

from dataclasses import dataclass

from fastmcp.server.dependencies import get_http_request

from app.database import SessionLocal
from app.repositories.connection_repository import ConnectionRepository
from app.schemas.auth import AuthenticatedUser
from app.services.backend_client import InvalidApiKeyError, UpstreamUnavailableError, create_ow_api_client
from app.services.crypto_service import CryptoError, crypto_service
from app.services.session_resolver import SessionResolverError, resolve_authenticated_user_from_request


@dataclass
class ToolExecutionContext:
    """Resolved context for an authenticated MCP tool execution."""

    authenticated_user: AuthenticatedUser
    api_client: object


def _error(error: str, message: str) -> dict[str, str]:
    return {"error": error, "message": message}


async def resolve_tool_execution_context() -> ToolExecutionContext | dict[str, str]:
    """
    Resolve the authenticated user and request-scoped ow-api client.

    Returns either a fully resolved execution context or a standard error payload.
    """
    try:
        request = get_http_request()
        authenticated_user = resolve_authenticated_user_from_request(request)
    except (RuntimeError, SessionResolverError):
        return _error("unauthorized", "Authentication required.")

    db = SessionLocal()
    try:
        repository = ConnectionRepository(db)
        connection = repository.get_by_google_user_id(authenticated_user.google_user_id)
        if connection is None or connection.status == "not_connected":
            return _error(
                "account_not_connected",
                "Connect a valid Open Wearables API key to use this MCP server.",
            )
        if connection.status == "invalid_key":
            return _error(
                "connection_invalid",
                "Your stored Open Wearables API key is no longer valid. Reconnect your account.",
            )
        if not connection.encrypted_api_key:
            return _error(
                "account_not_connected",
                "Connect a valid Open Wearables API key to use this MCP server.",
            )

        try:
            api_key = crypto_service.decrypt_api_key(connection.encrypted_api_key)
        except CryptoError:
            return _error("unexpected_error", "An unexpected error occurred.")

        api_client = create_ow_api_client(api_key)
        return ToolExecutionContext(authenticated_user=authenticated_user, api_client=api_client)
    finally:
        db.close()


async def execute_guarded_tool(operation) -> dict:
    """
    Execute a tool operation behind the standard runtime guard.

    The provided operation receives a request-scoped authenticated client.
    """
    context_or_error = await resolve_tool_execution_context()
    if isinstance(context_or_error, dict):
        return context_or_error

    context = context_or_error

    try:
        return await operation(context)
    except InvalidApiKeyError:
        db = SessionLocal()
        try:
            repository = ConnectionRepository(db)
            repository.mark_connection_invalid(
                context.authenticated_user.google_user_id,
                "invalid_api_key",
            )
        finally:
            db.close()
        return _error(
            "connection_invalid",
            "Your stored Open Wearables API key is no longer valid. Reconnect your account.",
        )
    except UpstreamUnavailableError:
        return _error(
            "upstream_unreachable",
            "Open Wearables API is temporarily unavailable. Try again later.",
        )
    except Exception:  # noqa: BLE001
        return _error("unexpected_error", "An unexpected error occurred.")
