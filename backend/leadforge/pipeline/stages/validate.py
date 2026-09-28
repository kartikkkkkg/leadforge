"""Record validation: required-field, format, and missing-value checks.

Validation returns structured results (:class:`ValidationResult`) rather
than a bare boolean, so callers can explain *why* a record was rejected.

Issue codes (stable, UPPER_SNAKE — the single closed set used by this
module; do not invent new codes elsewhere)
------------------------------------------------
* ``MISSING_COMPANY_NAME`` — ``company_name`` is absent or blank.
* ``INVALID_COMPANY_NAME`` — ``company_name`` is present but malformed
  (wrong type, control characters, or nothing but punctuation).
* ``INVALID_EMAIL``        — ``public_email`` is present but malformed.
* ``INVALID_DOMAIN``       — ``website``/``normalized_domain`` is present
  but not a plausible domain.
* ``INVALID_PHONE``        — ``phone`` is present but has too few or too
  many digits to be a real phone number.
* ``MISSING_LOCATION``     — ``country`` is absent or blank.
* ``INVALID_RECORD``       — the record itself is malformed (not a mapping,
  or a field has an unexpected type).

A record is *valid* only when it has zero issues. Fields that are simply
absent (email, phone, website) do not invalidate a record — absence lowers
the completeness score instead (see :mod:`score`).

Each issue is a plain ``{"field", "code", "message"}`` dict, matching the
``ValidationIssue`` schema in ``leadforge.schemas`` so it can be stored
directly in ``LeadResearchResult.validation_issues``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Stable issue codes (closed set — see module docstring).
# ---------------------------------------------------------------------------
MISSING_COMPANY_NAME = "MISSING_COMPANY_NAME"
INVALID_COMPANY_NAME = "INVALID_COMPANY_NAME"
INVALID_EMAIL = "INVALID_EMAIL"
INVALID_DOMAIN = "INVALID_DOMAIN"
INVALID_PHONE = "INVALID_PHONE"
MISSING_LOCATION = "MISSING_LOCATION"
INVALID_RECORD = "INVALID_RECORD"

ISSUE_CODES: tuple[str, ...] = (
    MISSING_COMPANY_NAME,
    INVALID_COMPANY_NAME,
    INVALID_EMAIL,
    INVALID_DOMAIN,
    INVALID_PHONE,
    MISSING_LOCATION,
    INVALID_RECORD,
)

# Pragmatic email check: local@domain.tld. Rejects obvious garbage; it is a
# syntax check, not proof the mailbox exists.
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

# Plausible public domain: labels of letters/digits/hyphens, at least one
# dot, TLD of 2+ letters. Rejects "not a domain", bare words, IPs-as-text.
_DOMAIN_RE = re.compile(
    r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)"
    r"(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*"
    r"\.[A-Za-z]{2,}$"
)

# Control characters that must never appear in a company name.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# E.164 allows at most 15 digits; fewer than 7 digits is not a dialable
# business number.
_MIN_PHONE_DIGITS = 7
_MAX_PHONE_DIGITS = 15


@dataclass
class ValidationResult:
    """Structured outcome of :func:`validate_record`."""

    is_valid: bool
    issues: list[dict[str, str]] = field(default_factory=list)


def _issue(field_name: str, code: str, message: str) -> dict[str, str]:
    return {"field": field_name, "code": code, "message": message}


def _present(value: Any) -> bool:
    """True when a value is a non-blank string."""
    return isinstance(value, str) and bool(value.strip())


def validate_record(rec: dict[str, Any]) -> ValidationResult:
    """Validate a (preferably normalized) company record.

    Pure function: no I/O, no mutation of the input. Safe to call on raw
    records too — normalization only makes the checks more reliable.
    """
    if not isinstance(rec, dict):
        return ValidationResult(
            is_valid=False,
            issues=[
                _issue(
                    "record",
                    INVALID_RECORD,
                    f"record must be a mapping, got {type(rec).__name__}",
                )
            ],
        )

    issues: list[dict[str, str]] = []

    # -- company name: required -------------------------------------------
    name = rec.get("company_name")
    if not _present(name):
        issues.append(
            _issue("company_name", MISSING_COMPANY_NAME, "company_name is required")
        )
    elif _CONTROL_CHARS_RE.search(name) or not re.search(r"[A-Za-z0-9]", name):
        issues.append(
            _issue(
                "company_name",
                INVALID_COMPANY_NAME,
                "company_name contains control characters or no alphanumeric content",
            )
        )

    # -- email: validated only when present --------------------------------
    # (``or`` — not ``dict.get`` default — because normalize_record always
    # sets the normalized keys, possibly to None)
    email = rec.get("email_normalized") or rec.get("public_email")
    if _present(email) and not _EMAIL_RE.fullmatch(email.strip()):
        issues.append(
            _issue("public_email", INVALID_EMAIL, f"{email.strip()!r} is not a valid email")
        )

    # -- domain: validated only when present -------------------------------
    domain = rec.get("normalized_domain") or rec.get("website")
    if _present(domain) and not _DOMAIN_RE.fullmatch(domain.strip()):
        issues.append(
            _issue("website", INVALID_DOMAIN, f"{domain.strip()!r} is not a valid domain")
        )

    # -- phone: validated only when present --------------------------------
    phone = rec.get("phone_normalized") or rec.get("phone")
    if _present(phone):
        digits = re.sub(r"\D", "", phone)
        if not (_MIN_PHONE_DIGITS <= len(digits) <= _MAX_PHONE_DIGITS):
            issues.append(
                _issue(
                    "phone",
                    INVALID_PHONE,
                    f"phone has {len(digits)} digits; expected "
                    f"{_MIN_PHONE_DIGITS}-{_MAX_PHONE_DIGITS}",
                )
            )

    # -- location: country is required -------------------------------------
    if not _present(rec.get("country")):
        issues.append(
            _issue("country", MISSING_LOCATION, "country is required for a usable lead")
        )

    return ValidationResult(is_valid=not issues, issues=issues)
