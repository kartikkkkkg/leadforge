"""Pure normalization functions for lead records.

Each function is deterministic, has no side effects, and performs no I/O:
no network calls, no database access, no filesystem access.

Conventions
-----------
* ``None`` or blank input  -> ``None`` output (never an invented value).
* Raw input values are never mutated; :func:`normalize_record` returns a new
  dict that preserves every raw key verbatim and *adds* ``normalized_*`` keys.
* Normalization never creates data that was not present in the input: it only
  reformats what is already there.
"""

from __future__ import annotations

import re
from typing import Any

# Collapse any run of whitespace (spaces, tabs, newlines, non-breaking spaces).
_WS_RE = re.compile(r"\s+")

# Common "smart" punctuation mapped to plain ASCII equivalents. This is
# formatting noise, not meaningful content.
_PUNCT_MAP = str.maketrans(
    {
        "\u2018": "'",  # left single quote
        "\u2019": "'",  # right single quote
        "\u201c": '"',  # left double quote
        "\u201d": '"',  # right double quote
        "\u2013": "-",  # en dash
        "\u2014": "-",  # em dash
        "\u00a0": " ",  # non-breaking space
    }
)

# Best-effort country name -> E.164 dial prefix mapping, used only when the
# caller supplies ``default_country`` to :func:`normalize_phone`. A number
# that already carries country information is never rewritten.
_COUNTRY_DIAL_PREFIXES = {
    "united states": "1",
    "canada": "1",
    "united kingdom": "44",
    "ireland": "353",
    "germany": "49",
    "france": "33",
    "netherlands": "31",
    "spain": "34",
    "italy": "39",
    "india": "91",
    "singapore": "65",
    "australia": "61",
    "japan": "81",
    "south korea": "82",
    "china": "86",
    "brazil": "55",
    "mexico": "52",
    "united arab emirates": "971",
}


def _clean(value: str | None) -> str | None:
    """Trim, collapse internal whitespace, and flatten smart punctuation.

    Returns ``None`` for ``None``/blank/non-string input.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    text = value.translate(_PUNCT_MAP)
    text = _WS_RE.sub(" ", text).strip()
    return text or None


def normalize_company_name(name: str | None) -> str | None:
    """Normalize a company name for matching and display keys.

    Strips surrounding whitespace, collapses repeated internal whitespace,
    flattens smart punctuation, strips enclosing quotes, and lowercases.
    Legal/company distinctions (``LLC``, ``Inc.``, ``GmbH`` ...) are
    preserved — only formatting noise is removed.
    """
    text = _clean(name)
    if text is None:
        return None
    # Strip enclosing quotes: '"ABC Jewelry"' -> 'ABC Jewelry'.
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1].strip()
    return text.lower() or None


def normalize_domain(url_or_domain: str | None) -> str | None:
    """Normalize a website URL or bare domain to a bare lowercase domain.

    Removes the protocol (``http://``, ``https://``, ...), a leading
    ``www.``, any path/query/fragment, ports, and a trailing dot.
    Returns ``None`` for blank input or input that cannot be a domain
    (e.g. it contains whitespace). Never invents a domain.
    """
    text = _clean(url_or_domain)
    if text is None:
        return None
    text = text.lower()
    # Strip scheme like "https://", "http://", "ftp://".
    text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", text)
    if text.startswith("www."):
        text = text[4:]
    # Drop path, query string, and fragment.
    text = re.split(r"[/?#]", text, maxsplit=1)[0]
    # Drop an explicit port (":8080"); a bare host is what we match on.
    text = re.sub(r":\d+$", "", text)
    text = text.rstrip(".").strip()
    if not text or any(ch.isspace() for ch in text):
        return None
    return text


def normalize_phone(phone: str | None, default_country: str | None = None) -> str | None:
    """Normalize a phone number to a canonical digit string.

    * Whitespace and common separators (spaces, dashes, dots, parentheses)
      are removed.
    * A leading ``+`` is preserved; a leading ``00`` international prefix is
      converted to ``+``.
    * Extensions (``x123``, ``ext. 123``) are dropped.
    * If the number carries no country information and ``default_country``
      is supplied (e.g. the research job's country), the corresponding dial
      prefix is prepended. Without ``default_country`` no country code is
      ever fabricated.
    """
    text = _clean(phone)
    if text is None:
        return None
    # Drop trailing extensions such as "x123" / "ext. 123".
    text = re.split(r"(?i)\s*(?:ext\.?|x)\s*\d+\s*$", text)[0].strip()
    has_plus = text.startswith("+")
    if not has_plus and text.startswith("00"):
        text = text[2:]
        has_plus = True
    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    if has_plus:
        return f"+{digits}"
    if default_country:
        prefix = _COUNTRY_DIAL_PREFIXES.get(default_country.strip().lower())
        if prefix and not digits.startswith(prefix):
            return f"+{prefix}{digits}"
    return digits


def normalize_email(email: str | None) -> str | None:
    """Normalize an email address: trim whitespace and lowercase.

    Malformed addresses are *not* repaired here — :mod:`validate` rejects
    them instead of silently inventing corrections.
    """
    text = _clean(email)
    if text is None:
        return None
    return text.lower()


def normalize_address(address: str | None) -> str | None:
    """Normalize a free-text address: whitespace and comma-spacing cleanup.

    Meaningful components are preserved as-is. No geocoding, no inference
    of missing parts.
    """
    text = _clean(address)
    if text is None:
        return None
    # "12 Main St ,  Springfield" -> "12 Main St, Springfield"
    text = re.sub(r"\s*,\s*", ", ", text).strip()
    return text or None


def normalize_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Apply field-level normalization to a raw company record.

    Returns a *new* dict: every raw key is preserved verbatim and
    ``normalized_*`` keys are added. Never creates data that was not
    present in the input.

    Added keys
    ----------
    * ``normalized_name``      from ``company_name``
    * ``normalized_domain``    from ``website``
    * ``phone_normalized``     from ``phone``
    * ``email_normalized``     from ``public_email``
    * ``address_normalized``   from ``address``
    * ``country_normalized`` / ``region_normalized`` / ``city_normalized``
      (lowercase match keys for location-aware rules)
    """
    if not isinstance(raw, dict):
        raise TypeError(f"normalize_record expects a dict, got {type(raw).__name__}")
    record: dict[str, Any] = dict(raw)  # shallow copy; input never mutated

    record["normalized_name"] = normalize_company_name(raw.get("company_name"))
    record["normalized_domain"] = normalize_domain(raw.get("website"))
    record["phone_normalized"] = normalize_phone(raw.get("phone"))
    record["email_normalized"] = normalize_email(raw.get("public_email"))
    record["address_normalized"] = normalize_address(raw.get("address"))

    for key in ("country", "region", "city"):
        cleaned = _clean(raw.get(key))
        record[f"{key}_normalized"] = cleaned.lower() if cleaned else None

    return record
