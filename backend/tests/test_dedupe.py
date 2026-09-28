"""Unit tests for the deduplication stage (pure function, no I/O)."""

from leadforge.pipeline.stages.dedupe import (
    EXACT_DOMAIN,
    EXACT_EMAIL,
    FUZZY_NAME,
    NAME_LOCATION,
    find_duplicates,
)
from leadforge.pipeline.stages.normalize import normalize_record


def rec(name, domain=None, email=None, country="United States", city="Springfield", **kw):
    base = {
        "company_name": name,
        "website": f"https://{domain}/" if domain else None,
        "public_email": email,
        "country": country,
        "city": city,
    }
    base.update(kw)
    return normalize_record(base)


class TestExactDuplicates:
    def test_exact_domain_duplicate_removed(self):
        a = rec("ABC Jewelry", domain="abcjewelry.com")
        b = rec("ABC Jewelry Co", domain="www.abcjewelry.com/about")
        result = find_duplicates([a, b])
        assert len(result.unique) == 1
        assert result.unique[0]["company_name"] == "ABC Jewelry"  # first kept
        assert len(result.duplicates) == 1
        dup = result.duplicates[0]
        assert (dup.index, dup.matched_index, dup.rule) == (1, 0, EXACT_DOMAIN)
        assert dup.confidence == 1.0
        assert dup.needs_review is False

    def test_exact_email_duplicate_removed(self):
        a = rec("ABC Jewelry", email="info@abc.com")
        b = rec("Totally Different Name", email="INFO@abc.com")
        result = find_duplicates([a, b])
        assert len(result.unique) == 1
        assert result.duplicates[0].rule == EXACT_EMAIL

    def test_name_location_duplicate_removed(self):
        a = rec("ABC Jewelry", country="United States", city="Springfield")
        b = rec("abc  jewelry", country="united states", city="springfield")
        result = find_duplicates([a, b])
        assert len(result.unique) == 1
        assert result.duplicates[0].rule == NAME_LOCATION

    def test_rule_precedence_domain_before_email(self):
        # Both domain and email match record 0; domain wins by precedence.
        a = rec("ABC", domain="a.com", email="x@a.com")
        b = rec("ABC", domain="a.com", email="x@a.com")
        result = find_duplicates([a, b])
        assert result.duplicates[0].rule == EXACT_DOMAIN

    def test_chain_of_three_duplicates(self):
        records = [rec("ABC", domain="a.com"), rec("ABC", domain="a.com"), rec("ABC", domain="a.com")]
        result = find_duplicates(records)
        assert len(result.unique) == 1
        assert len(result.duplicates) == 2
        assert all(d.matched_index == 0 for d in result.duplicates)


class TestClearlyDifferent:
    def test_different_companies_all_unique(self):
        records = [
            rec("ABC Jewelry", domain="abc.com"),
            rec("XYZ Tools", domain="xyz.com"),
            rec("LMN Foods", domain="lmn.com"),
        ]
        result = find_duplicates(records)
        assert len(result.unique) == 3
        assert result.duplicates == []
        assert result.needs_review == []

    def test_same_name_different_location_is_unique(self):
        a = rec("ABC Jewelry", country="United States", city="Springfield")
        b = rec("ABC Jewelry", country="Canada", city="Toronto")
        result = find_duplicates([a, b])
        # Exact rules need the full name+country+city triple; fuzzy is
        # blocked by the country gate -> both unique.
        assert len(result.unique) == 2
        assert result.duplicates == []
        assert result.needs_review == []


class TestFuzzyMatches:
    def test_fuzzy_duplicate_needs_review_not_removed(self):
        a = rec("ABC Jewelry LLC")
        b = rec("ABC Jewelry Inc")  # similar name, no exact rule fires
        result = find_duplicates([a, b])
        assert len(result.unique) == 2  # kept!
        assert result.duplicates == []
        assert len(result.needs_review) == 1
        review = result.needs_review[0]
        assert review.rule == FUZZY_NAME
        assert review.needs_review is True
        assert review.confidence >= 0.85

    def test_borderline_fuzzy_below_threshold_is_unique(self):
        a = rec("ABC Jewelry and Gemstone Emporium")
        b = rec("XYZ Industrial Tooling Solutions")
        result = find_duplicates([a, b])
        assert len(result.unique) == 2
        assert result.needs_review == []

    def test_fuzzy_match_keeps_record_and_registers_exact_keys(self):
        # B fuzzy-matches A (kept, needs_review). C is an exact domain
        # duplicate of B -> auto-removed as duplicate of B, not A.
        a = rec("ABC Jewelry LLC", domain="a.com")
        b = rec("ABC Jewelry Inc", domain="b.com")
        c = rec("Something Else", domain="b.com")
        result = find_duplicates([a, b, c])
        assert len(result.unique) == 2
        assert len(result.needs_review) == 1
        assert len(result.duplicates) == 1
        assert result.duplicates[0].matched_index == 1


class TestMissingIdentifyingFields:
    def test_records_without_identifiers_are_unique(self):
        a = rec("ABC Jewelry", domain=None, email=None, country=None, city=None)
        b = rec("XYZ Tools", domain=None, email=None, country=None, city=None)
        result = find_duplicates([a, b])
        assert len(result.unique) == 2
        assert result.duplicates == []

    def test_empty_list(self):
        result = find_duplicates([])
        assert result.unique == []
        assert result.duplicates == []
        assert result.needs_review == []

    def test_rejects_non_list(self):
        import pytest

        with pytest.raises(TypeError):
            find_duplicates("not a list")

    def test_fuzzy_scan_skips_kept_records_without_names(self):
        from leadforge.pipeline.stages.normalize import normalize_record

        nameless = normalize_record({"country": "United States"})
        named = normalize_record({"company_name": "ABC Jewelry", "country": "United States"})
        result = find_duplicates([nameless, named])
        assert len(result.unique) == 2
        assert result.needs_review == []

    def test_input_not_mutated(self):
        records = [rec("ABC", domain="a.com"), rec("ABC", domain="a.com")]
        snapshot = [dict(r) for r in records]
        find_duplicates(records)
        assert records == snapshot
