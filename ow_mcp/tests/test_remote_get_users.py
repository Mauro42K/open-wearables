from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone

from pydantic import SecretStr


TEST_DB = Path("/Users/mauro/open-wearables/ow_mcp/test_ow_mcp_users.db")
if TEST_DB.exists():
    TEST_DB.unlink()


import app.config as app_config  # noqa: E402

app_config.settings.database_url = f"sqlite:///{TEST_DB}"
app_config.settings.allow_debug_session_headers = True
app_config.settings.encryption_key = SecretStr("test-encryption-key")

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.repositories.connection_repository import ConnectionRepository  # noqa: E402
from app.services.backend_client import InvalidApiKeyError  # noqa: E402
import app.services.tool_execution_guard as tool_execution_guard  # noqa: E402
from app.tools.users import get_users  # noqa: E402


Base.metadata.create_all(bind=engine)


def _store_connection() -> None:
    db = SessionLocal()
    try:
        repository = ConnectionRepository(db)
        existing = repository.get_by_google_user_id("google-user-1")
        if existing is not None:
            db.delete(existing)
            db.commit()
        repository.save_validated_connection(
            google_user_id="google-user-1",
            google_email="mauro@example.com",
            encrypted_api_key=tool_execution_guard.crypto_service.encrypt_api_key("sk-test-valid-f3f4"),
            api_key_masked="sk-****f3f4",
            validated_at=datetime.now(timezone.utc),
        )
    finally:
        db.close()


def _fake_request() -> SimpleNamespace:
    return SimpleNamespace(
        headers={
            "x-debug-google-user-id": "google-user-1",
            "x-debug-google-email": "mauro@example.com",
        }
    )


async def _run_get_users(payload: dict) -> dict:
    return await get_users(**payload)


def test_remote_get_users_returns_users(monkeypatch) -> None:
    _store_connection()
    monkeypatch.setattr(tool_execution_guard, "get_http_request", _fake_request)

    class FakeClient:
        async def get_users(self, *, search: str | None = None, limit: int = 10) -> dict:
            assert search == "tim"
            assert limit == 5
            return {
                "items": [
                    {
                        "id": "user-1",
                        "first_name": "Timothy",
                        "last_name": "Duncan",
                        "email": "tim@example.com",
                    }
                ],
                "total": 1,
            }

    monkeypatch.setattr(tool_execution_guard, "create_ow_api_client", lambda api_key: FakeClient())

    import asyncio

    payload = asyncio.run(_run_get_users({"search": "tim", "limit": 5}))
    assert payload["total"] == 1
    assert payload["users"][0]["email"] == "tim@example.com"


def test_remote_get_users_requires_connected_account(monkeypatch) -> None:
    db = SessionLocal()
    try:
        repository = ConnectionRepository(db)
        existing = repository.get_by_google_user_id("google-user-1")
        if existing is not None:
            db.delete(existing)
            db.commit()
    finally:
        db.close()

    monkeypatch.setattr(tool_execution_guard, "get_http_request", _fake_request)

    import asyncio

    payload = asyncio.run(_run_get_users({}))
    assert payload["error"] == "account_not_connected"


def test_remote_get_users_marks_invalid_connection(monkeypatch) -> None:
    _store_connection()
    monkeypatch.setattr(tool_execution_guard, "get_http_request", _fake_request)

    class FakeClient:
        async def get_users(self, *, search: str | None = None, limit: int = 10) -> dict:
            raise InvalidApiKeyError

    monkeypatch.setattr(tool_execution_guard, "create_ow_api_client", lambda api_key: FakeClient())

    import asyncio

    payload = asyncio.run(_run_get_users({}))
    assert payload["error"] == "connection_invalid"

    db = SessionLocal()
    try:
        repository = ConnectionRepository(db)
        connection = repository.get_by_google_user_id("google-user-1")
        assert connection is not None
        assert connection.status == "invalid_key"
        assert connection.last_error_code == "invalid_api_key"
    finally:
        db.close()
