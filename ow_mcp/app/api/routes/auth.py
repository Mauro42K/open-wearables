"""Google OAuth routes."""

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.dependencies import AuthenticatedUserDep, DbSession
from app.repositories.connection_repository import ConnectionRepository
from app.schemas.errors import ErrorResponse
from app.services.google_oauth import (
    OAuthAuthenticationError,
    OAuthConfigurationError,
    begin_google_oauth,
    complete_google_oauth,
)

router = APIRouter(tags=["auth"])


@router.get("/auth/google/start", name="google_oauth_start")
async def google_oauth_start(request: Request):
    """Start Google OAuth login."""
    try:
        return await begin_google_oauth(request)
    except OAuthConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(error="unexpected_error", message="Google OAuth is not configured.").model_dump(),
        ) from exc


@router.get("/auth/google/callback", name="google_oauth_callback")
async def google_oauth_callback(request: Request, db: DbSession):
    """Complete Google OAuth login and persist the session."""
    try:
        authenticated_user = await complete_google_oauth(request)
    except OAuthConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(error="unexpected_error", message="Google OAuth is not configured.").model_dump(),
        ) from exc
    except OAuthAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse(error="unauthorized", message="Authentication required.").model_dump(),
        ) from exc

    request.session["authenticated_user"] = authenticated_user.model_dump(mode="json")

    repository = ConnectionRepository(db)
    connection = repository.get_active_connection(authenticated_user.google_user_id)
    redirect_target = "/status" if connection is not None else "/connect"
    return RedirectResponse(url=redirect_target, status_code=status.HTTP_302_FOUND)


@router.post("/auth/logout")
async def logout(request: Request) -> JSONResponse:
    """Clear the authenticated session."""
    request.session.pop("authenticated_user", None)
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "signed_out"})


@router.get("/auth/session")
async def auth_session(
    authenticated_user: AuthenticatedUserDep,
    db: DbSession,
) -> JSONResponse:
    """Return the current authenticated session and connection status."""
    repository = ConnectionRepository(db)
    connection = repository.get_by_google_user_id(authenticated_user.google_user_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "authenticated_user": authenticated_user.model_dump(mode="json"),
            "connection": {
                "status": connection.status if connection is not None else "not_connected",
                "api_key_masked": connection.api_key_masked if connection is not None else None,
                "validated_at": connection.validated_at.isoformat() if connection and connection.validated_at else None,
            },
        },
    )
