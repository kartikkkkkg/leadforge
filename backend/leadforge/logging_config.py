"""Structured logging with secret redaction.

Every log line carries an ISO-8601 timestamp, level, and logger name. Values that
look like API keys, tokens, secrets, or passwords are masked before they are
emitted — never log credentials.
"""

from __future__ import annotations

import logging
import re
import sys

REDACTED = "***"

# Each pattern captures the secret value in a named group ``secret``.
_REDACT_PATTERNS = [
    # api_key=..., apiKey: "...", password='...'
    re.compile(
        r"(?i)\b(api[_-]?key|client[_-]?secret|secret|access[_-]?token|"
        r"auth[_-]?token|password|passwd)\b\s*[:=]\s*[\"']?(?P<secret>[^\s\"',;}&]+)"
    ),
    # query strings: ?api_key=...&token=...
    re.compile(r"(?i)[?&](?:api[_-]?key|token)=(?P<secret>[^&\s]+)"),
    # Authorization: Bearer <token>
    re.compile(r"(?i)\bBearer\s+(?P<secret>[A-Za-z0-9\-._~+/=]+)"),
]


def redact(text: str) -> str:
    """Mask secret-looking values in a log string."""
    for pattern in _REDACT_PATTERNS:

        def _mask(match: re.Match[str]) -> str:
            secret = match.group("secret")
            return match.group(0).replace(secret, REDACTED, 1)

        text = pattern.sub(_mask, text)
    return text


class RedactingFormatter(logging.Formatter):
    """Formatter that redacts secrets from the final rendered log line."""

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger once (idempotent)."""
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        RedactingFormatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    """Return a module logger (call :func:`setup_logging` once at startup)."""
    return logging.getLogger(name)
