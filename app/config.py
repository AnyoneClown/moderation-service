"""
app/config.py — Centralised configuration via environment variables.

Uses pydantic-settings to parse the .env file automatically and expose
typed configuration throughout the application.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application-wide settings loaded from environment / .env file."""

    # ── Database ──
    DATABASE_URL: str = "postgresql+asyncpg://moderation_user:moderation_pass@db:5432/moderation_db"

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


@lru_cache()
def get_settings() -> Settings:
    """Singleton accessor — settings are read once and cached."""
    return Settings()
