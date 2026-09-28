"""Deterministic synthetic dataset generator (100 companies).

Used by :class:`DemoProvider`. The dataset is fully synthetic and every
record is flagged ``is_synthetic=True`` so synthetic data can never be
mistaken for real business data:

* domains live under ``.example.com`` (reserved, never real),
* phones use the fictional ``555-01XX`` range,
* company names are assembled from business-style parts — no real personal
  names anywhere,
* addresses use fictional street names.

Generation is deterministic: the same ``seed`` always yields the same
dataset, in the same order. No network, no randomness beyond the seeded
generator.
"""

from __future__ import annotations

import random
import re
from typing import Any

DATASET_SIZE = 100

# Industry -> name cores. Business-style words only; no personal names.
_INDUSTRY_CORES: dict[str, list[str]] = {
    "Jewelry Stores": [
        "Harbor", "Meridian", "Copperline", "Golden Hour", "Velvet Box",
        "Northstar", "Ember & Oak", "Lakeside", "Truecarat", "Willow",
    ],
    "Software Publishers": [
        "Brightstack", "Northloop", "Kernel & Co", "Datamere", "Cloudharbor",
        "Pixelforge", "Statline", "Appward", "Codemesa", "Bitfield",
    ],
    "Restaurants": [
        "Copper Skillet", "Juniper Table", "Emberline", "The Gilded Fork",
        "Harbor & Thyme", "Saffron Road", "Blueplate", "Fern & Fable",
        "Old Mill", "Cinder",
    ],
    "Legal Services": [
        "Hartwell", "Bexley & Marsh", "Clearcounsel", "Ironclad", "Meridian Law",
        "Stonebridge", "Fairhaven", "Ledger & Lane", "Northgate", "Vantage",
    ],
    "Dental Offices": [
        "Brightsmile", "Clearwater", "Gentle Arch", "Pearl & Pine", "Smileline",
        "Harborview", "Tooth & Timber", "Lumina", "Everbright", "Calmroot",
    ],
}

_INDUSTRY_TRADE_WORD: dict[str, str] = {
    "Jewelry Stores": "Jewelry",
    "Software Publishers": "Software",
    "Restaurants": "Kitchen",
    "Legal Services": "Legal",
    "Dental Offices": "Dental",
}

_NAME_SUFFIXES = ["LLC", "Inc.", "Co.", "Ltd.", "Group", "Partners", "Studio", "Works"]

# (city, region, country) — real place names are fine; they are locations,
# not personal data.
_PLACES: list[tuple[str, str, str]] = [
    ("Los Angeles", "California", "United States"),
    ("Austin", "Texas", "United States"),
    ("Chicago", "Illinois", "United States"),
    ("Miami", "Florida", "United States"),
    ("Seattle", "Washington", "United States"),
    ("Denver", "Colorado", "United States"),
    ("Boston", "Massachusetts", "United States"),
    ("Portland", "Oregon", "United States"),
    ("Toronto", "Ontario", "Canada"),
    ("London", "England", "United Kingdom"),
]

_STREETS = ["Meridian Ave", "Harbor Blvd", "Copperline St", "Juniper Way", "Foundry Rd"]


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)


def generate_dataset(seed: int = 42, size: int = DATASET_SIZE) -> list[dict[str, Any]]:
    """Generate ``size`` synthetic company records, deterministically.

    The same ``seed`` always produces the same records in the same order.
    A deterministic subset of records is intentionally sparse (missing phone
    / email / website) so completeness scoring has something to measure.
    """
    rng = random.Random(seed)
    industries = list(_INDUSTRY_CORES)
    records: list[dict[str, Any]] = []

    for i in range(size):
        industry = industries[i % len(industries)]
        core = rng.choice(_INDUSTRY_CORES[industry])
        trade = _INDUSTRY_TRADE_WORD[industry]
        suffix = rng.choice(_NAME_SUFFIXES)
        name = f"{core} {trade} {suffix}"
        domain = f"{_slug(name)}.example.com"
        city, region, country = _PLACES[i % len(_PLACES)]
        street = _STREETS[i % len(_STREETS)]

        # Deterministic sparsity: some records lack contact fields.
        sparse_phone = (i % 7 == 3)
        sparse_email = (i % 11 == 5)
        sparse_website = (i % 13 == 7)

        records.append(
            {
                "company_name": name,
                "website": None if sparse_website else f"https://www.{domain}/",
                "industry": industry,
                "country": country,
                "region": region,
                "city": city,
                "address": f"{100 + i} {street}, {city}, {region}",
                "phone": None if sparse_phone else f"+1-555-01{i % 100:02d}",
                "public_email": None if sparse_email else f"info@{domain}",
                "linkedin_url": None,
                "source_url": None,
                "source_provider": "demo",
                "is_synthetic": True,
                "demo_ref": f"demo-{i:04d}",
            }
        )
    return records
