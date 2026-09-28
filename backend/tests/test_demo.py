"""Integration tests: demo seed/reset endpoints, CLI, demo delay.

Uses an isolated file-based SQLite database and the DemoProvider — no
network, no external services. The demo dataset is synthetic by
construction; these tests assert that explicitly.
"""

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from leadforge import cli as cli_module
from leadforge import models
from leadforge.db import session_scope
from leadforge.main import create_app
from leadforge.pipeline.runner import PipelineRunner
from leadforge.schemas import JobCreate
from leadforge.seed import DATASET_SIZE
from leadforge.services import demo as demo_service
from leadforge.services import jobs as job_service


@pytest.fixture
def client(engine):
    app = create_app(engine=engine)
    with TestClient(app) as test_client:
        yield test_client


def _company_count(session):
    return session.query(models.Company).count()


def _run_demo_job(engine, **overrides):
    """Create + synchronously run a small demo job (delay_ms=0)."""
    payload = {
        "industry": "Jewelry Stores",
        "country": "United States",
        "requested_leads": 10,
        "provider": "demo",
        "demo_delay_ms": 0,
    }
    payload.update(overrides)
    with session_scope(engine) as session:
        job = job_service.create_job(session, JobCreate(**payload))
        session.commit()
        job_id = job.id
    asyncio.run(job_service.run_job(job_id, engine=engine, delay_ms=0))
    return job_id


# ---------------------------------------------------------------------------
# POST /api/demo/seed
# ---------------------------------------------------------------------------


class TestDemoSeed:
    def test_dataset_size_matches_seed_contract(self):
        assert demo_service.demo_dataset_size() == DATASET_SIZE == 100

    def test_seed_returns_100_companies(self, client, engine):
        resp = client.post("/api/demo/seed")
        assert resp.status_code == 200
        assert resp.json() == {"companies": DATASET_SIZE}
        assert DATASET_SIZE == 100
        with session_scope(engine) as session:
            assert _company_count(session) == 100

    def test_seed_is_synthetic_only(self, client, engine):
        client.post("/api/demo/seed")
        with session_scope(engine) as session:
            companies = session.query(models.Company).all()
            assert all(c.is_synthetic for c in companies)
            assert all(c.source_provider == "demo-seed" for c in companies)
            for c in companies:
                if c.website:
                    assert ".example.com" in c.website
                if c.public_email:
                    assert ".example.com" in c.public_email
                if c.phone:
                    assert "555-01" in c.phone

    def test_seed_is_idempotent(self, client, engine):
        client.post("/api/demo/seed")
        resp = client.post("/api/demo/seed")
        assert resp.status_code == 200
        assert resp.json() == {"companies": 100}
        with session_scope(engine) as session:
            assert _company_count(session) == 100

    def test_seed_is_deterministic(self, client, engine):
        client.post("/api/demo/seed")
        with session_scope(engine) as session:
            first = [c.company_name for c in
                     session.query(models.Company).order_by(models.Company.company_name).all()]
        client.post("/api/demo/seed")
        with session_scope(engine) as session:
            second = [c.company_name for c in
                      session.query(models.Company).order_by(models.Company.company_name).all()]
        assert first == second
        assert len(first) == 100

    def test_seed_does_not_touch_jobs(self, client, engine):
        job_id = _run_demo_job(engine)
        client.post("/api/demo/seed")
        with session_scope(engine) as session:
            assert session.get(models.ResearchJob, job_id) is not None
            assert session.query(models.LeadResearchResult).count() > 0


# ---------------------------------------------------------------------------
# POST /api/demo/reset
# ---------------------------------------------------------------------------


class TestDemoReset:
    def test_reset_wipes_demo_data(self, client, engine):
        job_id = _run_demo_job(engine)
        client.post("/api/demo/seed")
        resp = client.post("/api/demo/reset")
        assert resp.status_code == 200
        body = resp.json()
        assert body["jobs_deleted"] == 1
        assert body["results_deleted"] > 0
        assert body["companies_deleted"] >= 100  # seeded + pipeline companies
        assert body["reseeded"] is False
        assert body["companies"] == 0
        with session_scope(engine) as session:
            assert session.get(models.ResearchJob, job_id) is None
            assert _company_count(session) == 0
            assert session.query(models.LeadResearchResult).count() == 0
            assert session.query(models.RejectedRecord).count() == 0

    def test_reset_on_empty_database(self, client, engine):
        resp = client.post("/api/demo/reset")
        assert resp.status_code == 200
        body = resp.json()
        assert body["jobs_deleted"] == 0
        assert body["companies_deleted"] == 0

    def test_reset_with_reseed(self, client, engine):
        _run_demo_job(engine)
        resp = client.post("/api/demo/reset", json={"reseed": True})
        assert resp.status_code == 200
        body = resp.json()
        assert body["jobs_deleted"] == 1
        assert body["reseeded"] is True
        assert body["companies"] == 100
        with session_scope(engine) as session:
            assert _company_count(session) == 100
            assert session.query(models.ResearchJob).count() == 0

    def test_reset_without_body_defaults_to_no_reseed(self, client):
        resp = client.post("/api/demo/reset")
        assert resp.status_code == 200
        assert resp.json()["reseeded"] is False


# ---------------------------------------------------------------------------
# CLI: seed-demo / reset-demo / run-demo
# ---------------------------------------------------------------------------


class TestDemoCli:
    def test_seed_demo_cli(self, engine, monkeypatch):
        monkeypatch.setattr("leadforge.db.get_engine", lambda: engine)
        assert cli_module.main(["seed-demo"]) == 0
        with session_scope(engine) as session:
            assert _company_count(session) == 100

    def test_reset_demo_cli_with_reseed(self, engine, monkeypatch):
        monkeypatch.setattr("leadforge.db.get_engine", lambda: engine)
        assert cli_module.main(["seed-demo"]) == 0
        assert cli_module.main(["reset-demo", "--reseed"]) == 0
        with session_scope(engine) as session:
            assert _company_count(session) == 100
            assert session.query(models.ResearchJob).count() == 0

    def test_run_demo_cli_no_delay(self, engine, monkeypatch, capsys):
        monkeypatch.setattr("leadforge.db.get_engine", lambda: engine)
        rc = cli_module.main([
            "run-demo", "--industry", "Jewelry Stores",
            "--country", "United States", "--leads", "10", "--no-delay",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "completed" in out
        with session_scope(engine) as session:
            assert session.query(models.ResearchJob).count() == 1


# ---------------------------------------------------------------------------
# demo delay configuration
# ---------------------------------------------------------------------------


class TestDemoDelay:
    def test_delay_ms_stored_on_job(self, client):
        resp = client.post("/api/research/jobs", json={
            "industry": "Jewelry Stores",
            "country": "United States",
            "requested_leads": 10,
            "demo_delay_ms": 250,
        })
        assert resp.status_code == 202
        assert resp.json()["demo_delay_ms"] == 250

    def test_delay_ms_defaults_to_120(self, client):
        resp = client.post("/api/research/jobs", json={
            "industry": "Jewelry Stores",
            "country": "United States",
            "requested_leads": 10,
        })
        assert resp.json()["demo_delay_ms"] == 120

    def test_runner_sleeps_when_delay_configured(self, engine, monkeypatch):
        sleeps: list[float] = []

        async def _record(delay):
            sleeps.append(delay)

        monkeypatch.setattr("asyncio.sleep", _record)
        with session_scope(engine) as session:
            job = job_service.create_job(session, JobCreate(
                industry="Jewelry Stores", country="United States",
                requested_leads=10, provider="demo", demo_delay_ms=120,
            ))
            session.commit()
            job_id = job.id
        asyncio.run(job_service.run_job(job_id, engine=engine))
        assert sleeps, "expected the runner to sleep with demo_delay_ms=120"
        assert all(s == pytest.approx(0.12) for s in sleeps)

    def test_runner_does_not_sleep_when_delay_zero(self, engine, monkeypatch):
        sleeps: list[float] = []

        async def _record(delay):
            sleeps.append(delay)

        monkeypatch.setattr("asyncio.sleep", _record)
        with session_scope(engine) as session:
            job = job_service.create_job(session, JobCreate(
                industry="Jewelry Stores", country="United States",
                requested_leads=10, provider="demo", demo_delay_ms=0,
            ))
            session.commit()
            job_id = job.id
        asyncio.run(job_service.run_job(job_id, engine=engine, delay_ms=0))
        assert sleeps == []

    def test_progress_events_follow_real_stages(self, engine):
        """Progress callbacks fire for the actual pipeline stages, in order."""
        seen: list[str] = []
        with session_scope(engine) as session:
            job = job_service.create_job(session, JobCreate(
                industry="Jewelry Stores", country="United States",
                requested_leads=10, provider="demo", demo_delay_ms=0,
            ))
            session.commit()
            job_id = job.id
        runner = PipelineRunner(
            engine=engine, delay_ms=0,
            on_progress=lambda stage, snap: seen.append(stage),
        )
        asyncio.run(runner.run(job_id))
        for stage in ("DISCOVER", "NORMALIZE", "VALIDATE", "DEDUPLICATE",
                      "SCORE", "STORE", "DONE"):
            assert stage in seen
        # stages appear in pipeline order
        order = [seen.index(s) for s in
                 ("DISCOVER", "NORMALIZE", "VALIDATE", "DEDUPLICATE",
                  "SCORE", "STORE", "DONE")]
        assert order == sorted(order)
