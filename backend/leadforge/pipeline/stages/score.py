"""Deterministic lead *completeness* scoring.

A completeness score measures how complete a record is — how many of the
expected fields are present — **not** whether the information is true.
Never call this a "verification score".

Formula (transparent, sums to 100)
----------------------------------
================= ====== ============================================
Factor            Points Counts when present (non-blank)
================= ====== ============================================
``website``          20   ``normalized_domain`` or ``website``
``company_name``     20   ``company_name``
``location``         15   ``country``
``phone``            15   ``phone_normalized`` or ``phone``
``public_email``     20   ``public_email``
``source``           10   ``source_url`` or ``source_provider``
================= ====== ============================================

Bands
-----
* ``"High"``   — 90–100
* ``"Medium"`` — 70–89
* ``"Low"``    — below 70

Pure functions: no I/O, no mutation of the input.
"""

from __future__ import annotations

from typing import Any

# Factor -> max points. Sums to 100. Keep in sync with the module docstring.
COMPLETENESS_WEIGHTS: dict[str, int] = {
    "website": 20,
    "company_name": 20,
    "location": 15,
    "phone": 15,
    "public_email": 20,
    "source": 10,
}

_HIGH_MIN = 90
_MEDIUM_MIN = 70


def _present(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def completeness_score(rec: dict[str, Any]) -> tuple[int, dict[str, int]]:
    """Score a record's completeness: ``(total, {factor: points})``.

    ``factors`` always contains every key of :data:`COMPLETENESS_WEIGHTS`
    (0 for absent fields) so the breakdown is explainable and the values
    sum to the total. A non-mapping record scores 0.
    """
    factors: dict[str, int] = {name: 0 for name in COMPLETENESS_WEIGHTS}
    if not isinstance(rec, dict):
        return 0, factors

    if _present(rec.get("normalized_domain")) or _present(rec.get("website")):
        factors["website"] = COMPLETENESS_WEIGHTS["website"]
    if _present(rec.get("company_name")):
        factors["company_name"] = COMPLETENESS_WEIGHTS["company_name"]
    if _present(rec.get("country")):
        factors["location"] = COMPLETENESS_WEIGHTS["location"]
    if _present(rec.get("phone_normalized")) or _present(rec.get("phone")):
        factors["phone"] = COMPLETENESS_WEIGHTS["phone"]
    if _present(rec.get("public_email")):
        factors["public_email"] = COMPLETENESS_WEIGHTS["public_email"]
    if _present(rec.get("source_url")) or _present(rec.get("source_provider")):
        factors["source"] = COMPLETENESS_WEIGHTS["source"]

    return sum(factors.values()), factors


def completeness_band(score: int) -> str:
    """Map a completeness score to its band: ``"High"`` | ``"Medium"`` | ``"Low"``."""
    if score >= _HIGH_MIN:
        return "High"
    if score >= _MEDIUM_MIN:
        return "Medium"
    return "Low"
