"""AIProvider abstract interface.

AI enrichment is strictly optional and additive: it may *add* tagged,
AI-derived fields to a result, but it can never replace deterministic
normalization, validation, deduplication, or completeness scoring, and it
can never turn its output into source facts. See ``null.py`` and ``llm.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    """Optional AI enrichment for lead records.

    Implementations must be side-effect free with respect to the pipeline:
    they receive already-normalized data and return *suggestions*, never
    mutations. The pipeline wraps stored values as
    ``{"value": ..., "ai_derived": True}`` so AI output is never mistaken
    for a verified source fact.
    """

    name: str = "base"
    enabled: bool = False

    @abstractmethod
    async def classify_company(
        self, company: dict[str, Any], industry: str
    ) -> str | None:
        """Suggest an industry label for a normalized company record.

        Returns the suggestion, ``"Unknown"``, or ``None`` when the provider
        cannot classify. Must never invent company facts to do so.
        """

    @abstractmethod
    async def extract_company_information(self, text: str) -> dict[str, Any] | None:
        """Extract structured fields from free text.

        Returns a plain ``{field: value}`` dict, or ``None`` when nothing can
        be extracted. Values must come from the input text only — no invented
        contacts, URLs, or addresses.
        """

    @abstractmethod
    async def summarize_company(self, company: dict[str, Any]) -> str | None:
        """One-to-three sentence summary of a normalized company record.

        Returns ``None`` when the provider cannot summarize. The summary is
        derived only from the fields it was given.
        """
