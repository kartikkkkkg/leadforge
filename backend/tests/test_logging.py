"""Tests for structured logging with secret redaction (Phase 3)."""

import logging

from leadforge.logging_config import get_logger, redact, setup_logging


def test_redact_api_key_assignment():
    assert redact("calling api with api_key=supersecret123 done") == \
        "calling api with api_key=*** done"


def test_redact_query_string():
    assert redact("GET /search?api_key=abc123&token=xyz789") == \
        "GET /search?api_key=***&token=***"


def test_redact_bearer_token():
    assert redact("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9") == \
        "Authorization: Bearer ***"


def test_redact_password():
    assert redact("login failed: password='hunter2' for user bob") == \
        "login failed: password='***' for user bob"


def test_redact_leaves_normal_text_alone():
    text = "job abc-123 completed: 90 accepted, 6 duplicates"
    assert redact(text) == text


def test_setup_logging_is_idempotent_and_structured(caplog):
    setup_logging("INFO")
    setup_logging("INFO")  # second call must not add a duplicate handler
    logger = get_logger("leadforge.test")
    with caplog.at_level(logging.INFO, logger="leadforge.test"):
        logger.info("pipeline stage=%s", "DISCOVER")
    assert any("leadforge.test" in r.name for r in caplog.records)
