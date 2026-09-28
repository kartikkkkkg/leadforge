"""PostgreSQL compatibility: the real pipeline against a REAL PostgreSQL.

Runs only when ``LEADFORGE_TEST_POSTGRES_URL`` is set (e.g. pointing at the
``docker compose`` database); otherwise skipped. This exercises the exact
code paths the SQLite suite covers — table creation, the demo-provider
pipeline, JSON columns, UUID-string keys, transactions, cascade deletes,
timestamps, and the export service — catching anything SQLite hides.

The test cleans up everything it creates (job, results, companies).
"""

import asyncio
import os

import pytest

POSTGRES_URL = os.environ.get("LEADFORGE_TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="LEADFORGE_TEST_POSTGRES_URL not set — needs a real PostgreSQL",
)

from leadforge import models  # noqa: E402
from leadforge.db import build_engine, init_db, session_scope  # noqa: E402
from leadforge.schemas import JobCreate  # noqa: E402
from leadforge.services import export as export_service  # noqa: E402
from leadforge.services import jobs as job_service  # noqa: E402


@pytest.fixture()
def pg_engine():
    eng = build_engine(POSTGRES_URL)
    init_db(eng)  # create_all is a no-op for existing tables
    yield eng
    eng.dispose()


def _run_demo_job(engine) -> str:
    with session_scope(engine) as session:
        job = job_service.create_job(
            session,
            JobCreate(
                industry="Jewelry Stores",
                country="United States",
                requested_leads=10,
                provider="demo",
                demo_delay_ms=0,
            ),
        )
        job_id = job.id
    result = asyncio.run(job_service.run_job(job_id, engine=engine, delay_ms=0))
    assert result.status == "completed"
    return job_id


def _cleanup(engine, job_id: str) -> None:
    with session_scope(engine) as session:
        company_ids = [
            r.company_id
            for r in session.query(models.LeadResearchResult)
            .filter_by(job_id=job_id)
            .all()
        ]
        job = session.get(models.ResearchJob, job_id)
        if job is not None:
            session.delete(job)  # cascades to results + rejected records
        session.flush()
        if company_ids:
            session.query(models.Company).filter(
                models.Company.id.in_(company_ids)
            ).delete(synchronize_session=False)


class TestPostgresPipeline:
    def test_demo_job_completes_and_persists(self, pg_engine):
        job_id = _run_demo_job(pg_engine)
        try:
            with session_scope(pg_engine) as session:
                job = session.get(models.ResearchJob, job_id)
                assert job.status == "completed"
                assert job.accepted == 10
                assert job.completed_at is not None
                # naive UTC timestamps, same as SQLite behavior
                assert job.completed_at.tzinfo is None

                results = (
                    session.query(models.LeadResearchResult)
                    .filter_by(job_id=job_id)
                    .all()
                )
                assert len(results) == 10
                # JSON columns round-trip as dicts/lists on PostgreSQL
                scored = [r for r in results if r.score_factors]
                assert scored, "expected score_factors JSON on results"
                assert isinstance(scored[0].score_factors, dict)
        finally:
            _cleanup(pg_engine, job_id)

    def test_export_service_against_postgres(self, pg_engine):
        job_id = _run_demo_job(pg_engine)
        try:
            with session_scope(pg_engine) as session:
                job = session.get(models.ResearchJob, job_id)
                rows = export_service.fetch_export_rows(session, job_id)
                assert len(rows) == 10
                csv_bytes = export_service.render_csv(rows)
                assert csv_bytes.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
                xlsx_bytes = export_service.render_xlsx(job, rows)
                assert xlsx_bytes.startswith(b"PK")  # zip container
        finally:
            _cleanup(pg_engine, job_id)

    def test_cascade_delete_removes_results(self, pg_engine):
        job_id = _run_demo_job(pg_engine)
        with session_scope(pg_engine) as session:
            n_results = (
                session.query(models.LeadResearchResult)
                .filter_by(job_id=job_id)
                .count()
            )
            assert n_results == 10
        _cleanup(pg_engine, job_id)
        with session_scope(pg_engine) as session:
            assert session.get(models.ResearchJob, job_id) is None
            assert (
                session.query(models.LeadResearchResult)
                .filter_by(job_id=job_id)
                .count()
                == 0
            )
            assert (
                session.query(models.RejectedRecord)
                .filter_by(job_id=job_id)
                .count()
                == 0
            )
