"""API routers: health, providers, research jobs, results.

Thin HTTP layer over the existing service/pipeline/provider code — no
business logic lives in route handlers. Every error response uses the
``ErrorResponse`` schema (``{detail, code}``); credentials, connection
strings, and stack traces never leave the server.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from . import models
from .ai import get_ai_provider
from .db import session_scope
from .pipeline.runner import JobNotFoundError
from .providers import DemoProvider, HttpApiProvider, NotConfiguredError, get_provider
from .schemas import (
    DemoResetRequest,
    DemoResetResponse,
    DemoSeedResponse,
    HealthResponse,
    JobCreate,
    JobList,
    JobRead,
    ProviderHealth,
    ProvidersHealth,
    ResultDetail,
    ResultsPage,
    ValidationReport,
)
from .services import demo as demo_service
from .services import jobs as job_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# dependencies & background execution
# ---------------------------------------------------------------------------


def get_session(request: Request) -> Iterator[Session]:
    """Per-request database session (commit on success, rollback on error)."""
    with session_scope(request.app.state.engine) as session:
        yield session


async def _run_job_in_background(engine, job_id: str) -> None:
    """Execute the pipeline outside the request cycle.

    The runner records failures on the job row itself; anything escaping is
    logged server-side (never swallowed silently, never leaked to clients).
    """
    try:
        await job_service.run_job(job_id, engine=engine)
    except Exception:
        log.exception("background job %s raised (failure recorded on job)", job_id)


def _require_job(session: Session, job_id: str) -> models.ResearchJob:
    job = job_service.get_job(session, job_id)
    if job is None:
        raise JobNotFoundError(f"no research job {job_id!r}")
    return job


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health",
    description="Liveness check. Always returns `{\"status\": \"ok\"}` when the "
    "service is up; does not probe dependencies (see /providers/health).",
)
def health() -> HealthResponse:
    return HealthResponse()


@router.get(
    "/providers/health",
    response_model=ProvidersHealth,
    summary="Provider health",
    description="Health of every provider plus the database. A provider is "
    "only reported `available` after an actual check; unconfigured providers "
    "report `not_configured` (never `available`, never `offline`).",
)
def providers_health(request: Request) -> ProvidersHealth:
    try:
        # Touch a real table: SELECT 1 never opens the SQLite file, so it
        # cannot detect an unreachable database.
        with session_scope(request.app.state.engine) as session:
            session.execute(text("SELECT COUNT(*) FROM research_jobs"))
        database = ProviderHealth(
            name="database", status="available", detail="Database reachable."
        )
    except Exception as exc:
        log.warning("database health check failed: %s", exc)
        database = ProviderHealth(
            name="database", status="error", detail="Database unreachable."
        )
    """AI health is honest about configuration: ``configured`` means an API key is
    present (no probe call is made — the provider is only contacted during a
    job that requested AI); ``not_configured`` means the disabled default
    NullAIProvider is active and the app is fully usable without AI.
    """
    ai_provider = get_ai_provider()
    if ai_provider.enabled:
        ai = ProviderHealth(
            name="ai",
            status="configured",
            detail=(
                "AI enrichment is enabled (LLM API key configured). The "
                "provider is only contacted for jobs created with AI "
                "enrichment enabled; no probe call was made."
            ),
        )
    else:
        ai = ProviderHealth(
            name="ai",
            status="not_configured",
            detail=(
                "AI enrichment is not configured (NullAIProvider default). "
                "Jobs run normally with no AI-derived fields."
            ),
        )
    return ProvidersHealth(
        demo=DemoProvider().health(),
        http=HttpApiProvider().health(),
        ai=ai,
        database=database,
    )


# ---------------------------------------------------------------------------
# demo dataset management
# ---------------------------------------------------------------------------


@router.post(
    "/demo/seed",
    response_model=DemoSeedResponse,
    summary="Seed the synthetic demo dataset",
    description="Insert the deterministic 100-company synthetic dataset "
    "(the same generator DemoProvider uses) into the companies table. "
    "Idempotent: existing synthetic companies are replaced, never duplicated. "
    "All data is synthetic and labeled as such.",
)
def demo_seed(session: Session = Depends(get_session)) -> DemoSeedResponse:
    count = demo_service.seed_demo_companies(session)
    return DemoSeedResponse(companies=count)


@router.post(
    "/demo/reset",
    response_model=DemoResetResponse,
    summary="Reset demo data",
    description="Wipe all demo data: research jobs (with their results and "
    "rejected records) and companies. Pass `{\"reseed\": true}` to re-seed "
    "the synthetic dataset afterwards.",
)
def demo_reset(
    payload: DemoResetRequest | None = None,
    session: Session = Depends(get_session),
) -> DemoResetResponse:
    reseed = payload.reseed if payload is not None else False
    outcome = demo_service.reset_demo_data(session, reseed=reseed)
    return DemoResetResponse(**outcome)


# ---------------------------------------------------------------------------
# research jobs
# ---------------------------------------------------------------------------


@router.post(
    "/research/jobs",
    response_model=JobRead,
    status_code=202,
    summary="Create a research job",
    description="Validate the request, create a `queued` ResearchJob, and start "
    "the pipeline in the background. Returns 202 immediately — the request "
    "never blocks. Poll `GET /research/jobs/{id}` for progress. Unknown "
    "providers and unconfigured providers are rejected with 400.",
)
def create_research_job(
    payload: JobCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    session: Session = Depends(get_session),
) -> models.ResearchJob:
    # Unknown names raise ValueError -> 400 invalid_request via the error handler.
    provider = get_provider(payload.provider)
    if isinstance(provider, HttpApiProvider) and not provider.is_configured:
        raise NotConfiguredError(
            "HTTP provider is not configured: set LEADFORGE_HTTP_API_BASE_URL "
            "and LEADFORGE_HTTP_API_KEY."
        )
    job = job_service.create_job(session, payload)
    # Commit NOW: background tasks run before this request's session
    # finalizer, so the job row must be visible to the background task.
    session.commit()
    background_tasks.add_task(
        _run_job_in_background, request.app.state.engine, job.id
    )
    return job


@router.get(
    "/research/jobs",
    response_model=JobList,
    summary="List research jobs",
    description="Recent jobs first. Paginated.",
)
def list_research_jobs(
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    session: Session = Depends(get_session),
) -> dict:
    total = session.query(func.count(models.ResearchJob.id)).scalar() or 0
    items = (
        session.query(models.ResearchJob)
        .order_by(models.ResearchJob.created_at.desc(), models.ResearchJob.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get(
    "/research/jobs/{job_id}",
    response_model=JobRead,
    summary="Get a research job",
    description="Full job representation including live pipeline counters, "
    "current stage, and progress milestone. Poll this while a job runs.",
)
def get_research_job(
    job_id: str, session: Session = Depends(get_session)
) -> models.ResearchJob:
    return _require_job(session, job_id)


# ---------------------------------------------------------------------------
# results
# ---------------------------------------------------------------------------

_SORT_COLUMNS = {
    "quality_score": models.LeadResearchResult.quality_score,
    "company_name": models.Company.company_name,
    "created_at": models.LeadResearchResult.collected_at,
}


@router.get(
    "/research/jobs/{job_id}/results",
    response_model=ResultsPage,
    summary="List job results",
    description="Paginated, filterable results table for a job. `progress_pct` "
    "on the job is a coarse stage milestone — the counters here are the exact "
    "numbers. Ordering is deterministic (id tiebreaker).",
)
def list_job_results(
    job_id: str,
    search: str | None = Query(default=None, description="Matches name, website, city"),
    industry: str | None = Query(default=None),
    region: str | None = Query(default=None),
    city: str | None = Query(default=None),
    min_score: int | None = Query(default=None, ge=0, le=100),
    max_score: int | None = Query(default=None, ge=0, le=100),
    validation_status: str | None = Query(default=None),
    verification_status: str | None = Query(default=None),
    sort: Literal["quality_score", "company_name", "created_at"] = Query(
        default="quality_score"
    ),
    order: Literal["asc", "desc"] = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict:
    _require_job(session, job_id)
    query = (
        session.query(models.LeadResearchResult)
        .join(
            models.Company,
            models.LeadResearchResult.company_id == models.Company.id,
        )
        .filter(models.LeadResearchResult.job_id == job_id)
    )
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                models.Company.company_name.ilike(like),
                models.Company.website.ilike(like),
                models.Company.city.ilike(like),
            )
        )
    if industry:
        query = query.filter(models.Company.industry == industry)
    if region:
        query = query.filter(models.Company.region == region)
    if city:
        query = query.filter(models.Company.city == city)
    if min_score is not None:
        query = query.filter(models.LeadResearchResult.quality_score >= min_score)
    if max_score is not None:
        query = query.filter(models.LeadResearchResult.quality_score <= max_score)
    if validation_status:
        query = query.filter(
            models.LeadResearchResult.validation_status == validation_status
        )
    if verification_status:
        query = query.filter(
            models.LeadResearchResult.verification_status == verification_status
        )

    total = query.count()
    sort_col = _SORT_COLUMNS[sort]
    query = query.order_by(
        sort_col.desc() if order == "desc" else sort_col.asc(),
        models.Company.id.asc(),  # deterministic tiebreaker
    )
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get(
    "/research/jobs/{job_id}/results/{result_id}",
    response_model=ResultDetail,
    summary="Get a result record",
    description="Full detail for one result: company (raw + normalized), "
    "completeness score and factor breakdown, source/provider, validation and "
    "dedupe status. Validation is not verification.",
)
def get_job_result(
    job_id: str, result_id: str, session: Session = Depends(get_session)
) -> models.LeadResearchResult:
    _require_job(session, job_id)
    result = (
        session.query(models.LeadResearchResult)
        .filter(
            models.LeadResearchResult.id == result_id,
            models.LeadResearchResult.job_id == job_id,
        )
        .one_or_none()
    )
    if result is None:
        raise JobNotFoundError(f"no result {result_id!r} for job {job_id!r}")
    return result


@router.delete(
    "/research/jobs/{job_id}/results/{result_id}",
    status_code=204,
    summary="Delete a result record",
    description="Deletes the result and its company (companies are per-job, "
    "so nothing else references it). Returns 204 with no body.",
)
def delete_job_result(
    job_id: str, result_id: str, session: Session = Depends(get_session)
) -> Response:
    _require_job(session, job_id)
    result = (
        session.query(models.LeadResearchResult)
        .filter(
            models.LeadResearchResult.id == result_id,
            models.LeadResearchResult.job_id == job_id,
        )
        .one_or_none()
    )
    if result is None:
        raise JobNotFoundError(f"no result {result_id!r} for job {job_id!r}")
    # Delete the result row before its company: Company.lead_results carries
    # no ORM cascade, so deleting the company first would make SQLAlchemy
    # null out lead_results.company_id (NOT NULL). DB-level ON DELETE CASCADE
    # is a backup, not the ORM path.
    company = result.company
    session.delete(result)
    session.delete(company)
    return Response(status_code=204)


@router.get(
    "/research/jobs/{job_id}/validation-report",
    response_model=ValidationReport,
    summary="Validation report",
    description="Counts of valid / invalid / duplicate records for a job, plus "
    "rejection issue codes (e.g. INVALID_EMAIL) and their frequencies. Keys "
    "in `issues_by_field` are stable UPPER_SNAKE issue codes.",
)
def validation_report(
    job_id: str, session: Session = Depends(get_session)
) -> dict:
    _require_job(session, job_id)
    valid = (
        session.query(func.count(models.LeadResearchResult.id))
        .filter(models.LeadResearchResult.job_id == job_id)
        .scalar()
        or 0
    )
    rejected = (
        session.query(models.RejectedRecord)
        .filter(models.RejectedRecord.job_id == job_id)
        .all()
    )
    invalid_rows = [r for r in rejected if r.stage == "validate"]
    duplicate_rows = [r for r in rejected if r.stage == "deduplicate"]
    issues_by_field: dict[str, int] = {}
    for row in invalid_rows:
        for code in row.reason.split("; "):
            code = code.strip()
            if code:
                issues_by_field[code] = issues_by_field.get(code, 0) + 1
    return {
        "job_id": job_id,
        "total": valid + len(invalid_rows) + len(duplicate_rows),
        "valid": valid,
        "invalid": len(invalid_rows),
        "duplicates": len(duplicate_rows),
        "issues_by_field": issues_by_field,
    }
