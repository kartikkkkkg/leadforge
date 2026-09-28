"""Unit tests for the completeness scoring stage (pure functions, no I/O)."""

import pytest

from leadforge.pipeline.stages.normalize import normalize_record
from leadforge.pipeline.stages.score import (
    COMPLETENESS_WEIGHTS,
    completeness_band,
    completeness_score,
)


def scored(**overrides):
    """Build a normalized record with only the requested fields present."""
    base = {
        "company_name": None,
        "website": None,
        "country": None,
        "phone": None,
        "public_email": None,
        "source_url": None,
        "source_provider": None,
    }
    base.update(overrides)
    return normalize_record(base)


class TestWeights:
    def test_weights_sum_to_100(self):
        assert sum(COMPLETENESS_WEIGHTS.values()) == 100

    def test_weights_match_spec(self):
        assert COMPLETENESS_WEIGHTS == {
            "website": 20,
            "company_name": 20,
            "location": 15,
            "phone": 15,
            "public_email": 20,
            "source": 10,
        }


class TestScoring:
    def test_empty_record_scores_zero(self):
        total, factors = completeness_score(scored())
        assert total == 0
        assert all(v == 0 for v in factors.values())
        assert set(factors) == set(COMPLETENESS_WEIGHTS)

    def test_single_field(self):
        total, factors = completeness_score(scored(company_name="ABC"))
        assert total == 20
        assert factors["company_name"] == 20

    def test_all_fields_scores_100(self):
        total, factors = completeness_score(
            scored(
                company_name="ABC",
                website="https://abc.com",
                country="United States",
                phone="4155550132",
                public_email="info@abc.com",
                source_url="https://example.com",
            )
        )
        assert total == 100
        assert sum(factors.values()) == 100

    def test_factor_breakdown_sums_to_total(self):
        total, factors = completeness_score(
            scored(company_name="ABC", country="United States", public_email="a@b.com")
        )
        assert total == 55
        assert sum(factors.values()) == total

    def test_source_provider_counts_as_source(self):
        total, _ = completeness_score(scored(source_provider="demo"))
        assert total == 10

    def test_normalized_domain_counts_as_website(self):
        total, factors = completeness_score(scored(website="https://www.abc.com/"))
        assert factors["website"] == 20

    def test_blank_strings_do_not_count(self):
        total, _ = completeness_score(scored(company_name="   ", phone=""))
        assert total == 0

    def test_non_dict_scores_zero(self):
        total, factors = completeness_score(None)
        assert total == 0


class TestExactBoundaries:
    def _combo(self, **kw):
        return scored(**kw)

    def test_65_is_low(self):
        # 20 (name) + 20 (website) + 15 (location) + 14? -> use real combos:
        # 20+20+15+10 = 65 (Low); 20+20+15+20 = 75 (Medium)
        total, _ = completeness_score(
            self._combo(company_name="A", website="https://a.com", country="US",
                        source_url="https://x.com")
        )
        assert total == 65
        assert completeness_band(total) == "Low"

    def test_70_is_medium(self):
        # 20+20+15+15 = 70
        total, _ = completeness_score(
            self._combo(company_name="A", website="https://a.com", country="US",
                        phone="4155550132")
        )
        assert total == 70
        assert completeness_band(total) == "Medium"

    def test_85_is_medium(self):
        # 20 (name) + 20 (website) + 15 (location) + 20 (email) + 10 (source) = 85
        total, _ = completeness_score(
            self._combo(company_name="A", website="https://a.com", country="US",
                        public_email="a@b.com", source_url="https://x.com")
        )
        assert total == 85
        assert completeness_band(total) == "Medium"

    def test_90_is_high(self):
        # 20+20+15+15+20 = 90
        total, _ = completeness_score(
            self._combo(company_name="A", website="https://a.com", country="US",
                        phone="4155550132", public_email="a@b.com")
        )
        assert total == 90
        assert completeness_band(total) == "High"

    def test_100_is_high(self):
        total, _ = completeness_score(
            self._combo(company_name="A", website="https://a.com", country="US",
                        phone="1", public_email="a@b.com", source_url="https://x.com")
        )
        assert total == 100
        assert completeness_band(total) == "High"


class TestBands:
    @pytest.mark.parametrize(
        "score,expected",
        [(100, "High"), (90, "High"), (89, "Medium"), (70, "Medium"), (69, "Low"), (0, "Low")],
    )
    def test_band_mapping(self, score, expected):
        assert completeness_band(score) == expected
