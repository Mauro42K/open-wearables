"""Error payloads."""

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard API error."""

    error: str
    message: str

