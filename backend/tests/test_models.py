"""Tests for the SQLAlchemy models: defaults, relationships, constraints (Phase 3)."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from leadforge import models
from tests.fixtures import make_company, make_job, make_result


def test_job_defaults(session):
    job = make_job()
    session.add(job)
    session.flush()
    assert uuid.UUID(job.id)  # valid UUID string
    assert job.status == "queued"
    assert job.provider == "demo"
    assert job.enable_ai is False
    assert job.progress_pct == 0
    assert (job.discovered, job.processed, job.accepted, job.duplicates, job.invalid) == (0, 0, 0, 0, 0)
    assert job.created_at is not None
    assert job.completed_at is None
    assert job.error is None


def test_job_requires_industry_and_country(session):
    session.add(make_job(industry=None))
    with pytest.raises(IntegrityError):
        session.flush()


def test_company_result_relationship(session):
    job = make_job()
    company = make_company()
    result = make_result(job, company)
    session.add_all([job, company, result])
    session.flush()

    assert result.job_id == job.id
    assert result.company_id == company.id
    assert job.results[0] is result
    assert result.company.company_name == "ABC Jewelry LLC"
    assert company.lead_results[0] is result


def test_json_fields_round_trip(session):
    job = make_job()
    company = make_company()
    factors = {"website": 20, "company_name": 20, "location": 15,
               "phone": 0, "public_email": 20, "source": 10}
    issues = [{"field": "phone", "code": "missing_required", "message": "Phone is missing."}]
    result = make_result(job, company, quality_score=75,
                         score_factors=factors, validation_status="invalid",
                         validation_issues=issues,
                         ai_fields={"summary": {"value": "Jewelry retailer.", "ai_derived": True}})
    session.add_all([job, company, result])
    session.commit()

    loaded = session.get(models.LeadResearchResult, result.id)
    assert loaded.score_factors == factors
    assert loaded.validation_issues == issues
    assert loaded.ai_fields["summary"]["ai_derived"] is True
    assert loaded.quality_score == 75


def test_rejected_record_linked_to_job(session):
    job = make_job()
    rejected = models.RejectedRecord(
        job=job,
        stage="validate",
        reason="public_email 'john@@example..com' is not a valid email address",
        raw_data={"company_name": "Bad Email Co", "public_email": "john@@example..com"},
    )
    session.add_all([job, rejected])
    session.flush()

    assert rejected.job_id == job.id
    assert job.rejected_records[0] is rejected
    assert rejected.raw_data["public_email"] == "john@@example..com"


def test_uuid_primary_keys_are_unique(session):
    jobs = [make_job() for _ in range(3)]
    session.add_all(jobs)
    session.flush()
    ids = [j.id for j in jobs]
    assert len(set(ids)) == 3
    for i in ids:
        uuid.UUID(i)


def test_dedupe_self_reference(session):
    job = make_job()
    original = make_company(company_name="Original Co")
    duplicate = make_company(company_name="Original Co LLC",
                             normalized_domain="original-co.example.com")
    result = make_result(job, duplicate, dedupe_status="duplicate_removed")
    result.duplicate_of = original
    session.add_all([job, original, duplicate, result])
    session.flush()
    assert result.duplicate_of_id == original.id


def test_company_nullable_fields(session):
    sparse = models.Company(company_name="Sparse Co")
    session.add(sparse)
    session.flush()
    assert sparse.website is None
    assert sparse.normalized_domain is None
    assert sparse.is_synthetic is False
    assert sparse.source_provider == "demo"
