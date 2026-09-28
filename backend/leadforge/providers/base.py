"""Research provider abstraction.

A provider supplies *raw* company records to LeadForge. It is deliberately
independent from the downstream pipeline: a provider must NOT normalize,
validate, deduplicate, score, enrich, persist, or export — those are separate
pipeline responsibilities (see ``leadforge.pipeline.stages``).

Contract (DESIGN.md §5.1)
-------------------------
* ``CompanyQuery``  — research parameters (industry, country, region?, city?, keywords?).
* ``RawCompany``    — one raw company record; ``is_synthetic`` flags demo data.
* ``ContactInfo``   — contact details extracted from a raw record.
* ``ResearchProvider`` — ABC: ``name``, ``search_companies``, ``get_company_details``,
  ``extract_contacts``, ``health``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..schemas import ProviderHealth


class ProviderError(Exception):
    """Predictable provider failure (timeout, connection, bad response, ...).

    Never carries credentials — messages and logs must stay secret-free.
    """


class NotConfiguredError(ProviderError):
    """Raised when a provider cannot run without external configuration.

    The message tells the operator exactly which environment variables to set.
    """


class CompanyQuery(BaseModel):
    """Research parameters for a provider search."""

    industry: str = Field(min_length=1, max_length=200)
    country: str = Field(min_length=1, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    keywords: str | None = Field(default=None, max_length=500)


class RawCompany(BaseModel):
    """One raw company record as returned by a provider."""

    model_config = ConfigDict(extra="ignore")  # internal fields (e.g. demo_ref) stay out

    company_name: str | None = None
    website: str | None = None
    industry: str | None = None
    country: str | None = None
    region: str | None = None
    city: str | None = None
    address: str | None = None
    phone: str | None = None
    public_email: str | None = None
    linkedin_url: str | None = None
    source_url: str | None = None
    source_provider: str | None = None
    is_synthetic: bool = False


class ContactInfo(BaseModel):
    """Contact details extracted from a raw company record."""

    email: str | None = None
    phone: str | None = None


class ResearchProvider(ABC):
    """Abstract discovery provider. Implementations supply raw records only."""

    name: str = "base"

    @abstractmethod
    async def search_companies(self, query: CompanyQuery, limit: int) -> list[RawCompany]:
        """Discover raw company records matching ``query`` (at most ``limit``)."""
        raise NotImplementedError

    @abstractmethod
    async def get_company_details(self, ref: str) -> RawCompany | None:
        """Fetch one company by provider-specific reference, or ``None``."""
        raise NotImplementedError

    @abstractmethod
    def extract_contacts(self, raw: RawCompany) -> ContactInfo:
        """Pull contact details out of a raw record (no network)."""
        raise NotImplementedError

    def health(self) -> ProviderHealth:
        """Provider health. Base default: unknown (override with a real check)."""
        return ProviderHealth(
            name=self.name,
            status="unknown",
            detail="No health check implemented for this provider.",
        )

    def to_dict(self, raw: RawCompany) -> dict[str, Any]:
        """Convert a raw record to a plain dict for the pipeline stages."""
        return raw.model_dump()
