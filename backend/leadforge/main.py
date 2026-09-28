"""FastAPI application factory, routers, error handlers."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .api import router
from .config import get_settings
from .db import build_engine, init_db
from .pipeline.runner import JobNotFoundError, JobNotRunnableError
from .providers import NotConfiguredError
from .schemas import ErrorResponse

log = logging.getLogger(__name__)


def _error(status_code: int, detail: str, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(detail=detail, code=code).model_dump(),
    )


def create_app(engine=None) -> FastAPI:
    """Build the LeadForge FastAPI application.

    Pass ``engine`` in tests to use an isolated database; otherwise the
    engine is built from the project configuration (SQLite by default,
    PostgreSQL when ``DATABASE_URL`` is set).
    """
    eng = engine or build_engine()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(eng)
        yield

    app = FastAPI(
        title="LeadForge",
        description=(
            "Automated B2B lead research & data enrichment. "
            "Create a research job, poll it while the pipeline runs "
            "(discover → normalize → validate → deduplicate → score → store), "
            "then browse the results. Demo mode works fully offline with "
            "synthetic data (always flagged `is_synthetic`)."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.engine = eng
    app.state.settings = get_settings()
    app.include_router(router)

    @app.exception_handler(JobNotFoundError)
    async def job_not_found(request: Request, exc: JobNotFoundError) -> JSONResponse:
        return _error(404, str(exc), "job_not_found")

    @app.exception_handler(JobNotRunnableError)
    async def job_not_runnable(
        request: Request, exc: JobNotRunnableError
    ) -> JSONResponse:
        return _error(409, str(exc), "job_not_runnable")

    @app.exception_handler(NotConfiguredError)
    async def provider_not_configured(
        request: Request, exc: NotConfiguredError
    ) -> JSONResponse:
        return _error(400, str(exc), "provider_not_configured")

    @app.exception_handler(ValueError)
    async def invalid_request(request: Request, exc: ValueError) -> JSONResponse:
        return _error(400, str(exc), "invalid_request")

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Never leak internals: log server-side, return a generic message.
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return _error(500, "Internal server error.", "internal_error")

    return app


# `uvicorn leadforge.main:app` entrypoint.
app = create_app()
