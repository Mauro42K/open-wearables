"""Persistence helpers for connections."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.connection import Connection


class ConnectionRepository:
    """Repository for user connection state."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_google_user_id(self, google_user_id: str) -> Connection | None:
        """Fetch a connection by Google user id."""
        return self.db.get(Connection, google_user_id)

    def get_active_connection(self, google_user_id: str) -> Connection | None:
        """Fetch a valid active connection."""
        connection = self.get_by_google_user_id(google_user_id)
        if connection is None:
            return None
        if connection.status != "connected":
            return None
        if not connection.encrypted_api_key:
            return None
        return connection

    def save_validated_connection(
        self,
        google_user_id: str,
        google_email: str,
        encrypted_api_key: str,
        api_key_masked: str,
        validated_at: datetime,
    ) -> Connection:
        """Persist a validated connection."""
        connection = self.get_by_google_user_id(google_user_id)
        if connection is None:
            connection = Connection(
                google_user_id=google_user_id,
                google_email=google_email,
                created_at=validated_at,
            )
            self.db.add(connection)

        connection.google_email = google_email
        connection.status = "connected"
        connection.encrypted_api_key = encrypted_api_key
        connection.api_key_masked = api_key_masked
        connection.validated_at = validated_at
        connection.updated_at = validated_at
        connection.disconnected_at = None
        connection.last_error_code = None
        connection.last_error_at = None
        self.db.commit()
        self.db.refresh(connection)
        return connection

    def mark_connection_invalid(self, google_user_id: str, error_code: str) -> Connection | None:
        """Mark a stored connection as invalid."""
        connection = self.get_by_google_user_id(google_user_id)
        if connection is None:
            return None

        now = datetime.now(timezone.utc)
        connection.status = "invalid_key"
        connection.updated_at = now
        connection.last_error_code = error_code
        connection.last_error_at = now
        self.db.commit()
        self.db.refresh(connection)
        return connection

    def delete_connection(self, google_user_id: str) -> bool:
        """Delete stored secret material while preserving a disconnected record."""
        connection = self.get_by_google_user_id(google_user_id)
        if connection is None:
            return False

        now = datetime.now(timezone.utc)
        connection.status = "not_connected"
        connection.encrypted_api_key = None
        connection.api_key_masked = None
        connection.updated_at = now
        connection.disconnected_at = now
        connection.last_error_code = None
        connection.last_error_at = None
        self.db.commit()
        return True

