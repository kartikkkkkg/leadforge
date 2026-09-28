"""API tests: health, jobs, results, validation report, errors.

Uses an isolated in-memory database and the DemoProvider — no network, no
external services. Background pipeline tasks run in-process.
"""

import time

import pytest
from fastapi.testclient import TestClient

from leadforge.main import create_app
from leadforge.providers import DemoProvider
from leadforge.schemas import JobRead, ResultDetail, ResultsPage, ValidationReport


@pytest.fixture
def client(engine):
    app = create_app(engine=engine)
    with TestClient(app) as test_client:
        yield test_client


def create_job(client, **overrides):
    payload = {
        "industry": "Jewelry Stores",
        "country": "United States",
        "requested_leads": 10,
        "demo_delay_ms": 0,
    }
    payload.update(overrides)
    return client.post("/api/research/jobs", json=payload)


def wait_for(client, job_id, timeout_s=15.0):
    """Poll until the background pipeline finishes."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        job = client.get(f"/api/research/jobs/{job_id}").json()
        if job["status"] in ("completed", "failed"):
            return job
        time.sleep(0.05)
    raise TimeoutError(f"job {job_id} did not finish in {timeout_s}s")


# ---------------------------------------------------------------------------
# health & docs
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "version": "0.1.0"}

    def test_providers_health(self, client):
        resp = client.get("/api/providers/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["demo"]["status"] == "available"
        assert body["http"]["status"] == "not_configured"
        assert "LEADFORGE_HTTP_API_KEY" in body["http"]["detail"]
        assert body["ai"]["status"] == "not_configured"
        assert body["database"]["status"] == "available"
        # No secrets anywhere in the payload.
        assert "api_key" not in resp.text.lower() or "LEADFORGE_HTTP_API_KEY" in resp.text

    def test_openapi_generates(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        paths = resp.json()["paths"]
        for path in (
            "/api/health",
            "/api/providers/health",
            "/api/research/jobs",
            "/api/research/jobs/{job_id}",
            "/api/research/jobs/{job_id}/results",
            "/api/research/jobs/{job_id}/results/{result_id}",
            "/api/research/jobs/{job_id}/validation-report",
        ):
            assert path in paths


# ---------------------------------------------------------------------------
# job creation
# ---------------------------------------------------------------------------


class TestJobCreation:
    def test_create_job(self, client):
        resp = create_job(client)
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "queued"
        assert body["industry"] == "Jewelry Stores"
        assert body["provider"] == "demo"
        # Response validates against the documented schema.
        JobRead(**body)

    def test_create_job_invalid_request(self, client):
        resp = create_job(client, requested_leads=7)
        assert resp.status_code == 422

    def test_create_job_blank_industry(self, client):
        resp = create_job(client, industry="")
        assert resp.status_code == 422

    def test_create_job_unknown_provider(self, client):
        resp = create_job(client, provider="scraper")
        assert resp.status_code == 400
        assert resp.json()["code"] == "invalid_request"

    def test_create_job_unconfigured_http_provider(self, client):
        resp = create_job(client, provider="http")
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == "provider_not_configured"
        assert "LEADFORGE_HTTP_API_KEY" in body["detail"]


# ---------------------------------------------------------------------------
# job lifecycle via the API
# ---------------------------------------------------------------------------


class TestJobLifecycle:
    def test_full_demo_flow(self, client):
        job_id = create_job(client).json()["id"]
        job = wait_for(client, job_id)
        assert job["status"] == "completed"
        assert job["stage"] == "DONE"
        assert job["progress_pct"] == 100
        assert job["discovered"] == 10
        assert job["accepted"] + job["duplicates"] + job["invalid"] == 10
        assert job["error"] is None

    def test_get_job_not_found(self, client):
        resp = client.get("/api/research/jobs/job-missing")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "job_not_found"
        assert body["detail"]

    def test_list_jobs_pagination(self, client):
        create_job(client)
        create_job(client, industry="Restaurants")
        page1 = client.get("/api/research/jobs", params={"page": 1, "page_size": 1})
        assert page1.status_code == 200
        body = page1.json()
        assert body["total"] == 2
        assert body["page"] == 1
        assert body["page_size"] == 1
        assert len(body["items"]) == 1
        page2 = client.get("/api/research/jobs", params={"page": 2, "page_size": 1})
        assert len(page2.json()["items"]) == 1
        assert page2.json()["items"][0]["id"] != body["items"][0]["id"]

    def test_pipeline_failure_surfaces_on_job(self, client, monkeypatch):
        async def boom(self, query, limit):
            raise RuntimeError("demo blew up")

        monkeypatch.setattr(DemoProvider, "search_companies", boom)
        job_id = create_job(client).json()["id"]
        job = wait_for(client, job_id)
        assert job["status"] == "failed"
        assert "demo blew up" in job["error"]


# ---------------------------------------------------------------------------
# results
# ---------------------------------------------------------------------------


class TestResults:
    @pytest.fixture
    def completed_job(self, client):
        job_id = create_job(client).json()["id"]
        job = wait_for(client, job_id)
        assert job["status"] == "completed"
        return job_id, job

    def test_list_results(self, client, completed_job):
        job_id, job = completed_job
        resp = client.get(f"/api/research/jobs/{job_id}/results")
        assert resp.status_code == 200
        body = resp.json()
        ResultsPage(**body)  # schema validation
        assert body["total"] == job["accepted"]
        assert len(body["items"]) <= body["page_size"]
        first = body["items"][0]
        assert first["quality_score"] >= 0
        assert sum(first["score_factors"].values()) == first["quality_score"]
        assert first["company"]["company_name"]
        assert first["company"]["is_synthetic"] is True
        assert first["verification_status"] == "unverified"

    def test_results_pagination(self, client, completed_job):
        job_id, job = completed_job
        p1 = client.get(
            f"/api/research/jobs/{job_id}/results", params={"page": 1, "page_size": 3}
        ).json()
        p2 = client.get(
            f"/api/research/jobs/{job_id}/results", params={"page": 2, "page_size": 3}
        ).json()
        assert p1["total"] == p2["total"]
        ids1 = {i["id"] for i in p1["items"]}
        ids2 = {i["id"] for i in p2["items"]}
        assert ids1.isdisjoint(ids2)

    def test_results_filters(self, client, completed_job):
        job_id, _ = completed_job
        high = client.get(
            f"/api/research/jobs/{job_id}/results", params={"min_score": 90}
        ).json()
        assert all(i["quality_score"] >= 90 for i in high["items"])
        low = client.get(
            f"/api/research/jobs/{job_id}/results", params={"max_score": 50}
        ).json()
        assert all(i["quality_score"] <= 50 for i in low["items"])
        searched = client.get(
            f"/api/research/jobs/{job_id}/results", params={"search": "jewelry"}
        ).json()
        assert searched["total"] > 0
        industry = client.get(
            f"/api/research/jobs/{job_id}/results",
            params={"industry": "Jewelry Stores"},
        ).json()
        assert industry["total"] > 0
        assert all(
            i["company"]["industry"] == "Jewelry Stores" for i in industry["items"]
        )

    def test_results_sorting(self, client, completed_job):
        job_id, _ = completed_job
        desc = client.get(
            f"/api/research/jobs/{job_id}/results",
            params={"sort": "quality_score", "order": "desc", "page_size": 100},
        ).json()["items"]
        asc = client.get(
            f"/api/research/jobs/{job_id}/results",
            params={"sort": "quality_score", "order": "asc", "page_size": 100},
        ).json()["items"]
        scores_desc = [i["quality_score"] for i in desc]
        scores_asc = [i["quality_score"] for i in asc]
        assert scores_desc == sorted(scores_desc, reverse=True)
        assert scores_asc == sorted(scores_asc)

    def test_results_unknown_job(self, client):
        resp = client.get("/api/research/jobs/job-missing/results")
        assert resp.status_code == 404
        assert resp.json()["code"] == "job_not_found"

    def test_results_location_filters(self, client, completed_job):
        job_id, _ = completed_job
        first = client.get(f"/api/research/jobs/{job_id}/results").json()["items"][0]
        company = first["company"]
        by_region = client.get(
            f"/api/research/jobs/{job_id}/results",
            params={"region": company["region"]},
        ).json()
        assert by_region["total"] > 0
        assert all(i["company"]["region"] == company["region"] for i in by_region["items"])
        by_city = client.get(
            f"/api/research/jobs/{job_id}/results",
            params={"city": company["city"]},
        ).json()
        assert by_city["total"] > 0
        assert all(i["company"]["city"] == company["city"] for i in by_city["items"])

    def test_results_status_filters(self, client, completed_job):
        job_id, _ = completed_job
        valid = client.get(
            f"/api/research/jobs/{job_id}/results",
            params={"validation_status": "valid"},
        ).json()
        assert valid["total"] > 0
        unverified = client.get(
            f"/api/research/jobs/{job_id}/results",
            params={"verification_status": "unverified"},
        ).json()
        assert unverified["total"] == valid["total"]
        bogus = client.get(
            f"/api/research/jobs/{job_id}/results",
            params={"validation_status": "bogus"},
        ).json()
        assert bogus["total"] == 0

    def test_result_detail(self, client, completed_job):
        job_id, _ = completed_job
        result_id = client.get(f"/api/research/jobs/{job_id}/results").json()["items"][0]["id"]
        resp = client.get(f"/api/research/jobs/{job_id}/results/{result_id}")
        assert resp.status_code == 200
        detail = ResultDetail(**resp.json())  # schema validation
        assert detail.id == result_id
        assert detail.company.normalized_name
        assert detail.dedupe_status in ("unique", "needs_review")

    def test_result_detail_not_found(self, client, completed_job):
        job_id, _ = completed_job
        resp = client.get(f"/api/research/jobs/{job_id}/results/result-missing")
        assert resp.status_code == 404

    def test_delete_result(self, client, completed_job):
        job_id, job = completed_job
        result_id = client.get(f"/api/research/jobs/{job_id}/results").json()["items"][0]["id"]
        resp = client.delete(f"/api/research/jobs/{job_id}/results/{result_id}")
        assert resp.status_code == 204
        assert resp.content == b""
        assert (
            client.get(f"/api/research/jobs/{job_id}/results/{result_id}").status_code
            == 404
        )
        total = client.get(f"/api/research/jobs/{job_id}/results").json()["total"]
        assert total == job["accepted"] - 1

    def test_delete_result_not_found(self, client, completed_job):
        job_id, _ = completed_job
        resp = client.delete(f"/api/research/jobs/{job_id}/results/result-missing")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# validation report
# ---------------------------------------------------------------------------


class TestValidationReport:
    def test_report_shape(self, client):
        job_id = create_job(client).json()["id"]
        job = wait_for(client, job_id)
        resp = client.get(f"/api/research/jobs/{job_id}/validation-report")
        assert resp.status_code == 200
        report = ValidationReport(**resp.json())
        assert report.job_id == job_id
        assert report.total == report.valid + report.invalid + report.duplicates
        assert report.valid == job["accepted"]
        assert report.invalid == job["invalid"]
        assert report.duplicates == job["duplicates"]
        assert isinstance(report.issues_by_field, dict)

    def test_report_unknown_job(self, client):
        resp = client.get("/api/research/jobs/job-missing/validation-report")
        assert resp.status_code == 404

    def test_report_aggregates_issue_codes(self, client, engine):
        from leadforge import models
        from leadforge.db import get_session_factory

        job_id = create_job(client).json()["id"]
        job = wait_for(client, job_id)
        assert job["status"] == "completed"
        with get_session_factory(engine)() as session:
            session.add(
                models.RejectedRecord(
                    job_id=job_id,
                    stage="validate",
                    reason="INVALID_EMAIL; MISSING_COMPANY_NAME",
                    raw_data={"company_name": "Bad Co"},
                )
            )
            session.add(
                models.RejectedRecord(
                    job_id=job_id,
                    stage="validate",
                    reason="INVALID_EMAIL",
                    raw_data={"company_name": "Worse Co"},
                )
            )
            session.commit()
        report = client.get(f"/api/research/jobs/{job_id}/validation-report").json()
        assert report["invalid"] == 2
        assert report["issues_by_field"] == {
            "INVALID_EMAIL": 2,
            "MISSING_COMPANY_NAME": 1,
        }
        assert report["total"] == report["valid"] + 2


class TestErrorHandling:
    def test_not_runnable_maps_to_409(self, engine, monkeypatch):
        import leadforge.api as api_module
        from leadforge.pipeline.runner import JobNotRunnableError

        def refuse(session, job_id):
            raise JobNotRunnableError("job 'x' is 'completed'")

        monkeypatch.setattr(api_module.job_service, "get_job", refuse)
        app = create_app(engine=engine)
        with TestClient(app, raise_server_exceptions=False) as quiet_client:
            resp = quiet_client.get("/api/research/jobs/job-1")
        assert resp.status_code == 409
        body = resp.json()
        assert body["code"] == "job_not_runnable"
        assert "completed" in body["detail"]

    def test_unhandled_error_is_generic(self, engine, monkeypatch):
        import leadforge.api as api_module

        def boom(session, job_id):
            raise RuntimeError("secret stack trace content")

        monkeypatch.setattr(api_module.job_service, "get_job", boom)
        app = create_app(engine=engine)
        with TestClient(app, raise_server_exceptions=False) as quiet_client:
            resp = quiet_client.get("/api/research/jobs/job-1")
        assert resp.status_code == 500
        body = resp.json()
        assert body == {"detail": "Internal server error.", "code": "internal_error"}
        assert "secret stack trace" not in resp.text

    def test_providers_health_database_error(self):
        from leadforge.db import build_engine

        broken = build_engine(
            "sqlite:///file:/tmp/leadforge_no_such_db_xyz123.db?mode=ro&uri=true"
        )
        app = create_app(engine=broken)
        # No lifespan: init_db would fail on the bad path before we get here.
        client = TestClient(app)
        try:
            body = client.get("/api/providers/health").json()
        finally:
            client.close()
            broken.dispose()
        assert body["database"]["status"] == "error"
        assert "detail" in body["database"]
