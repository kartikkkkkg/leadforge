"""Environment-driven configuration for LeadForge.

SQLite is the default (zero setup). Set ``DATABASE_URL`` for PostgreSQL.
No secrets live in source code — everything sensitive comes from the environment
(or an untracked ``.env`` file, which is gitignored).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database ---
    # Leave unset for zero-setup SQLite mode.
    database_url: str | None = None

    # --- Research providers ---
    leadforge_provider: str = "demo"
    leadforge_http_api_key: str | None = None
    leadforge_http_api_base_url: str | None = None

    # --- AI enrichment (optional; the app fully works without it) ---
    leadforge_ai_enabled: bool = False
    leadforge_llm_provider: str | None = None
    leadforge_llm_api_key: str | None = None
    leadforge_llm_model: str | None = None

    # --- Demo ---
    leadforge_demo_seed: int = 42
    leadforge_demo_delay_ms: int = 120

    # --- App ---
    leadforge_env: str = "development"
    leadforge_log_level: str = "INFO"
    backend_port: int = 8000

    @property
    def sqlalchemy_url(self) -> str:
        """Resolve the SQLAlchemy URL: ``DATABASE_URL`` or the default SQLite file."""
        if self.database_url:
            return self.database_url
        data_dir = Path(__file__).resolve().parent.parent / "data"
        return f"sqlite:///{data_dir / 'leadforge.db'}"

    @property
    def is_postgres(self) -> bool:
        """True when a PostgreSQL ``DATABASE_URL`` is configured."""
        return (self.database_url or "").startswith("postgresql")


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance. Call :func:`reset_settings_cache` in tests."""
    return Settings()


def reset_settings_cache() -> None:
    """Clear the cached settings (used by tests that monkeypatch the environment)."""
    get_settings.cache_clear()
