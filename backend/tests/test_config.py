"""Tests for environment-driven configuration (Phase 3)."""

import os

from leadforge.config import Settings, get_settings, reset_settings_cache


def test_sqlite_is_default(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings()
    assert settings.database_url is None
    assert not settings.is_postgres
    assert settings.sqlalchemy_url.startswith("sqlite:///")
    assert settings.sqlalchemy_url.endswith("leadforge.db")


def test_postgres_when_database_url_set(monkeypatch):
    url = "postgresql+psycopg2://leadforge:leadforge@localhost:5432/leadforge"
    monkeypatch.setenv("DATABASE_URL", url)
    settings = Settings()
    assert settings.is_postgres
    assert settings.sqlalchemy_url == url


def test_development_defaults(monkeypatch):
    for var in list(os.environ):
        if var == "DATABASE_URL" or var.startswith("LEADFORGE_"):
            monkeypatch.delenv(var, raising=False)
    settings = Settings()
    assert settings.leadforge_provider == "demo"
    assert settings.leadforge_ai_enabled is False
    assert settings.leadforge_llm_api_key is None
    assert settings.leadforge_demo_seed == 42
    assert settings.leadforge_demo_delay_ms == 120
    assert settings.leadforge_env == "development"
    assert settings.leadforge_log_level == "INFO"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("LEADFORGE_DEMO_DELAY_MS", "0")
    monkeypatch.setenv("LEADFORGE_AI_ENABLED", "true")
    monkeypatch.setenv("LEADFORGE_LLM_API_KEY", "test-key")
    settings = Settings()
    assert settings.leadforge_demo_delay_ms == 0
    assert settings.leadforge_ai_enabled is True
    assert settings.leadforge_llm_api_key == "test-key"


def test_get_settings_is_cached_and_resettable(monkeypatch):
    first = get_settings()
    assert get_settings() is first
    reset_settings_cache()
    assert get_settings() is not first
