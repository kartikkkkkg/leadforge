"""DemoProvider: offline, deterministic synthetic company discovery.

* Works completely offline; no API key; no network; no scraping.
* Data comes from :mod:`leadforge.seed` — 100 synthetic companies, seeded
  for determinism (same seed -> same records, same order).
* Every record has ``is_synthetic=True`` and ``source_provider="demo"``;
  domains live under ``.example.com`` and phones in the fictional
  ``555-01XX`` range, so synthetic data can never be mistaken for real
  business data.
"""

from __future__ import annotations

from ..schemas import ProviderHealth
from ..seed import DATASET_SIZE, generate_dataset
from .base import CompanyQuery, ContactInfo, RawCompany, ResearchProvider


def _matches(query: CompanyQuery, record: RawCompany) -> bool:
    """Deterministic filter: exact (case-insensitive) location/industry match,
    substring match for keywords."""

    def eq(want: str | None, have: str | None) -> bool:
        return want is None or (have is not None and want.strip().lower() == have.strip().lower())

    if not eq(query.industry, record.industry):
        return False
    if not eq(query.country, record.country):
        return False
    if not eq(query.region, record.region):
        return False
    if not eq(query.city, record.city):
        return False
    if query.keywords:
        haystack = f"{record.company_name or ''} {record.industry or ''}".lower()
        if query.keywords.strip().lower() not in haystack:
            return False
    return True


class DemoProvider(ResearchProvider):
    """Synthetic offline provider. Always available, never real data."""

    name = "demo"

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        dataset = generate_dataset(seed=seed)
        # Internal refs "demo-0000".."demo-0099" map to dataset positions.
        self._records: list[RawCompany] = [RawCompany(**item) for item in dataset]
        self._refs: dict[str, RawCompany] = {
            f"demo-{i:04d}": record for i, record in enumerate(self._records)
        }

    @property
    def dataset_size(self) -> int:
        return len(self._records)

    async def search_companies(self, query: CompanyQuery, limit: int) -> list[RawCompany]:
        """Return up to ``limit`` synthetic records matching ``query``.

        Filtering is deterministic: dataset order is preserved and the first
        ``limit`` matches win. An empty list is an honest "no matches".
        """
        if limit <= 0:
            return []
        matched = [r for r in self._records if _matches(query, r)]
        return matched[:limit]

    async def get_company_details(self, ref: str) -> RawCompany | None:
        """Look up one synthetic company by its ``demo-NNNN`` reference."""
        return self._refs.get(ref)

    def extract_contacts(self, raw: RawCompany) -> ContactInfo:
        """Pull contact details from a raw record (no network)."""
        return ContactInfo(email=raw.public_email, phone=raw.phone)

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            name=self.name,
            status="available",
            detail=f"Demo provider ready: {DATASET_SIZE} synthetic companies (offline, seeded).",
        )
