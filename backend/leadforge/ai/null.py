"""NullAIProvider: the default AI provider.

``enabled=False`` — it performs no network calls, needs no credentials, and
never produces AI-derived content. ``classify_company`` does deterministic,
rule-based industry label cleanup only (this is normalization, not AI); the
other methods return ``None`` so the pipeline stores no AI fields.

The application is fully usable with this provider: every job completes with
``ai_enriched=False``.
"""

from __future__ import annotations

from typing import Any

from .base import AIProvider

# Deterministic alias cleanup for industry labels. This is a fixed lookup
# table, not inference — the same input always yields the same output.
_INDUSTRY_ALIASES = {
    "jewelry store": "Jewelry Stores",
    "jewellery stores": "Jewelry Stores",
    "saas": "SaaS",
    "software as a service": "SaaS",
}


class NullAIProvider(AIProvider):
    """Default provider: disabled, offline, no credentials, no AI output."""

    name: str = "null"
    enabled: bool = False

    async def classify_company(
        self, company: dict[str, Any], industry: str
    ) -> str | None:
        """Rule-based industry label cleanup; ``"Unknown"`` when empty."""
        cleaned = (industry or "").strip()
        if not cleaned:
            return "Unknown"
        return _INDUSTRY_ALIASES.get(cleaned.lower(), cleaned)

    async def extract_company_information(self, text: str) -> dict[str, Any] | None:
        return None

    async def summarize_company(self, company: dict[str, Any]) -> str | None:
        return None
