"""Job lifecycle service: create, run, progress, complete.

Thin service layer over :class:`PipelineRunner` — this is what the API
(Phase 7) will call. Lifecycle uses the statuses already defined on the
``ResearchJob`` model: ``queued -> running -> completed | failed``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .. import models
from ..db import get_engine, session_scope
from ..pipeline.runner import (
    JobNotFoundError,
    JobNotRunnableError,
    JobResult,
    PipelineRunner,
    ProgressCallback,
)
from ..providers import ResearchProvider
from ..schemas import JobCreate

__all__ = [
    "JobNotFoundError",
    "JobNotRunnableError",
    "JobResult",
    "create_job",
    "get_job",
    "job_progress",
    "run_job",
]


def create_job(session: Session, job_create: JobCreate) -> models.ResearchJob:
    """Create a research job in ``queued`` status. Caller commits."""
    job = models.ResearchJob(
        industry=job_create.industry,
        country=job_create.country,
        region=job_create.region,
        city=job_create.city,
        keywords=job_create.keywords,
        requested_leads=job_create.requested_leads,
        provider=job_create.provider,
        enable_ai=job_create.enable_ai,
        demo_delay_ms=job_create.demo_delay_ms,
        status="queued",
    )
    session.add(job)
    session.flush()  # assign job.id
    return job


def get_job(session: Session, job_id: str) -> models.ResearchJob | None:
    """Fetch a job by id (or ``None``)."""
    return session.get(models.ResearchJob, job_id)


def job_progress(session: Session, job_id: str) -> dict[str, Any] | None:
    """Deterministic progress snapshot: stage, milestone %, and real counters.

    Returns ``None`` when the job does not exist.
    """
    job = session.get(models.ResearchJob, job_id)
    if job is None:
        return None
    return {
        "job_id": job.id,
        "status": job.status,
        "stage": job.stage,
        "progress_pct": job.progress_pct,
        "discovered": job.discovered,
        "processed": job.processed,
        "accepted": job.accepted,
        "duplicates": job.duplicates,
        "invalid": job.invalid,
        "error": job.error,
    }


async def run_job(
    job_id: str,
    engine=None,
    provider: ResearchProvider | None = None,
    delay_ms: int | None = None,
    on_progress: ProgressCallback | None = None,
) -> JobResult:
    """Execute the pipeline for ``job_id``.

    * ``provider`` overrides the job's configured provider (tests, ops).
    * ``delay_ms`` overrides the job's ``demo_delay_ms`` (tests use 0).
    * Re-raises after recording the failure on the job — never swallows.
    """
    eng = engine or get_engine()
    if delay_ms is None:
        with session_scope(eng) as session:
            job = session.get(models.ResearchJob, job_id)
            if job is None:
                raise JobNotFoundError(f"no research job {job_id!r}")
            delay_ms = job.demo_delay_ms
    runner = PipelineRunner(
        engine=eng,
        provider=provider,
        delay_ms=delay_ms,
        on_progress=on_progress,
    )
    return await runner.run(job_id)
