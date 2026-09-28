"""Pydantic request/response schemas for the LeadForge API contract (DESIGN.md §4).

Foundational models for job creation, job reads, companies, lead results,
validation, scoring, provider health, and errors. API routes arrive in Phase 6.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Research jobs
# ---------------------------------------------------------------------------


class JobCreate(BaseModel):
    """POST /api/research/jobs request body."""

    industry: str = Field(min_length=1, max_length=200, examples=["Jewelry Stores"])
    country: str = Field(min_length=1, max_length=100, examples=["United States"])
    region: str | None = Field(default=None, max_length=100, examples=["California"])
    city: str | None = Field(default=None, max_length=100)
    keywords: str | None = Field(default=None, max_length=500)
    requested_leads: Literal[10, 50, 100, 500] = 100
    provider: str = Field(default="demo", max_length=50)
    enable_ai: bool = False
    demo_delay_ms: int = Field(default=120, ge=0, le=5000)


class JobRead(BaseModel):
    """Full research-job representation, incl. live pipeline counters."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    industry: str
    country: str
    region: str | None
    city: str | None
    keywords: str | None
    requested_leads: int
    provider: str
    enable_ai: bool
    demo_delay_ms: int
    status: str
    stage: str | None
    progress_pct: int
    discovered: int
    processed: int
    accepted: int
    duplicates: int
    invalid: int
    error: str | None
    created_at: datetime
    completed_at: datetime | None


class JobSummary(BaseModel):
    """Compact job representation for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    industry: str
    country: str
    region: str | None
    requested_leads: int
    status: str
    progress_pct: int
    accepted: int
    duplicates: int
    invalid: int
    created_at: datetime
    completed_at: datetime | None


class JobList(BaseModel):
    items: list[JobSummary]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Companies & results
# ---------------------------------------------------------------------------


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_name: str
    normalized_name: str | None
    website: str | None
    normalized_domain: str | None
    industry: str | None
    country: str | None
    region: str | None
    city: str | None
    address: str | None
    phone: str | None
    phone_normalized: str | None
    public_email: str | None
    linkedin_url: str | None
    source_url: str | None
    source_provider: str
    is_synthetic: bool
    created_at: datetime
    updated_at: datetime


class ValidationIssue(BaseModel):
    field: str
    code: str  # invalid_email | invalid_url | invalid_phone | missing_required | ...
    message: str


class AIField(BaseModel):
    value: str | None
    ai_derived: bool = True


class ResultRead(BaseModel):
    """One row of a job's results table."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    company: CompanyRead
    quality_score: int
    score_factors: dict[str, int] | None  # factor -> points, sums to quality_score
    validation_status: str
    validation_issues: list[ValidationIssue] | None
    verification_status: str
    ai_enriched: bool
    ai_fields: dict[str, AIField] | None
    dedupe_status: str
    duplicate_of_id: str | None
    collected_at: datetime


class ResultDetail(ResultRead):
    """Record detail view: everything in ResultRead (already explainable)."""

    # Normalized info, source, validation, score breakdown, AI fields, dedupe
    # status, and collection timestamp are all present via ResultRead + CompanyRead.
    pass


class ResultsPage(BaseModel):
    items: list[ResultRead]
    total: int
    page: int
    page_size: int


class ValidationReport(BaseModel):
    job_id: str
    total: int
    valid: int
    invalid: int
    duplicates: int
    issues_by_field: dict[str, int]


# ---------------------------------------------------------------------------
# Demo dataset management
# ---------------------------------------------------------------------------


class DemoSeedResponse(BaseModel):
    """Result of ``POST /api/demo/seed`` — how many synthetic companies exist."""

    companies: int


class DemoResetRequest(BaseModel):
    """Body for ``POST /api/demo/reset``."""

    reseed: bool = False


class DemoResetResponse(BaseModel):
    """Result of ``POST /api/demo/reset`` — deletion counts plus reseed info."""

    jobs_deleted: int
    results_deleted: int
    rejected_records_deleted: int
    companies_deleted: int
    reseeded: bool
    companies: int


# ---------------------------------------------------------------------------
# Providers & health
# ---------------------------------------------------------------------------


class ProviderHealth(BaseModel):
    name: str
    status: str  # available | not_configured | disabled | configured | error
    detail: str


class ProvidersHealth(BaseModel):
    demo: ProviderHealth
    http: ProviderHealth
    ai: ProviderHealth
    database: ProviderHealth


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str = "0.1.0"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    detail: str
    code: str = "error"
