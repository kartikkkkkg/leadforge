"""Tests for the Pydantic schemas (Phase 3)."""

import pytest
from pydantic import ValidationError

from leadforge import models, schemas
from tests.fixtures import make_company, make_job, make_result


def test_job_create_valid():
    job = schemas.JobCreate(
        industry="Jewelry Stores",
        country="United States",
        region="California",
        requested_leads=100,
    )
    assert job.provider == "demo"
    assert job.enable_ai is False
    assert job.demo_delay_ms == 120
    assert job.city is None


def test_job_create_rejects_bad_lead_count():
    with pytest.raises(ValidationError):
        schemas.JobCreate(industry="X", country="Y", requested_leads=7)


def test_job_create_requires_industry_and_country():
    with pytest.raises(ValidationError):
        schemas.JobCreate(industry="", country="United States")
    with pytest.raises(ValidationError):
        schemas.JobCreate(industry="Jewelry Stores")


def test_job_read_from_orm(session):
    job = make_job()
    session.add(job)
    session.flush()
    read = schemas.JobRead.model_validate(job)
    assert read.id == job.id
    assert read.industry == "Jewelry Stores"
    assert read.status == "queued"
    assert read.created_at == job.created_at


def test_result_read_from_orm(session):
    job = make_job()
    company = make_company()
    result = make_result(job, company)
    session.add_all([job, company, result])
    session.flush()
    read = schemas.ResultRead.model_validate(result)
    assert read.company.company_name == "ABC Jewelry LLC"
    assert read.quality_score == 85
    assert read.score_factors["website"] == 20
    assert read.verification_status == "unverified"
    assert read.dedupe_status == "unique"


def test_validation_issue_schema():
    issue = schemas.ValidationIssue(
        field="public_email", code="invalid_email", message="Not a valid email."
    )
    assert issue.code == "invalid_email"


def test_providers_health_schema():
    health = schemas.ProvidersHealth(
        demo=schemas.ProviderHealth(name="demo", status="available", detail="100 synthetic companies"),
        http=schemas.ProviderHealth(name="http", status="not_configured", detail="LEADFORGE_HTTP_API_KEY not set"),
        ai=schemas.ProviderHealth(name="ai", status="disabled", detail="LEADFORGE_AI_ENABLED=false"),
        database=schemas.ProviderHealth(name="database", status="available", detail="sqlite"),
    )
    assert health.ai.status == "disabled"


def test_error_response_defaults():
    err = schemas.ErrorResponse(detail="Job not found")
    assert err.code == "error"
    assert err.detail == "Job not found"


def test_validation_report_schema():
    report = schemas.ValidationReport(
        job_id="abc", total=100, valid=90, invalid=4, duplicates=6,
        issues_by_field={"public_email": 3, "website": 1},
    )
    assert report.total == report.valid + report.invalid + report.duplicates
