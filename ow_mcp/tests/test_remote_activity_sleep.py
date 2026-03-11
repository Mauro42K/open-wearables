from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone

from pydantic import SecretStr


TEST_DB = Path("/Users/mauro/open-wearables/ow_mcp/test_ow_mcp_activity_sleep.db")
if TEST_DB.exists():
    TEST_DB.unlink()


import app.config as app_config  # noqa: E402

app_config.settings.database_url = f"sqlite:///{TEST_DB}"
app_config.settings.allow_debug_session_headers = True
app_config.settings.encryption_key = SecretStr("test-encryption-key")

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.repositories.connection_repository import ConnectionRepository  # noqa: E402
import app.services.tool_execution_guard as tool_execution_guard  # noqa: E402
from app.tools.activity import get_activity_summary  # noqa: E402
from app.tools.sleep import get_sleep_summary  # noqa: E402


Base.metadata.create_all(bind=engine)


def _fake_request() -> SimpleNamespace:
    return SimpleNamespace(
        headers={
            "x-debug-google-user-id": "google-user-activity",
            "x-debug-google-email": "mauro@example.com",
        }
    )


def _store_connection() -> None:
    db = SessionLocal()
    try:
        repository = ConnectionRepository(db)
        existing = repository.get_by_google_user_id("google-user-activity")
        if existing is not None:
            db.delete(existing)
            db.commit()
        repository.save_validated_connection(
            google_user_id="google-user-activity",
            google_email="mauro@example.com",
            encrypted_api_key=tool_execution_guard.crypto_service.encrypt_api_key("sk-test-valid-f3f4"),
            api_key_masked="sk-****f3f4",
            validated_at=datetime.now(timezone.utc),
        )
    finally:
        db.close()


def test_remote_get_activity_summary(monkeypatch) -> None:
    _store_connection()
    monkeypatch.setattr(tool_execution_guard, "get_http_request", _fake_request)

    class FakeClient:
        async def get_user(self, user_id: str) -> dict:
            assert user_id == "user-1"
            return {"id": "user-1", "first_name": "Tim", "last_name": "Duncan"}

        async def get_activity_summaries(self, *, user_id: str, start_date: str, end_date: str) -> dict:
            return {
                "data": [
                    {
                        "date": "2026-03-10",
                        "steps": 4000,
                        "distance_meters": 3200.0,
                        "active_calories_kcal": 250.0,
                        "total_calories_kcal": 2100.0,
                        "active_minutes": 40,
                        "intensity_minutes": {"light": 15, "moderate": 20, "vigorous": 5},
                        "heart_rate": {"avg_bpm": 72, "max_bpm": 130, "min_bpm": 55},
                        "source": {"provider": "apple"},
                    }
                ]
            }

    monkeypatch.setattr(tool_execution_guard, "create_ow_api_client", lambda api_key: FakeClient())

    import asyncio

    payload = asyncio.run(get_activity_summary(user_id="user-1", start_date="2026-03-01", end_date="2026-03-11"))
    assert payload["summary"]["total_steps"] == 4000
    assert payload["summary"]["avg_steps"] == 4000
    assert payload["records"][0]["source"] == "apple"


def test_remote_get_sleep_summary(monkeypatch) -> None:
    _store_connection()
    monkeypatch.setattr(tool_execution_guard, "get_http_request", _fake_request)

    class FakeClient:
        async def get_user(self, user_id: str) -> dict:
            return {"id": "user-1", "first_name": "Tim", "last_name": "Duncan"}

        async def get_sleep_summaries(self, *, user_id: str, start_date: str, end_date: str) -> dict:
            return {
                "data": [
                    {
                        "date": "2026-03-10",
                        "start_time": "2026-03-09T23:00:00Z",
                        "end_time": "2026-03-10T07:00:00Z",
                        "duration_minutes": 480,
                        "source": {"provider": "apple"},
                    }
                ]
            }

    monkeypatch.setattr(tool_execution_guard, "create_ow_api_client", lambda api_key: FakeClient())

    import asyncio

    payload = asyncio.run(get_sleep_summary(user_id="user-1", start_date="2026-03-01", end_date="2026-03-11"))
    assert payload["summary"]["total_nights"] == 1
    assert payload["summary"]["avg_duration_minutes"] == 480
    assert payload["records"][0]["source"] == "apple"
