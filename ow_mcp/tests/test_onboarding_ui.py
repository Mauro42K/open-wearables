from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr


TEST_DB = Path("/Users/mauro/open-wearables/ow_mcp/test_ow_mcp_ui.db")
if TEST_DB.exists():
    TEST_DB.unlink()


import app.config as app_config  # noqa: E402

app_config.settings.database_url = f"sqlite:///{TEST_DB}"
app_config.settings.allow_debug_session_headers = True
app_config.settings.encryption_key = SecretStr("test-encryption-key")
app_config.settings.session_secret_key = SecretStr("test-session-secret")

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repositories.connection_repository import ConnectionRepository  # noqa: E402
import app.api.routes.auth as auth_routes  # noqa: E402
import app.api.routes.connection as connection_routes  # noqa: E402


Base.metadata.create_all(bind=engine)
app = create_app()
client = TestClient(app)


def _login(monkeypatch) -> None:
    async def fake_complete_google_oauth(request):
        from app.schemas.auth import AuthenticatedUser

        return AuthenticatedUser(
            google_user_id="google-user-ui",
            google_email="mauro@example.com",
            session_id="google-google-user-ui",
            authenticated_at="2026-03-11T12:00:00Z",
        )

    monkeypatch.setattr(auth_routes, "complete_google_oauth", fake_complete_google_oauth)
    response = client.get("/auth/google/callback", follow_redirects=False)
    assert response.status_code == 302


def test_connect_page_renders_form(monkeypatch) -> None:
    _login(monkeypatch)

    response = client.get("/connect")
    assert response.status_code == 200
    assert "Connect Open Wearables API Key" in response.text
    assert "/api/connection/validate" in response.text


def test_status_page_renders_connected_state_and_disconnect(monkeypatch) -> None:
    _login(monkeypatch)

    class FakeClient:
        async def validate_api_key(self) -> None:
            return None

    monkeypatch.setattr(connection_routes, "create_ow_api_client", lambda api_key: FakeClient())

    validate = client.post("/api/connection/validate", json={"api_key": "sk-test-valid-f3f4"})
    assert validate.status_code == 200

    response = client.get("/status")
    assert response.status_code == 200
    assert "Connection Status" in response.text
    assert "sk-****f3f4" in response.text
    assert "/api/connection/disconnect" in response.text


def test_disconnect_flow_returns_to_connect(monkeypatch) -> None:
    _login(monkeypatch)

    class FakeClient:
        async def validate_api_key(self) -> None:
            return None

    monkeypatch.setattr(connection_routes, "create_ow_api_client", lambda api_key: FakeClient())
    client.post("/api/connection/validate", json={"api_key": "sk-test-valid-f3f4"})
    disconnect = client.post("/api/connection/disconnect", json={})
    assert disconnect.status_code == 200

    response = client.get("/connect")
    assert response.status_code == 200

    db = SessionLocal()
    try:
        repository = ConnectionRepository(db)
        connection = repository.get_by_google_user_id("google-user-ui")
        assert connection is not None
        assert connection.status == "not_connected"
        assert connection.encrypted_api_key is None
    finally:
        db.close()
