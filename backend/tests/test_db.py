"""Tests for engine/session management and table initialization (Phase 3)."""

from sqlalchemy import inspect

from leadforge import models  # noqa: F401
from leadforge.db import build_engine, get_session_factory, init_db, session_scope


def test_build_engine_sqlite_defaults(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path}/sub/dir/test.db")
    assert engine.url.drivername == "sqlite"
    # parent directories are created on demand
    assert (tmp_path / "sub" / "dir" / "test.db").parent.exists()
    engine.dispose()


def test_sqlite_foreign_keys_enforced(engine):
    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_init_db_creates_all_four_tables(engine):
    tables = set(inspect(engine).get_table_names())
    assert {"research_jobs", "companies", "lead_results", "rejected_records"} <= tables


def test_session_scope_commits(session, engine):
    from tests.fixtures import make_job

    with session_scope(engine) as sess:
        sess.add(make_job())
    # new session sees the committed row
    with session_scope(engine) as sess:
        assert sess.query(models.ResearchJob).count() == 1


def test_session_scope_rolls_back_on_error(engine):
    from sqlalchemy.exc import IntegrityError

    from tests.fixtures import make_job

    try:
        with session_scope(engine) as sess:
            sess.add(make_job(industry="Will Roll Back"))
            # violate NOT NULL on country -> IntegrityError on flush/commit
            bad = make_job()
            bad.country = None
            sess.add(bad)
            sess.flush()
    except IntegrityError:
        pass
    with session_scope(engine) as sess:
        assert sess.query(models.ResearchJob).count() == 0


def test_session_factory_binds_engine(engine):
    factory = get_session_factory(engine)
    sess = factory()
    try:
        assert sess.bind is engine
    finally:
        sess.close()
