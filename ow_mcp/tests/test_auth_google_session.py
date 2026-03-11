from pathlib import Path
from types import SimpleNamespace

from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from pydantic import SecretStr


TEST_DB = Path("/Users/mauro/open-wearables/ow_mcp/test_ow_mcp_auth.db")
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
from app.schemas.auth import AuthenticatedUser  # noqa: E402
import app.api.routes.auth as auth_routes  # noqa: E402
import app.api.routes.connection as connection_routes  # noqa: E402
import app.services.tool_execution_guard as tool_execution_guard  # noqa: E402
from app.tools.users import get_users  # noqa: E402


Base.metadata.create_all(bind=engine)
app = create_app()
client = TestClient(app)


def _authenticated_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        google_user_id="google-user-oauth",
        google_email="mauro@example.com",
        session_id="google-google-user-oauth",
        authenticated_at="2026-03-11T12:00:00Z",
    )


def test_google_start_redirects(monkeypatch) -> None:
    async def fake_begin_google_oauth(request):
        return RedirectResponse(url="https://accounts.google.com/o/oauth2/auth", status_code=302)

    monkeypatch.setattr(auth_routes, "begin_google_oauth", fake_begin_google_oauth)

    response = client.get("/auth/google/start", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].startswith("https://accounts.google.com/")


def test_google_callback_persists_session_and_validate_disconnect_work(monkeypatch) -> None:
    async def fake_complete_google_oauth(request):
        return _authenticated_user()

    class FakeClient:
        async def validate_api_key(self) -> None:
            return None

    monkeypatch.setattr(auth_routes, "complete_google_oauth", fake_complete_google_oauth)
    monkeypatch.setattr(connection_routes, "create_ow_api_client", lambda api_key: FakeClient())

    callback_response = client.get("/auth/google/callback", follow_redirects=False)
    assert callback_response.status_code == 302
    assert callback_response.headers["location"] == "/connect"

    session_response = client.get("/auth/session")
    assert session_response.status_code == 200
    assert session_response.json()["authenticated_user"]["google_email"] == "mauro@example.com"

    validate_response = client.post("/api/connection/validate", json={"api_key": "sk-test-valid-f3f4"})
    assert validate_response.status_code == 200
    assert validate_response.json()["connection"]["status"] == "connected"

    db = SessionLocal()
    try:
        repository = ConnectionRepository(db)
        connection = repository.get_by_google_user_id("google-user-oauth")
        assert connection is not None
        assert connection.status == "connected"
        assert connection.encrypted_api_key is not None
    finally:
        db.close()

    disconnect_response = client.post("/api/connection/disconnect", json={})
    assert disconnect_response.status_code == 200
    assert disconnect_response.json() == {"status": "not_connected"}


def test_logout_clears_session(monkeypatch) -> None:
    async def fake_complete_google_oauth(request):
        return _authenticated_user()

    monkeypatch.setattr(auth_routes, "complete_google_oauth", fake_complete_google_oauth)
    client.get("/auth/google/callback", follow_redirects=False)

    logout_response = client.post("/auth/logout")
    assert logout_response.status_code == 200
    assert logout_response.json() == {"status": "signed_out"}

    session_response = client.get("/auth/session")
    assert session_response.status_code == 401
    assert session_response.json()["error"] == "unauthorized"


def test_remote_get_users_uses_session_context(monkeypatch) -> None:
    db = SessionLocal()
    try:
        repository = ConnectionRepository(db)
        repository.save_validated_connection(
            google_user_id="google-user-oauth",
            google_email="mauro@example.com",
            encrypted_api_key=tool_execution_guard.crypto_service.encrypt_api_key("sk-test-valid-f3f4"),
            api_key_masked="sk-****f3f4",
            validated_at=_authenticated_user().authenticated_at,
        )
    finally:
        db.close()

    monkeypatch.setattr(
        tool_execution_guard,
        "get_http_request",
        lambda: SimpleNamespace(
            session={"authenticated_user": _authenticated_user().model_dump(mode="json")},
            headers={},
        ),
    )

    class FakeOwApiClient:
        async def get_users(self, *, search: str | None = None, limit: int = 10) -> dict:
            assert search == "tim"
            assert limit == 2
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

    monkeypatch.setattr(tool_execution_guard, "create_ow_api_client", lambda api_key: FakeOwApiClient())

    import asyncio

    payload = asyncio.run(get_users(search="tim", limit=2))
    assert payload["total"] == 1
    assert payload["users"][0]["email"] == "tim@example.com"
