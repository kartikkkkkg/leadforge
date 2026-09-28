"""SQLAlchemy models for LeadForge.

Entities (per DESIGN.md §3):
- ``ResearchJob``      — one research request + live pipeline counters
- ``Company``          — a discovered company with normalized variants
- ``LeadResearchResult`` — job ↔ company link: score, validation, dedupe, AI flags
- ``RejectedRecord``   — records dropped by validation/deduplication, with reasons

One model set serves SQLite and PostgreSQL. Primary keys are UUID strings.
Timestamps are naive UTC datetimes (identical behavior on both backends).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    # Naive UTC: SQLite and PostgreSQL behave identically.
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Status vocabularies (stored as plain strings; documented here, not enums,
# so both databases stay simple and migrations stay painless).
JOB_STATUSES = ("queued", "running", "completed", "failed")
VALIDATION_STATUSES = ("valid", "invalid")
VERIFICATION_STATUSES = ("unverified", "self_reported", "independently_verified")
DEDUPE_STATUSES = ("unique", "duplicate_removed", "needs_review")


class ResearchJob(Base):
    """A single lead-research request and its pipeline run."""

    __tablename__ = "research_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    industry: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    keywords: Mapped[str | None] = mapped_column(String(500), nullable=True)
    requested_leads: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="demo")
    enable_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    demo_delay_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=120)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    stage: Mapped[str | None] = mapped_column(String(30), nullable=True)
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    results: Mapped[list["LeadResearchResult"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    rejected_records: Mapped[list["RejectedRecord"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class Company(Base):
    """A discovered company. ``normalized_*`` columns power deduplication."""

    __tablename__ = "companies"
    __table_args__ = (
        Index("ix_companies_normalized_domain", "normalized_domain"),
        Index("ix_companies_normalized_name", "normalized_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    company_name: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    normalized_domain: Mapped[str | None] = mapped_column(String(300), nullable=True)

    industry: Mapped[str | None] = mapped_column(String(200), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    phone_normalized: Mapped[str | None] = mapped_column(String(50), nullable=True)
    public_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    source_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="demo")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    lead_results: Mapped[list["LeadResearchResult"]] = relationship(
        back_populates="company", foreign_keys="LeadResearchResult.company_id"
    )


class LeadResearchResult(Base):
    """Job ↔ company link carrying the score, validation, dedupe, and AI metadata."""

    __tablename__ = "lead_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_jobs.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )

    quality_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # e.g. {"website": 20, "company_name": 20, "location": 15, ...} — explainable scoring
    score_factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    validation_status: Mapped[str] = mapped_column(String(20), nullable=False, default="valid")
    # e.g. [{"field": "public_email", "code": "invalid_email", "message": "..."}]
    validation_issues: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Demo/synthetic data is NEVER marked verified.
    verification_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="unverified"
    )

    ai_enriched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # AI-derived values, each tagged {"value": ..., "ai_derived": True}
    ai_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    dedupe_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unique")
    duplicate_of_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )

    collected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)

    job: Mapped["ResearchJob"] = relationship(back_populates="results")
    company: Mapped["Company"] = relationship(
        back_populates="lead_results", foreign_keys=[company_id]
    )
    duplicate_of: Mapped["Company | None"] = relationship(foreign_keys=[duplicate_of_id])


class RejectedRecord(Base):
    """A record dropped by validation or deduplication — kept with its reason."""

    __tablename__ = "rejected_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_jobs.id", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[str] = mapped_column(String(20), nullable=False)  # validate|deduplicate
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)

    job: Mapped["ResearchJob"] = relationship(back_populates="rejected_records")
