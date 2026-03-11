"""Application settings for ow-mcp."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings."""

    model_config = SettingsConfigDict(env_file="config/.env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_base_url: str = "http://localhost:8010"
    database_url: str = "sqlite:///./ow_mcp.db"
    ow_api_base_url: str = "https://ow-api.mauro42k.com"
    encryption_key: SecretStr = SecretStr("dev-fernet-key-placeholder-change-me")
    session_secret_key: SecretStr = SecretStr("dev-session-secret-change-me")
    session_cookie_name: str = "ow_mcp_session"
    session_max_age_seconds: int = 60 * 60 * 24 * 14
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    google_metadata_url: str = "https://accounts.google.com/.well-known/openid-configuration"
    allow_debug_session_headers: bool = False
    request_timeout: float = 10.0


settings = Settings()
