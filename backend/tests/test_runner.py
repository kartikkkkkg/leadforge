"""Pipeline orchestration tests: DISCOVER -> NORMALIZE -> VALIDATE ->
DEDUPLICATE -> SCORE -> STORE, job lifecycle, transactions.

All tests use deterministic stub/demo providers and isolated in-memory
databases. No network.
"""

import asyncio

import pytest

from leadforge import models
from leadforge.db import session_scope
from leadforge.pipeline.runner import (
    JobNotFoundError,
    JobNotRunnableError,
    JobResult,
    PipelineRunner,
)
from leadforge.providers import (
    CompanyQuery,
    ContactInfo,
    ProviderError,
    RawCompany,
    ResearchProvider,
)
from leadforge.schemas import JobCreate, ProviderHealth
from leadforge.services import jobs as job_service


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


class StubProvider(ResearchProvider):
    """Deterministic test provider with canned records."""

    name = "stub"

    def __init__(self, records=None, error=None):
        self._records = [RawCompany(**r) for r in (records or [])]
        self._error = error

    async def search_companies(self, query: CompanyQuery, limit: int):
        if self._error is not None:
            raise self._error
        return self._records[:limit]

    async def get_company_details(self, ref: str):
        return None

    def extract_contacts(self, raw: RawCompany) -> ContactInfo:
        return ContactInfo(email=raw.public_email, phone=raw.phone)

    def health(self) -> ProviderHealth:
        return ProviderHealth(name="stub", status="available", detail="test stub")


def good_record(**overrides):
    base = {
        "company_name": "Acme Jewelry LLC",
        "website": "https://www.acme-jewelry.example.com/",
        "industry": "Jewelry Stores",
        "country": "United States",
        "region": "Texas",
        "city": "Austin",
        "address": "100 Meridian Ave, Austin, Texas",
        "phone": "+1-555-0100",
        "public_email": "info@acme-jewelry.example.com",
        "source_provider": "stub",
    }
    base.update(overrides)
    return base


def make_job(engine, **overrides):
    params = {
        "industry": "Jewelry Stores",
        "country": "United States",
        "requested_leads": 10,
    }
    params.update(overrides)
    with session_scope(engine) as session:
        job = job_service.create_job(session, JobCreate(**params))
        return job.id


def run(engine, job_id, **kwargs):
    kwargs.setdefault("delay_ms", 0)
    return asyncio.run(job_service.run_job(job_id, engine=engine, **kwargs))


def count(engine, model):
    with session_scope(engine) as session:
        return session.query(model).count()


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------


class TestSuccessfulJob:
    def test_demo_job_completes(self, engine):
        job_id = make_job(engine, requested_leads=10)
        result = run(engine, job_id)

        assert isinstance(result, JobResult)
        assert result.status == "completed"
        assert result.discovered == 10
        assert result.accepted + result.duplicates + result.invalid == 10
        assert count(engine, models.Company) == result.accepted
        assert count(engine, models.LeadResearchResult) == result.accepted

    def test_job_row_lifecycle(self, engine):
        job_id = make_job(engine, requested_leads=10)
        with session_scope(engine) as session:
            assert session.get(models.ResearchJob, job_id).status == "queued"

        run(engine, job_id)

        progress = job_service.job_progress(_fresh_session(engine), job_id)
        assert progress["status"] == "completed"
        assert progress["stage"] == "DONE"
        assert progress["progress_pct"] == 100
        assert progress["error"] is None
        assert progress["discovered"] == 10

    def test_progress_stage_sequence(self, engine):
        job_id = make_job(engine, requested_leads=10)
        seen = []
        run(engine, job_id, on_progress=lambda stage, snap: seen.append(stage))
        assert seen == [
            "DISCOVER",
            "NORMALIZE",
            "VALIDATE",
            "DEDUPLICATE",
            "SCORE",
            "STORE",
            "DONE",
        ]

    def test_normalization_integration(self, engine):
        job_id = make_job(engine, requested_leads=10)
        run(engine, job_id)
        with session_scope(engine) as session:
            companies = session.query(models.Company).all()
            assert companies
            for company in companies:
                assert company.normalized_name  # lowercased, trimmed
                assert company.normalized_name == company.normalized_name.strip()
                if company.website:
                    assert company.normalized_domain
                    assert "://" not in company.normalized_domain

    def test_completeness_scoring_persisted(self, engine):
        provider = StubProvider([good_record()])
        job_id = make_job(engine, requested_leads=10)
        run(engine, job_id, provider=provider)
        with session_scope(engine) as session:
            result = session.query(models.LeadResearchResult).one()
            assert result.quality_score == 100
            assert sum(result.score_factors.values()) == 100
            assert result.validation_status == "valid"
            assert result.verification_status == "unverified"
            assert result.ai_enriched is False
            assert result.dedupe_status == "unique"

    def test_sparse_record_scores_lower(self, engine):
        sparse = good_record(
            company_name="Sparse Co",
            website=None,
            phone=None,
            public_email=None,
        )
        provider = StubProvider([sparse])
        job_id = make_job(engine, requested_leads=10)
        run(engine, job_id, provider=provider)
        with session_scope(engine) as session:
            result = session.query(models.LeadResearchResult).one()
            assert result.quality_score < 100
            assert sum(result.score_factors.values()) == result.quality_score

    def test_empty_discovery_completes(self, engine):
        job_id = make_job(engine, requested_leads=10)
        result = run(engine, job_id, provider=StubProvider([]))
        assert result.status == "completed"
        assert result.discovered == 0
        assert result.accepted == 0
        assert count(engine, models.Company) == 0


class TestServiceHelpers:
    def test_get_job_found_and_missing(self, engine):
        job_id = make_job(engine)
        session = _fresh_session(engine)
        assert job_service.get_job(session, job_id).id == job_id
        assert job_service.get_job(session, "job-missing") is None

    def test_job_progress_missing(self, engine):
        assert job_service.job_progress(_fresh_session(engine), "job-missing") is None

    def test_run_job_uses_job_delay_when_not_given(self, engine):
        # delay_ms=None -> reads job.demo_delay_ms (default 120); the delay
        # applies per stage, so just assert the run still completes.
        job_id = make_job(engine)
        result = asyncio.run(
            job_service.run_job(
                job_id, engine=engine, provider=StubProvider([good_record()])
            )
        )
        assert result.status == "completed"

    def test_run_job_unknown_id_without_delay(self, engine):
        with pytest.raises(JobNotFoundError):
            asyncio.run(job_service.run_job("job-missing", engine=engine))


def _fresh_session(engine):
    """A usable session for job_progress reads."""
    from sqlalchemy.orm import Session as SASession

    return SASession(bind=engine)


# ---------------------------------------------------------------------------
# validation / rejection
# ---------------------------------------------------------------------------


class TestValidationIntegration:
    @pytest.fixture
    def dirty_provider(self):
        return StubProvider(
            [
                good_record(),
                good_record(company_name=None),  # MISSING_COMPANY_NAME
                good_record(company_name=""),  # MISSING_COMPANY_NAME (blank)
                good_record(public_email="not-an-email"),  # INVALID_EMAIL
                good_record(website="https://exa mple.com"),  # INVALID_DOMAIN
                good_record(country=None),  # MISSING_LOCATION
            ]
        )

    def test_invalid_records_rejected(self, engine, dirty_provider):
        job_id = make_job(engine, requested_leads=10)
        result = run(engine, job_id, provider=dirty_provider)

        assert result.status == "completed"
        assert result.discovered == 6
        assert result.accepted == 1
        assert result.invalid == 5
        assert count(engine, models.Company) == 1
        assert count(engine, models.RejectedRecord) == 5

    def test_rejection_rows_carry_codes(self, engine, dirty_provider):
        job_id = make_job(engine, requested_leads=10)
        run(engine, job_id, provider=dirty_provider)
        with session_scope(engine) as session:
            rejected = (
                session.query(models.RejectedRecord)
                .filter_by(job_id=job_id, stage="validate")
                .all()
            )
            codes = {r.reason for r in rejected}
            assert codes == {
                "MISSING_COMPANY_NAME",
                "INVALID_EMAIL",
                "INVALID_DOMAIN",
                "MISSING_LOCATION",
            }
            for row in rejected:
                # The original raw record is preserved for debugging.
                assert isinstance(row.raw_data, dict)
                assert "company_name" in row.raw_data
            names = {
                r.raw_data.get("company_name")
                for r in session.query(models.RejectedRecord)
                .filter_by(job_id=job_id, stage="validate")
                .all()
            }
            assert None in names  # the missing-name record kept its raw form


# ---------------------------------------------------------------------------
# deduplication
# ---------------------------------------------------------------------------


class TestDeduplicationIntegration:
    def test_exact_domain_duplicates_removed(self, engine):
        provider = StubProvider(
            [
                good_record(company_name="Dupe One LLC"),
                good_record(company_name="Dupe Two LLC"),  # same website
            ]
        )
        job_id = make_job(engine, requested_leads=10)
        result = run(engine, job_id, provider=provider)

        assert result.accepted == 1
        assert result.duplicates == 1
        assert count(engine, models.Company) == 1
        with session_scope(engine) as session:
            rejected = (
                session.query(models.RejectedRecord)
                .filter_by(job_id=job_id, stage="deduplicate")
                .one()
            )
            assert "exact_domain" in rejected.reason

    def test_fuzzy_match_needs_review_not_removed(self, engine):
        provider = StubProvider(
            [
                good_record(
                    company_name="Harbor Jewelry LLC",
                    website=None,
                    public_email=None,
                    city=None,
                ),
                good_record(
                    company_name="Harbor Jewelry Llc.",
                    website=None,
                    public_email=None,
                    city=None,
                ),
            ]
        )
        job_id = make_job(engine, requested_leads=10)
        result = run(engine, job_id, provider=provider)

        assert result.accepted == 2  # never silently removed
        assert result.duplicates == 0
        assert result.needs_review == 1
        with session_scope(engine) as session:
            statuses = sorted(
                r.dedupe_status
                for r in session.query(models.LeadResearchResult)
                .filter_by(job_id=job_id)
                .all()
            )
            assert statuses == ["needs_review", "unique"]


# ---------------------------------------------------------------------------
# failures, transactions, idempotency
# ---------------------------------------------------------------------------


class TestFailures:
    def test_unknown_provider_fails_job(self, engine):
        job_id = make_job(engine, provider="nonsense", requested_leads=10)
        with pytest.raises(ValueError, match="unknown provider"):
            run(engine, job_id)
        progress = job_service.job_progress(_fresh_session(engine), job_id)
        assert progress["status"] == "failed"
        assert "unknown provider" in progress["error"]
        assert count(engine, models.Company) == 0

    def test_unconfigured_http_provider_fails_job(self, engine):
        job_id = make_job(engine, provider="http", requested_leads=10)
        with pytest.raises(Exception, match="not configured"):
            run(engine, job_id)
        progress = job_service.job_progress(_fresh_session(engine), job_id)
        assert progress["status"] == "failed"
        assert count(engine, models.Company) == 0

    def test_provider_error_fails_job_without_partial_state(self, engine):
        provider = StubProvider(error=ProviderError("provider exploded"))
        job_id = make_job(engine, requested_leads=10)
        with pytest.raises(ProviderError, match="provider exploded"):
            run(engine, job_id, provider=provider)
        progress = job_service.job_progress(_fresh_session(engine), job_id)
        assert progress["status"] == "failed"
        assert "ProviderError: provider exploded" in progress["error"]
        assert count(engine, models.Company) == 0
        assert count(engine, models.LeadResearchResult) == 0
        assert count(engine, models.RejectedRecord) == 0

    def test_store_failure_rolls_back(self, engine, monkeypatch):
        async def evil_store(self, spec, *args, **kwargs):
            with session_scope(self._engine) as session:
                session.add(models.Company(company_name="Partial Corp"))
                raise RuntimeError("boom mid-store")

        monkeypatch.setattr(PipelineRunner, "_store", evil_store)
        job_id = make_job(engine, requested_leads=10)
        with pytest.raises(RuntimeError, match="boom mid-store"):
            run(engine, job_id)
        # The partial company was rolled back with the store transaction.
        assert count(engine, models.Company) == 0
        assert count(engine, models.LeadResearchResult) == 0
        assert count(engine, models.RejectedRecord) == 0
        progress = job_service.job_progress(_fresh_session(engine), job_id)
        assert progress["status"] == "failed"
        assert "boom mid-store" in progress["error"]

    def test_unknown_job(self, engine):
        with pytest.raises(JobNotFoundError):
            run(engine, "job-does-not-exist")

    def test_rerun_completed_job_refused(self, engine):
        provider = StubProvider([good_record()])
        job_id = make_job(engine, requested_leads=10)
        run(engine, job_id, provider=provider)
        assert count(engine, models.Company) == 1
        with pytest.raises(JobNotRunnableError, match="completed"):
            run(engine, job_id, provider=provider)
        # No duplicate companies from the refused re-run.
        assert count(engine, models.Company) == 1

    def test_failed_job_can_be_retried(self, engine):
        job_id = make_job(engine, provider="http", requested_leads=10)
        with pytest.raises(Exception, match="not configured"):
            run(engine, job_id)
        # Retry with a working provider override succeeds.
        result = run(engine, job_id, provider=StubProvider([good_record()]))
        assert result.status == "completed"
        assert result.accepted == 1
