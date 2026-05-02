"""
app/config.py — Centralised configuration via environment variables.

Uses pydantic-settings to parse the .env file automatically and expose
typed configuration throughout the application.
"""

from functools import lru_cache
import ssl

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application-wide settings loaded from environment / .env file."""

    # ── Database ──
    DATABASE_URL: str = "postgresql+asyncpg://moderation_user:moderation_pass@db:5432/moderation_db"
    DATABASE_SSL_MODE: str = "prefer"
    DATABASE_POOL_PRE_PING: bool = True

    # ── External API keys ──
    HF_API_TOKEN: str = ""
    NVIDIA_API_KEY: str = ""
    NVIDIA_NIM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_NIM_MODEL: str = "openai/gpt-oss-120b"

    # ── App metadata ──
    APP_TITLE: str = "AI Content Moderation System"
    APP_VERSION: str = "1.0.0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore POSTGRES_* and other vars not declared above

    @property
    def sqlalchemy_database_url(self) -> str:
        """
        Normalize incoming Postgres URLs for SQLAlchemy + asyncpg.

        This allows using a local asyncpg URL or pasting a Supabase
        connection string directly from the dashboard.
        """
        raw_url = self.DATABASE_URL.strip()

        if raw_url.startswith("postgresql+asyncpg://"):
            normalized = raw_url
        elif raw_url.startswith("postgresql://"):
            normalized = "postgresql+asyncpg://" + raw_url[len("postgresql://"):]
        elif raw_url.startswith("postgres://"):
            normalized = "postgresql+asyncpg://" + raw_url[len("postgres://"):]
        else:
            normalized = raw_url

        return normalized

    @property
    def sqlalchemy_connect_args(self) -> dict:
        """
        Build asyncpg-specific connection arguments.

        Supabase needs TLS, but asyncpg expects this via ``ssl`` rather than
        a libpq-style ``sslmode`` query parameter.
        """
        ssl_mode = self.DATABASE_SSL_MODE.strip().lower()

        if ssl_mode in ("", "prefer"):
            return {}
        if ssl_mode in ("disable", "allow"):
            return {"ssl": False}
        if ssl_mode == "require":
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return {"ssl": ctx}
        if ssl_mode in ("verify-ca", "verify-full"):
            return {"ssl": ssl.create_default_context()}
        return {"ssl": True}


@lru_cache()
def get_settings() -> Settings:
    """Singleton accessor — settings are read once and cached."""
    return Settings()
