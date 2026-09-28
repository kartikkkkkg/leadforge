"""LeadForge deterministic pipeline stages.

Pure functions implementing the processing core::

    raw record -> normalize -> validate -> deduplicate -> score

No stage performs network calls, database writes, or filesystem I/O.
"""

from .dedupe import (
    EXACT_DOMAIN,
    EXACT_EMAIL,
    FUZZY_NAME,
    FUZZY_REVIEW_THRESHOLD,
    MATCH_RULES,
    NAME_LOCATION,
    DedupeResult,
    DuplicateMatch,
    find_duplicates,
)
from .normalize import (
    normalize_address,
    normalize_company_name,
    normalize_domain,
    normalize_email,
    normalize_phone,
    normalize_record,
)
from .score import COMPLETENESS_WEIGHTS, completeness_band, completeness_score
from .validate import (
    INVALID_COMPANY_NAME,
    INVALID_DOMAIN,
    INVALID_EMAIL,
    INVALID_PHONE,
    INVALID_RECORD,
    ISSUE_CODES,
    MISSING_COMPANY_NAME,
    MISSING_LOCATION,
    ValidationResult,
    validate_record,
)

__all__ = [
    # normalize
    "normalize_company_name",
    "normalize_domain",
    "normalize_phone",
    "normalize_email",
    "normalize_address",
    "normalize_record",
    # validate
    "ValidationResult",
    "validate_record",
    "ISSUE_CODES",
    "MISSING_COMPANY_NAME",
    "INVALID_COMPANY_NAME",
    "INVALID_EMAIL",
    "INVALID_DOMAIN",
    "INVALID_PHONE",
    "MISSING_LOCATION",
    "INVALID_RECORD",
    # dedupe
    "DedupeResult",
    "DuplicateMatch",
    "find_duplicates",
    "MATCH_RULES",
    "EXACT_DOMAIN",
    "EXACT_EMAIL",
    "NAME_LOCATION",
    "FUZZY_NAME",
    "FUZZY_REVIEW_THRESHOLD",
    # score
    "COMPLETENESS_WEIGHTS",
    "completeness_score",
    "completeness_band",
]
