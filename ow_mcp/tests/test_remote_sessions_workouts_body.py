from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone

from pydantic import SecretStr


TEST_DB = Path("/Users/mauro/open-wearables/ow_mcp/test_ow_mcp_sessions_workouts_body.db")
if TEST_DB.exists():
    TEST_DB.unlink()


import app.config as app_config  # noqa: E402

app_config.settings.database_url = f"sqlite:///{TEST_DB}"
app_config.settings.allow_debug_session_headers = True
app_config.settings.encryption_key = SecretStr("test-encryption-key")

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.repositories.connection_repository import ConnectionRepository  # noqa: E402
import app.services.tool_execution_guard as tool_execution_guard  # noqa: E402
from app.tools.body import get_body_summary  # noqa: E402
from app.tools.sleep import get_sleep_sessions  # noqa: E402
from app.tools.workouts import get_workout_events  # noqa: E402


Base.metadata.create_all(bind=engine)


def _fake_request() -> SimpleNamespace:
    return SimpleNamespace(
        headers={
            "x-debug-google-user-id": "google-user-extra",
            "x-debug-google-email": "mauro@example.com",
        }
    )


def _store_connection() -> None:
    db = SessionLocal()
    try:
        repository = ConnectionRepository(db)
        existing = repository.get_by_google_user_id("google-user-extra")
        if existing is not None:
            db.delete(existing)
            db.commit()
        repository.save_validated_connection(
            google_user_id="google-user-extra",
            google_email="mauro@example.com",
            encrypted_api_key=tool_execution_guard.crypto_service.encrypt_api_key("sk-test-valid-f3f4"),
            api_key_masked="sk-****f3f4",
            validated_at=datetime.now(timezone.utc),
        )
    finally:
        db.close()


def test_remote_get_sleep_sessions(monkeypatch) -> None:
    _store_connection()
    monkeypatch.setattr(tool_execution_guard, "get_http_request", _fake_request)

    class FakeClient:
        async def get_user(self, user_id: str) -> dict:
            return {"id": "user-1", "first_name": "Tim", "last_name": "Duncan"}

        async def get_sleep_sessions(self, *, user_id: str, start_date: str, end_date: str) -> dict:
            return {
                "data": [
                    {
                        "id": "sleep-1",
                        "start_time": "2026-03-09T23:00:00Z",
                        "end_time": "2026-03-10T07:00:00Z",
                        "duration_seconds": 28800,
                        "efficiency_percent": 91,
                        "stages": {"deep_minutes": 80, "light_minutes": 250, "rem_minutes": 90},
                        "is_nap": False,
                        "source": {"provider": "apple", "device": "Watch"},
                    }
                ]
            }

    monkeypatch.setattr(tool_execution_guard, "create_ow_api_client", lambda api_key: FakeClient())

    import asyncio

    payload = asyncio.run(get_sleep_sessions(user_id="user-1", start_date="2026-03-01", end_date="2026-03-11"))
    assert payload["summary"]["total_sessions"] == 1
    assert payload["summary"]["avg_duration_seconds"] == 28800
    assert payload["records"][0]["source"] == "apple"
    assert payload["records"][0]["device"] == "Watch"


def test_remote_get_workout_events(monkeypatch) -> None:
    _store_connection()
    monkeypatch.setattr(tool_execution_guard, "get_http_request", _fake_request)

    class FakeClient:
        async def get_user(self, user_id: str) -> dict:
            return {"id": "user-1", "first_name": "Tim", "last_name": "Duncan"}

        async def get_workouts(
            self,
            *,
            user_id: str,
            start_date: str,
            end_date: str,
            record_type: str | None = None,
        ) -> dict:
            assert record_type == "running"
            return {
                "data": [
                    {
                        "id": "workout-1",
                        "type": "running",
                        "start_time": "2026-03-10T07:00:00Z",
                        "end_time": "2026-03-10T07:45:00Z",
                        "duration_seconds": 2700,
                        "distance_meters": 7500.0,
                        "calories_kcal": 520.0,
                        "avg_heart_rate_bpm": 145,
                        "max_heart_rate_bpm": 172,
                        "avg_pace_sec_per_km": 360,
                        "elevation_gain_meters": 85.0,
                        "source": {"provider": "garmin"},
                    }
                ]
            }

    monkeypatch.setattr(tool_execution_guard, "create_ow_api_client", lambda api_key: FakeClient())

    import asyncio

    payload = asyncio.run(
        get_workout_events(
            user_id="user-1",
            start_date="2026-03-01",
            end_date="2026-03-11",
            workout_type="running",
        )
    )
    assert payload["summary"]["total_workouts"] == 1
    assert payload["summary"]["total_distance_meters"] == 7500.0
    assert payload["summary"]["workout_types"]["running"] == 1
    assert payload["records"][0]["source"] == "garmin"


def test_remote_get_body_summary(monkeypatch) -> None:
    _store_connection()
    monkeypatch.setattr(tool_execution_guard, "get_http_request", _fake_request)

    class FakeClient:
        async def get_user(self, user_id: str) -> dict:
            return {"id": "user-1", "first_name": "Tim", "last_name": "Duncan"}

        async def get_body_summary(
            self,
            *,
            user_id: str,
            average_period: int = 7,
            latest_window_hours: int = 4,
        ) -> dict | None:
            assert average_period == 7
            assert latest_window_hours == 4
            return {
                "source": {"provider": "polar", "device": "Vantage V2"},
                "slow_changing": {
                    "weight_kg": 82.0,
                    "height_cm": 177.0,
                    "body_fat_percent": 15.0,
                    "muscle_mass_kg": None,
                    "bmi": 26.2,
                    "age": 36,
                },
                "averaged": {
                    "period_days": 7,
                    "resting_heart_rate_bpm": 54,
                    "avg_hrv_sdnn_ms": 41.2,
                    "period_start": "2026-03-04T00:00:00Z",
                    "period_end": "2026-03-11T00:00:00Z",
                },
                "latest": {
                    "body_temperature_celsius": None,
                    "body_temperature_measured_at": None,
                    "skin_temperature_celsius": None,
                    "skin_temperature_measured_at": None,
                    "blood_pressure": None,
                    "blood_pressure_measured_at": None,
                },
            }

    monkeypatch.setattr(tool_execution_guard, "create_ow_api_client", lambda api_key: FakeClient())

    import asyncio

    payload = asyncio.run(get_body_summary(user_id="user-1"))
    assert payload["summary"]["source"]["provider"] == "polar"
    assert payload["summary"]["slow_changing"]["weight_kg"] == 82.0
    assert payload["summary"]["averaged"]["resting_heart_rate_bpm"] == 54
