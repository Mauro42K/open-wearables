from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr


TEST_DB = Path("/Users/mauro/open-wearables/ow_mcp/test_ow_mcp.db")
if TEST_DB.exists():
    TEST_DB.unlink()


import app.config as app_config  # noqa: E402

app_config.settings.database_url = f"sqlite:///{TEST_DB}"
app_config.settings.allow_debug_session_headers = True
app_config.settings.encryption_key = SecretStr("test-encryption-key")

from app.main import create_app  # noqa: E402
from app.repositories.connection_repository import ConnectionRepository  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.services.backend_client import InvalidApiKeyError  # noqa: E402
import app.api.routes.connection as connection_routes  # noqa: E402


app = create_app()
client = TestClient(app)
Base.metadata.create_all(bind=engine)


def _headers() -> dict[str, str]:
    return {
        "X-Debug-Google-User-Id": "google-user-1",
        "X-Debug-Google-Email": "mauro@example.com",
    }


def test_validate_connection_persists_encrypted_key(monkeypatch) -> None:
    class FakeClient:
        async def validate_api_key(self) -> None:
            return None

    monkeypatch.setattr(connection_routes, "create_ow_api_client", lambda api_key: FakeClient())

    response = client.post("/api/connection/validate", headers=_headers(), json={"api_key": "sk-test-valid-f3f4"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "connected"
    assert body["connection"]["status"] == "connected"
    assert body["connection"]["api_key_masked"] == "sk-****f3f4"

    db = SessionLocal()
    try:
        repository = ConnectionRepository(db)
        connection = repository.get_by_google_user_id("google-user-1")
        assert connection is not None
        assert connection.encrypted_api_key is not None
        assert connection.encrypted_api_key != "sk-test-valid-f3f4"
    finally:
        db.close()


def test_validate_connection_rejects_invalid_key(monkeypatch) -> None:
    class FakeClient:
        async def validate_api_key(self) -> None:
            raise InvalidApiKeyError

    monkeypatch.setattr(connection_routes, "create_ow_api_client", lambda api_key: FakeClient())

    response = client.post("/api/connection/validate", headers=_headers(), json={"api_key": "sk-invalid"})
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_api_key"


def test_disconnect_connection_removes_stored_key(monkeypatch) -> None:
    class FakeClient:
        async def validate_api_key(self) -> None:
            return None

    monkeypatch.setattr(connection_routes, "create_ow_api_client", lambda api_key: FakeClient())
    client.post("/api/connection/validate", headers=_headers(), json={"api_key": "sk-test-valid-f3f4"})

    response = client.post("/api/connection/disconnect", headers=_headers(), json={})
    assert response.status_code == 200
    assert response.json() == {"status": "not_connected"}

    db = SessionLocal()
    try:
        repository = ConnectionRepository(db)
        connection = repository.get_by_google_user_id("google-user-1")
        assert connection is not None
        assert connection.status == "not_connected"
        assert connection.encrypted_api_key is None
    finally:
        db.close()


def test_validate_requires_authenticated_session() -> None:
    response = client.post("/api/connection/validate", json={"api_key": "sk-test-valid-f3f4"})
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"
