"""Shared API dependencies."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import AuthenticatedUser
from app.schemas.errors import ErrorResponse
from app.services.session_resolver import SessionResolverError, resolve_authenticated_user


DbSession = Annotated[Session, Depends(get_db)]


async def get_authenticated_user(
    request: Request,
) -> AuthenticatedUser:
    """Resolve the authenticated user or raise the standard unauthorized error."""
    try:
        return await resolve_authenticated_user(request)
    except SessionResolverError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse(error="unauthorized", message="Authentication required.").model_dump(),
        ) from exc


AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
