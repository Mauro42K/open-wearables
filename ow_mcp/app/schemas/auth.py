"""Authenticated session context."""

from datetime import datetime

from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    """Minimal authenticated session context."""

    google_user_id: str
    google_email: str
    session_id: str
    authenticated_at: datetime

