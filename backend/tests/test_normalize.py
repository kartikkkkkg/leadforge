"""Unit tests for the normalization stage (pure functions, no I/O)."""

import pytest

from leadforge.pipeline.stages.normalize import (
    normalize_address,
    normalize_company_name,
    normalize_domain,
    normalize_email,
    normalize_phone,
    normalize_record,
)


class TestNormalizeCompanyName:
    def test_trims_and_collapses_whitespace(self):
        assert normalize_company_name("  ABC   Jewelry\tLLC\n") == "abc jewelry llc"

    def test_lowercases_consistently(self):
        assert normalize_company_name("AbC JeWeLrY") == "abc jewelry"

    def test_preserves_legal_distinctions(self):
        assert normalize_company_name("ABC Jewelry LLC") == "abc jewelry llc"
        assert normalize_company_name("ABC Jewelry Inc.") == "abc jewelry inc."

    def test_strips_enclosing_quotes(self):
        assert normalize_company_name('"ABC Jewelry"') == "abc jewelry"

    def test_flattens_smart_punctuation(self):
        assert normalize_company_name("ABC \u2013 Jewelry \u2019Co\u2019") == "abc - jewelry 'co'"

    def test_empty_and_none(self):
        assert normalize_company_name(None) is None
        assert normalize_company_name("") is None
        assert normalize_company_name("   ") is None

    def test_non_string_input_returns_none(self):
        assert normalize_company_name(123) is None
        assert normalize_company_name(["ABC"]) is None


class TestNormalizeDomain:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("https://www.abcjewelry.com/", "abcjewelry.com"),
            ("http://abcjewelry.com", "abcjewelry.com"),
            ("HTTPS://WWW.ABCJEWELRY.COM/About?x=1#top", "abcjewelry.com"),
            ("www.abcjewelry.com", "abcjewelry.com"),
            ("abcjewelry.com", "abcjewelry.com"),
            ("  AbcJewelry.COM  ", "abcjewelry.com"),
            ("https://shop.abcjewelry.com:8080/sale/", "shop.abcjewelry.com"),
            ("abcjewelry.com.", "abcjewelry.com"),
        ],
    )
    def test_url_variations(self, raw, expected):
        assert normalize_domain(raw) == expected

    def test_empty_and_none(self):
        assert normalize_domain(None) is None
        assert normalize_domain("") is None
        assert normalize_domain("   ") is None

    def test_whitespace_inside_returns_none(self):
        assert normalize_domain("not a domain") is None

    def test_does_not_invent_domain(self):
        # Formatting-only normalization: garbage in -> None, never a guess.
        assert normalize_domain("http://") is None


class TestNormalizePhone:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("(415) 555-0132", "4155550132"),
            ("415.555.0132", "4155550132"),
            ("+1-415-555-0132", "+14155550132"),
            ("0044 20 7946 0958", "+442079460958"),
            ("415 555 0132 x123", "4155550132"),
            ("415-555-0132 ext. 9", "4155550132"),
        ],
    )
    def test_formatting_variants(self, raw, expected):
        assert normalize_phone(raw) == expected

    def test_preserves_country_info(self):
        assert normalize_phone("+91 98765 43210") == "+919876543210"

    def test_default_country_applies_prefix(self):
        assert normalize_phone("4155550132", default_country="United States") == "+14155550132"

    def test_no_country_fabricated_without_default(self):
        assert normalize_phone("4155550132") == "4155550132"

    def test_unknown_default_country_leaves_number_alone(self):
        assert normalize_phone("4155550132", default_country="Atlantis") == "4155550132"

    def test_empty_and_none(self):
        assert normalize_phone(None) is None
        assert normalize_phone("") is None
        assert normalize_phone("no digits here!") is None


class TestNormalizeEmail:
    def test_trims_and_lowercases(self):
        assert normalize_email("  Info@ABCJewelry.COM ") == "info@abcjewelry.com"

    def test_does_not_repair_malformed(self):
        # Repair is validation's job; normalization passes the value through.
        assert normalize_email("not-an-email") == "not-an-email"

    def test_empty_and_none(self):
        assert normalize_email(None) is None
        assert normalize_email("  ") is None


class TestNormalizeAddress:
    def test_whitespace_and_comma_spacing(self):
        assert (
            normalize_address("12  Main St ,Springfield ,  IL")
            == "12 Main St, Springfield, IL"
        )

    def test_preserves_components_verbatim(self):
        assert normalize_address("221B Baker Street, London") == "221B Baker Street, London"

    def test_empty_and_none(self):
        assert normalize_address(None) is None
        assert normalize_address("") is None


class TestNormalizeRecord:
    def test_applies_all_normalizers_and_preserves_raw(self):
        raw = {
            "company_name": "  ABC Jewelry LLC ",
            "website": "https://www.abcjewelry.com/",
            "phone": "(415) 555-0132",
            "public_email": "Info@ABCJewelry.com",
            "address": "12 Main St , Springfield",
            "country": "United States",
            "region": "California",
            "city": "Los Angeles",
            "source_url": "https://example.com/list",
        }
        out = normalize_record(raw)
        # Raw values preserved verbatim...
        assert out["company_name"] == "  ABC Jewelry LLC "
        assert out["website"] == "https://www.abcjewelry.com/"
        # ...normalized variants added.
        assert out["normalized_name"] == "abc jewelry llc"
        assert out["normalized_domain"] == "abcjewelry.com"
        assert out["phone_normalized"] == "4155550132"
        assert out["email_normalized"] == "info@abcjewelry.com"
        assert out["address_normalized"] == "12 Main St, Springfield"
        assert out["country_normalized"] == "united states"
        assert out["region_normalized"] == "california"
        assert out["city_normalized"] == "los angeles"

    def test_does_not_mutate_input(self):
        raw = {"company_name": "ABC", "country": "US"}
        snapshot = dict(raw)
        normalize_record(raw)
        assert raw == snapshot

    def test_missing_fields_yield_none_not_invented_data(self):
        out = normalize_record({"company_name": "ABC"})
        assert out["normalized_name"] == "abc"
        assert out["normalized_domain"] is None
        assert out["phone_normalized"] is None
        assert out["email_normalized"] is None
        assert out["country_normalized"] is None

    def test_rejects_non_dict(self):
        with pytest.raises(TypeError):
            normalize_record(["not", "a", "dict"])
