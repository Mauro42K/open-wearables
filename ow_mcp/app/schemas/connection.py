"""Connection response schemas."""

from datetime import datetime

from pydantic import BaseModel


class ConnectionView(BaseModel):
    """Public connection shape."""

    google_email: str
    status: str
    api_key_masked: str | None
    validated_at: datetime | None


class ValidateConnectionRequest(BaseModel):
    """Payload for validating and storing an ow-api key."""

    api_key: str


class ValidateConnectionResponse(BaseModel):
    """Successful validation response."""

    status: str
    connection: ConnectionView


class DisconnectResponse(BaseModel):
    """Successful disconnect response."""

    status: str

