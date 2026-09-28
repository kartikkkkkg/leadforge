"""Deduplication: exact + fuzzy matching with ``needs_review`` flagging.

Matching precedence (first hit wins, checked in this order)
------------------------------------------------------------
1. ``exact_domain``  — identical ``normalized_domain`` (non-empty).
2. ``exact_email``   — identical normalized ``public_email`` (non-empty).
3. ``name_location`` — identical ``normalized_name`` *and* identical
   ``country_normalized`` *and* identical ``city_normalized``
   (all three must be non-empty).
4. ``fuzzy_name``    — ``normalized_name`` similarity at or above
   :data:`FUZZY_REVIEW_THRESHOLD` *and* compatible countries
   (both missing, or equal). Fuzzy matches are **never** auto-removed;
   they are surfaced in :attr:`DedupeResult.needs_review` and keep
   ``dedupe_status = "needs_review"`` downstream.

Rules 1–3 auto-remove: the later record is dropped from
:attr:`DedupeResult.unique` and reported in :attr:`DedupeResult.duplicates`
with ``needs_review=False``.

The function is deterministic and order-aware: records are processed in
input order, the *first* occurrence of a duplicate group is kept, and fuzzy
comparison scans kept records in order, taking the first match.

No I/O, no mutation of the input list or its records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from .normalize import normalize_company_name, normalize_domain, normalize_email

# ---------------------------------------------------------------------------
# Matching rules (closed set, in precedence order).
# ---------------------------------------------------------------------------
EXACT_DOMAIN = "exact_domain"
EXACT_EMAIL = "exact_email"
NAME_LOCATION = "name_location"
FUZZY_NAME = "fuzzy_name"

MATCH_RULES: tuple[str, ...] = (EXACT_DOMAIN, EXACT_EMAIL, NAME_LOCATION, FUZZY_NAME)

# DESIGN.md defines the fuzzy threshold concept but no numeric value; this is
# the module default. At/above -> needs_review; below -> treated as unique.
# Fuzzy matches are never auto-removed regardless of confidence.
FUZZY_REVIEW_THRESHOLD = 0.85


@dataclass
class DuplicateMatch:
    """One duplicate relationship found by :func:`find_duplicates`."""

    index: int  # position of the duplicate record in the input list
    matched_index: int  # position of the earlier record it duplicates
    rule: str  # one of EXACT_DOMAIN | EXACT_EMAIL | NAME_LOCATION | FUZZY_NAME
    confidence: float  # 1.0 for exact rules; SequenceMatcher ratio for fuzzy
    needs_review: bool  # True only for fuzzy matches


@dataclass
class DedupeResult:
    """Outcome of :func:`find_duplicates`."""

    unique: list[dict[str, Any]]  # records to keep (incl. needs_review ones)
    duplicates: list[DuplicateMatch] = field(default_factory=list)  # auto-removed
    needs_review: list[DuplicateMatch] = field(default_factory=list)  # fuzzy


def _nonempty(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _match_keys(rec: dict[str, Any]) -> dict[str, str | None]:
    """Derive the dedupe match keys for a record.

    Works on normalized records but falls back to normalizing raw fields,
    so the function is safe to call on unnormalized input too.
    """
    domain = _nonempty(rec.get("normalized_domain")) or normalize_domain(rec.get("website"))
    email = _nonempty(rec.get("email_normalized")) or normalize_email(rec.get("public_email"))
    name = _nonempty(rec.get("normalized_name")) or normalize_company_name(
        rec.get("company_name")
    )
    country = _nonempty(rec.get("country_normalized"))
    if country is None:
        raw_country = rec.get("country")
        country = raw_country.strip().lower() if isinstance(raw_country, str) and raw_country.strip() else None
    city = _nonempty(rec.get("city_normalized"))
    if city is None:
        raw_city = rec.get("city")
        city = raw_city.strip().lower() if isinstance(raw_city, str) and raw_city.strip() else None
    return {
        "domain": domain,
        "email": email,
        "name": name,
        "country": country,
        "city": city,
    }


def _register_keys(
    keys: dict[str, str | None],
    index: int,
    seen_domains: dict[str, int],
    seen_emails: dict[str, int],
    seen_name_location: dict[tuple[str, str, str], int],
) -> None:
    """Register a kept record's exact keys (first occurrence wins)."""
    if keys["domain"] is not None:
        seen_domains.setdefault(keys["domain"], index)
    if keys["email"] is not None:
        seen_emails.setdefault(keys["email"], index)
    if (
        keys["name"] is not None
        and keys["country"] is not None
        and keys["city"] is not None
    ):
        seen_name_location.setdefault((keys["name"], keys["country"], keys["city"]), index)


def _countries_compatible(a: str | None, b: str | None) -> bool:
    """Fuzzy matches must not merge companies from different countries."""
    return a is None or b is None or a == b


def find_duplicates(records: list[dict[str, Any]]) -> DedupeResult:
    """Deduplicate company records.

    Parameters
    ----------
    records:
        Company records in pipeline order (raw or normalized dicts).
        The input list is not mutated.

    Returns
    -------
    DedupeResult
        ``unique`` keeps the first occurrence of every duplicate group;
        ``duplicates`` lists auto-removed exact matches; ``needs_review``
        lists fuzzy matches that a human must decide on.
    """
    if not isinstance(records, list):
        raise TypeError(f"find_duplicates expects a list, got {type(records).__name__}")

    result = DedupeResult(unique=[])
    # key value -> index (into the *input* list) of first record holding it
    seen_domains: dict[str, int] = {}
    seen_emails: dict[str, int] = {}
    seen_name_location: dict[tuple[str, str, str], int] = {}
    # (input index, match keys) of kept records, in order — fuzzy scan space
    kept: list[tuple[int, dict[str, str | None]]] = []

    for index, rec in enumerate(records):
        keys = _match_keys(rec if isinstance(rec, dict) else {})
        match: DuplicateMatch | None = None

        # Rule 1: exact normalized domain.
        if keys["domain"] is not None and keys["domain"] in seen_domains:
            match = DuplicateMatch(
                index=index,
                matched_index=seen_domains[keys["domain"]],
                rule=EXACT_DOMAIN,
                confidence=1.0,
                needs_review=False,
            )
        # Rule 2: exact normalized email.
        elif keys["email"] is not None and keys["email"] in seen_emails:
            match = DuplicateMatch(
                index=index,
                matched_index=seen_emails[keys["email"]],
                rule=EXACT_EMAIL,
                confidence=1.0,
                needs_review=False,
            )
        # Rule 3: normalized name + location (all three parts required).
        elif (
            keys["name"] is not None
            and keys["country"] is not None
            and keys["city"] is not None
            and (keys["name"], keys["country"], keys["city"]) in seen_name_location
        ):
            match = DuplicateMatch(
                index=index,
                matched_index=seen_name_location[
                    (keys["name"], keys["country"], keys["city"])
                ],
                rule=NAME_LOCATION,
                confidence=1.0,
                needs_review=False,
            )
        else:
            # Rule 4: fuzzy name — first kept record at/above threshold wins.
            if keys["name"]:
                for kept_index, kept_keys in kept:
                    if not kept_keys["name"]:
                        continue
                    if not _countries_compatible(keys["country"], kept_keys["country"]):
                        continue
                    ratio = SequenceMatcher(None, keys["name"], kept_keys["name"]).ratio()
                    if ratio >= FUZZY_REVIEW_THRESHOLD:
                        match = DuplicateMatch(
                            index=index,
                            matched_index=kept_index,
                            rule=FUZZY_NAME,
                            confidence=round(ratio, 4),
                            needs_review=True,
                        )
                        break

        if match is None:
            # Unique (or first of its group): keep and register its keys.
            result.unique.append(rec)
            kept.append((index, keys))
            _register_keys(keys, index, seen_domains, seen_emails, seen_name_location)
        elif match.needs_review:
            # Fuzzy: kept, but flagged for human review — never silently deleted.
            # Its exact keys are still registered so later exact duplicates of
            # *this* record are caught.
            result.unique.append(rec)
            kept.append((index, keys))
            _register_keys(keys, index, seen_domains, seen_emails, seen_name_location)
            result.needs_review.append(match)
        else:
            result.duplicates.append(match)

    return result
