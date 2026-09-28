"""Unit tests for the validation stage (pure function, no I/O)."""

from leadforge.pipeline.stages import normalize_record
from leadforge.pipeline.stages.validate import (
    INVALID_COMPANY_NAME,
    INVALID_DOMAIN,
    INVALID_EMAIL,
    INVALID_PHONE,
    INVALID_RECORD,
    ISSUE_CODES,
    MISSING_COMPANY_NAME,
    MISSING_LOCATION,
    validate_record,
)


def valid_record(**overrides):
    """A fully valid normalized record; override fields per test."""
    base = {
        "company_name": "ABC Jewelry LLC",
        "website": "https://www.abcjewelry.com",
        "public_email": "info@abcjewelry.com",
        "phone": "+14155550132",
        "country": "United States",
        "city": "Los Angeles",
    }
    base.update(overrides)
    return normalize_record(base)


def codes(result):
    return [issue["code"] for issue in result.issues]


class TestValidRecords:
    def test_fully_valid(self):
        result = validate_record(valid_record())
        assert result.is_valid is True
        assert result.issues == []

    def test_optional_fields_absent_still_valid(self):
        # Absence lowers the completeness score; it does not invalidate.
        result = validate_record(valid_record(website=None, public_email=None, phone=None))
        assert result.is_valid is True


class TestIndividualInvalidFields:
    def test_missing_company_name(self):
        result = validate_record(valid_record(company_name="   "))
        assert result.is_valid is False
        assert codes(result) == [MISSING_COMPANY_NAME]
        assert result.issues[0]["field"] == "company_name"

    def test_invalid_email(self):
        result = validate_record(valid_record(public_email="not-an-email"))
        assert result.is_valid is False
        assert codes(result) == [INVALID_EMAIL]

    def test_invalid_domain(self):
        result = validate_record(valid_record(website="not a domain"))
        assert result.is_valid is False
        assert codes(result) == [INVALID_DOMAIN]

    def test_invalid_phone_too_short(self):
        result = validate_record(valid_record(phone="123"))
        assert result.is_valid is False
        assert codes(result) == [INVALID_PHONE]

    def test_invalid_phone_too_long(self):
        result = validate_record(valid_record(phone="1" * 20))
        assert result.is_valid is False
        assert codes(result) == [INVALID_PHONE]

    def test_missing_location(self):
        result = validate_record(valid_record(country=None))
        assert result.is_valid is False
        assert codes(result) == [MISSING_LOCATION]

    def test_company_name_with_control_characters(self):
        result = validate_record(valid_record(company_name="ABC\x00Jewelry"))
        assert result.is_valid is False
        assert codes(result) == [INVALID_COMPANY_NAME]


class TestMultipleIssues:
    def test_multiple_simultaneous_issues(self):
        result = validate_record(
            valid_record(company_name="", public_email="bad", country=None)
        )
        assert result.is_valid is False
        assert set(codes(result)) == {
            MISSING_COMPANY_NAME,
            INVALID_EMAIL,
            MISSING_LOCATION,
        }
        assert len(result.issues) == 3

    def test_issue_shape_matches_schema_convention(self):
        result = validate_record(valid_record(public_email="bad"))
        issue = result.issues[0]
        assert set(issue.keys()) == {"field", "code", "message"}
        assert issue["field"] == "public_email"


class TestMalformedRecords:
    def test_non_dict_record(self):
        result = validate_record(["not", "a", "dict"])
        assert result.is_valid is False
        assert codes(result) == [INVALID_RECORD]

    def test_none_record(self):
        result = validate_record(None)
        assert result.is_valid is False
        assert codes(result) == [INVALID_RECORD]


class TestIssueCodesStable:
    def test_closed_code_set(self):
        assert set(ISSUE_CODES) == {
            MISSING_COMPANY_NAME,
            INVALID_COMPANY_NAME,
            INVALID_EMAIL,
            INVALID_DOMAIN,
            INVALID_PHONE,
            MISSING_LOCATION,
            INVALID_RECORD,
        }

    def test_codes_are_upper_snake(self):
        for code in ISSUE_CODES:
            assert code == code.upper()
            assert " " not in code
