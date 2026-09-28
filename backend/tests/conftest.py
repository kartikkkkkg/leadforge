"""pytest fixtures for LeadForge backend tests."""

import pytest

from leadforge import models  # noqa: F401
from leadforge.config import reset_settings_cache
from leadforge.db import build_engine, get_session_factory, init_db


@pytest.fixture(autouse=True)
def _clean_settings_cache():
    """Settings are cached process-wide; reset between tests that touch env vars."""
    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.fixture()
def engine(tmp_path):
    """Fresh file-based SQLite database with all four tables created."""
    eng = build_engine(f"sqlite:///{tmp_path}/test.db")
    init_db(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    """A session bound to the test engine (rolled back and closed after each test)."""
    sess = get_session_factory(engine)()
    yield sess
    sess.rollback()
    sess.close()
