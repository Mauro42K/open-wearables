from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from pydantic import SecretStr


TEST_DB = Path("/Users/mauro/open-wearables/ow_mcp/test_ow_mcp_oauth.db")
if TEST_DB.exists():
    TEST_DB.unlink()


import app.config as app_config  # noqa: E402

app_config.settings.database_url = f"sqlite:///{TEST_DB}"
app_config.settings.allow_debug_session_headers = False
app_config.settings.encryption_key = SecretStr("test-encryption-key")
app_config.settings.session_secret_key = SecretStr("test-session-secret")
app_config.settings.google_client_id = "test-client-id.apps.googleusercontent.com"
app_config.settings.google_client_secret = SecretStr("test-google-client-secret")
app_config.settings.app_base_url = "https://ow-mcp.example.com"

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repositories.connection_repository import ConnectionRepository  # noqa: E402
from app.services.crypto_service import crypto_service  # noqa: E402
from app.services.session_resolver import resolve_authenticated_user_from_request  # noqa: E402
import app.services.tool_execution_guard as tool_execution_guard  # noqa: E402
from app.tools.users import get_users  # noqa: E402


Base.metadata.create_all(bind=engine)
app = create_app()
client = TestClient(app)


def test_mcp_rejects_unauthenticated_requests_with_bearer_challenge() -> None:
    response = client.get("/mcp/")
    assert response.status_code == 401
    www_authenticate = response.headers.get("WWW-Authenticate", "")
    assert "Bearer" in www_authenticate
    assert "resource_metadata=" in www_authenticate
    assert "/.well-known/oauth-protected-resource/mcp" in www_authenticate


def test_root_well_known_metadata_routes_are_exposed() -> None:
    auth_server = client.get("/.well-known/oauth-authorization-server/mcp")
    assert auth_server.status_code == 200
    auth_server_json = auth_server.json()
    assert auth_server_json["issuer"] == "https://ow-mcp.example.com/mcp"
    assert auth_server_json["authorization_endpoint"] == "https://ow-mcp.example.com/mcp/authorize"
    assert auth_server_json["token_endpoint"] == "https://ow-mcp.example.com/mcp/token"

    resource_metadata = client.get("/.well-known/oauth-protected-resource/mcp")
    assert resource_metadata.status_code == 200
    metadata_json = resource_metadata.json()
    assert metadata_json["resource"] == "https://ow-mcp.example.com/mcp/"
    assert metadata_json["authorization_servers"] == ["https://ow-mcp.example.com/mcp"]


def test_bearer_token_context_is_used_before_session(monkeypatch) -> None:
    db = SessionLocal()
    try:
        repository = ConnectionRepository(db)
        repository.save_validated_connection(
            google_user_id="google-user-bearer",
            google_email="mauro@example.com",
            encrypted_api_key=crypto_service.encrypt_api_key("sk-test-valid-f3f4"),
            api_key_masked="sk-****f3f4",
            validated_at=datetime.now(timezone.utc),
        )
    finally:
        db.close()

    monkeypatch.setattr(
        tool_execution_guard,
        "get_http_request",
        lambda: SimpleNamespace(
            scope={},
            session={},
            headers={},
        ),
    )
    monkeypatch.setattr(
        "app.services.session_resolver.get_access_token",
        lambda: SimpleNamespace(
            client_id="chatgpt-client",
            claims={
                "sub": "google-user-bearer",
                "email": "mauro@example.com",
            },
        ),
    )

    class FakeOwApiClient:
        async def get_users(self, *, search: str | None = None, limit: int = 10) -> dict:
            return {
                "items": [
                    {
                        "id": "user-1",
                        "first_name": "Remote",
                        "last_name": "Bearer",
                        "email": "user@example.com",
                    }
                ],
                "total": 1,
            }

    monkeypatch.setattr(tool_execution_guard, "create_ow_api_client", lambda api_key: FakeOwApiClient())

    import asyncio

    payload = asyncio.run(get_users(limit=1))
    assert payload["total"] == 1
    assert payload["users"][0]["email"] == "user@example.com"

    resolved = resolve_authenticated_user_from_request(SimpleNamespace(session={}, headers={}))
    assert resolved.google_user_id == "google-user-bearer"
    assert resolved.google_email == "mauro@example.com"
