"""Demo dataset management: seed + reset.

``seed_demo_companies`` inserts the deterministic 100-company synthetic
dataset — produced by :func:`leadforge.seed.generate_dataset`, the same
generator :class:`~leadforge.providers.demo.DemoProvider` uses — into the
``companies`` table. ``reset_demo_data`` wipes all demo data (research jobs
with their results and rejected records, plus companies) with an optional
re-seed.

Everything here is synthetic by construction: the generator only produces
``is_synthetic=True`` rows on reserved ``.example.com`` domains with
fictional ``555-01XX`` phones, so seeded data can never be mistaken for
real business data.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .. import models
from ..seed import DATASET_SIZE, generate_dataset

# ``source_provider`` marker for rows owned by the seeded demo dataset.
# Pipeline runs create their own company rows (``source_provider="demo"``);
# the marker keeps ``seed`` from ever touching job results.
DEMO_SEED_PROVIDER = "demo-seed"

# Company columns populated from a seed item (``demo_ref`` is internal to the
# generator and stays out, like RawCompany does with extra="ignore").
_SEED_FIELDS = (
    "company_name",
    "website",
    "industry",
    "country",
    "region",
    "city",
    "address",
    "phone",
    "public_email",
    "linkedin_url",
    "source_url",
)


def seed_demo_companies(session: Session, seed: int = 42) -> int:
    """Insert the synthetic demo dataset into ``companies``.

    Idempotent: previously seeded rows (``source_provider="demo-seed"``) are
    removed first, so repeated seeding never accumulates duplicates — and
    companies created by research jobs are never touched. Returns the number
    of companies inserted (always :data:`DATASET_SIZE` for the default
    generator).
    """
    session.query(models.Company).filter(
        models.Company.source_provider == DEMO_SEED_PROVIDER
    ).delete(synchronize_session=False)
    inserted = 0
    for item in generate_dataset(seed=seed):
        fields = {field: item.get(field) for field in _SEED_FIELDS}
        fields["company_name"] = fields["company_name"] or ""  # NOT NULL guard
        session.add(
            models.Company(
                **fields,
                source_provider=DEMO_SEED_PROVIDER,
                is_synthetic=True,
            )
        )
        inserted += 1
    session.commit()
    return inserted


def reset_demo_data(session: Session, reseed: bool = False) -> dict[str, Any]:
    """Wipe all demo data and optionally re-seed the synthetic dataset.

    Deletes research jobs, their results and rejected records, and every
    company row (bulk deletes run child-first so no FK is ever violated, on
    SQLite and Postgres alike). Returns deletion counts plus reseed info.
    """
    results_deleted = (
        session.query(models.LeadResearchResult)
        .delete(synchronize_session=False)
    )
    rejected_deleted = (
        session.query(models.RejectedRecord).delete(synchronize_session=False)
    )
    jobs_deleted = (
        session.query(models.ResearchJob).delete(synchronize_session=False)
    )
    companies_deleted = (
        session.query(models.Company).delete(synchronize_session=False)
    )
    session.commit()
    outcome: dict[str, Any] = {
        "jobs_deleted": jobs_deleted,
        "results_deleted": results_deleted,
        "rejected_records_deleted": rejected_deleted,
        "companies_deleted": companies_deleted,
        "reseeded": False,
        "companies": 0,
    }
    if reseed:
        outcome["companies"] = seed_demo_companies(session)
        outcome["reseeded"] = True
    return outcome


def demo_dataset_size() -> int:
    """Number of companies the demo dataset holds (seed contract)."""
    return DATASET_SIZE
