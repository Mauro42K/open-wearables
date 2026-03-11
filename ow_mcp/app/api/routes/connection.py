"""Connection management endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import AuthenticatedUserDep, DbSession
from app.repositories.connection_repository import ConnectionRepository
from app.schemas.connection import (
    ConnectionView,
    DisconnectResponse,
    ValidateConnectionRequest,
    ValidateConnectionResponse,
)
from app.schemas.errors import ErrorResponse
from app.services.backend_client import InvalidApiKeyError, UpstreamUnavailableError, create_ow_api_client
from app.services.crypto_service import CryptoError, crypto_service

router = APIRouter(prefix="/api/connection", tags=["connection"])


@router.post(
    "/validate",
    response_model=ValidateConnectionResponse,
    responses={
        401: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def validate_connection(
    payload: ValidateConnectionRequest,
    authenticated_user: AuthenticatedUserDep,
    db: DbSession,
) -> ValidateConnectionResponse:
    """Validate and store an ow-api key for the authenticated user."""
    if not payload.api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(error="invalid_api_key", message="A non-empty API key is required.").model_dump(),
        )

    repository = ConnectionRepository(db)
    validation_client = create_ow_api_client(payload.api_key)

    try:
        await validation_client.validate_api_key()
    except InvalidApiKeyError:
        repository.mark_connection_invalid(authenticated_user.google_user_id, "invalid_api_key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse(error="invalid_api_key", message="The provided API key is invalid.").model_dump(),
        ) from None
    except UpstreamUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ErrorResponse(
                error="upstream_unreachable",
                message="Open Wearables API is temporarily unavailable. Try again later.",
            ).model_dump(),
        ) from None

    try:
        encrypted_api_key = crypto_service.encrypt_api_key(payload.api_key)
    except CryptoError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(error="unexpected_error", message="An unexpected error occurred.").model_dump(),
        ) from None

    validated_at = datetime.now(timezone.utc)
    connection = repository.save_validated_connection(
        google_user_id=authenticated_user.google_user_id,
        google_email=authenticated_user.google_email,
        encrypted_api_key=encrypted_api_key,
        api_key_masked=crypto_service.mask_api_key(payload.api_key),
        validated_at=validated_at,
    )

    return ValidateConnectionResponse(
        status="connected",
        connection=ConnectionView(
            google_email=connection.google_email,
            status=connection.status,
            api_key_masked=connection.api_key_masked,
            validated_at=connection.validated_at,
        ),
    )


@router.post(
    "/disconnect",
    response_model=DisconnectResponse,
    responses={401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def disconnect_connection(
    authenticated_user: AuthenticatedUserDep,
    db: DbSession,
) -> DisconnectResponse:
    """Delete the stored ow-api key for the authenticated user."""
    repository = ConnectionRepository(db)
    repository.delete_connection(authenticated_user.google_user_id)
    return DisconnectResponse(status="not_connected")
