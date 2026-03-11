from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone

from pydantic import SecretStr


TEST_DB = Path("/Users/mauro/open-wearables/ow_mcp/test_ow_mcp_timeseries.db")
if TEST_DB.exists():
    TEST_DB.unlink()


import app.config as app_config  # noqa: E402

app_config.settings.database_url = f"sqlite:///{TEST_DB}"
app_config.settings.allow_debug_session_headers = True
app_config.settings.encryption_key = SecretStr("test-encryption-key")

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.repositories.connection_repository import ConnectionRepository  # noqa: E402
import app.services.tool_execution_guard as tool_execution_guard  # noqa: E402
from app.tools.timeseries import get_timeseries  # noqa: E402


Base.metadata.create_all(bind=engine)


def _fake_request() -> SimpleNamespace:
    return SimpleNamespace(
        headers={
            "x-debug-google-user-id": "google-user-timeseries",
            "x-debug-google-email": "mauro@example.com",
        }
    )


def _store_connection() -> None:
    db = SessionLocal()
    try:
        repository = ConnectionRepository(db)
        existing = repository.get_by_google_user_id("google-user-timeseries")
        if existing is not None:
            db.delete(existing)
            db.commit()
        repository.save_validated_connection(
            google_user_id="google-user-timeseries",
            google_email="mauro@example.com",
            encrypted_api_key=tool_execution_guard.crypto_service.encrypt_api_key("sk-test-valid-f3f4"),
            api_key_masked="sk-****f3f4",
            validated_at=datetime.now(timezone.utc),
        )
    finally:
        db.close()


def test_remote_get_timeseries(monkeypatch) -> None:
    _store_connection()
    monkeypatch.setattr(tool_execution_guard, "get_http_request", _fake_request)

    class FakeClient:
        async def get_user(self, user_id: str) -> dict:
            return {"id": "user-1", "first_name": "Tim", "last_name": "Duncan"}

        async def get_timeseries(
            self,
            *,
            user_id: str,
            start_time: str,
            end_time: str,
            types: list[str],
            resolution: str = "raw",
            limit: int = 100,
            cursor: str | None = None,
        ) -> dict:
            assert types == ["heart_rate", "steps"]
            assert resolution == "1hour"
            assert limit == 5
            assert cursor is None
            return {
                "data": [
                    {
                        "timestamp": "2026-03-10T07:00:00Z",
                        "type": "heart_rate",
                        "value": 64,
                        "unit": "bpm",
                        "source": {"provider": "apple", "device": "Watch"},
                    },
                    {
                        "timestamp": "2026-03-10T07:00:00Z",
                        "type": "steps",
                        "value": 120,
                        "unit": "count",
                        "source": {"provider": "apple", "device": "Watch"},
                    },
                ],
                "pagination": {
                    "next_cursor": "cursor-2",
                    "previous_cursor": None,
                    "has_more": True,
                    "total_count": 24,
                },
                "metadata": {
                    "resolution": "1hour",
                    "sample_count": 2,
                    "start_time": "2026-03-01T00:00:00Z",
                    "end_time": "2026-03-11T00:00:00Z",
                },
            }

    monkeypatch.setattr(tool_execution_guard, "create_ow_api_client", lambda api_key: FakeClient())

    import asyncio

    payload = asyncio.run(
        get_timeseries(
            user_id="user-1",
            start_time="2026-03-01",
            end_time="2026-03-11",
            types=["heart_rate", "steps"],
            resolution="1hour",
            limit=5,
        )
    )
    assert payload["summary"]["sample_count"] == 2
    assert payload["summary"]["counts_by_type"]["heart_rate"] == 1
    assert payload["summary"]["counts_by_type"]["steps"] == 1
    assert payload["pagination"]["next_cursor"] == "cursor-2"
    assert payload["records"][0]["device"] == "Watch"


def test_remote_get_timeseries_rejects_unsupported_type(monkeypatch) -> None:
    _store_connection()
    monkeypatch.setattr(tool_execution_guard, "get_http_request", _fake_request)

    class FakeClient:
        async def get_user(self, user_id: str) -> dict:
            return {"id": "user-1", "first_name": "Tim", "last_name": "Duncan"}

    monkeypatch.setattr(tool_execution_guard, "create_ow_api_client", lambda api_key: FakeClient())

    import asyncio

    payload = asyncio.run(
        get_timeseries(
            user_id="user-1",
            start_time="2026-03-01",
            end_time="2026-03-11",
            types=["spo2"],
        )
    )
    assert payload["error"] == "unexpected_error"
    assert "Allowed types" in payload["message"]
