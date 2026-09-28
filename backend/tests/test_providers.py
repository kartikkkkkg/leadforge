"""Provider tests: interface, DemoProvider, HttpApiProvider skeleton.

No test touches the network — HTTP behavior is verified with mocks.
"""

import json
import urllib.error

import pytest

from leadforge.providers import (
    CompanyQuery,
    ContactInfo,
    DemoProvider,
    HttpApiProvider,
    NotConfiguredError,
    ProviderError,
    RawCompany,
    ResearchProvider,
    available_providers,
    get_provider,
)
from leadforge.schemas import ProviderHealth


def make_query(**overrides):
    base = {"industry": "Jewelry Stores", "country": "United States"}
    base.update(overrides)
    return CompanyQuery(**base)


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


class TestProviderInterface:
    def test_abstract_cannot_instantiate(self):
        with pytest.raises(TypeError):
            ResearchProvider()  # type: ignore[abstract]

    def test_default_health_is_unknown(self):
        class Minimal(ResearchProvider):
            name = "minimal"

            async def search_companies(self, query, limit):
                return []

            async def get_company_details(self, ref):
                return None

            def extract_contacts(self, raw):
                return ContactInfo()

        health = Minimal().health()
        assert health.name == "minimal"
        assert health.status == "unknown"

    def test_factory(self):
        assert isinstance(get_provider("demo"), DemoProvider)
        assert isinstance(get_provider("http"), HttpApiProvider)
        assert available_providers() == ["demo", "http"]

    def test_factory_unknown_name(self):
        with pytest.raises(ValueError, match="unknown provider"):
            get_provider("scraper")

    def test_raw_company_ignores_internal_fields(self):
        raw = RawCompany(company_name="ABC", demo_ref="demo-0001")
        assert not hasattr(raw, "demo_ref")
        assert raw.company_name == "ABC"


# ---------------------------------------------------------------------------
# DemoProvider
# ---------------------------------------------------------------------------


class TestDemoProvider:
    def test_search_returns_requested_count(self):
        provider = DemoProvider()
        results = _run(provider.search_companies(make_query(), 10))
        assert len(results) == 10

    def test_search_respects_limit_larger_than_matches(self):
        provider = DemoProvider()
        # Toronto records are Legal Services in Canada (deterministic layout).
        results = _run(
            provider.search_companies(
                make_query(industry="Legal Services", country="Canada", city="Toronto"),
                500,
            )
        )
        assert 0 < len(results) <= 500

    def test_deterministic_output(self):
        a = _run(DemoProvider(seed=7).search_companies(make_query(), 25))
        b = _run(DemoProvider(seed=7).search_companies(make_query(), 25))
        assert [r.model_dump() for r in a] == [r.model_dump() for r in b]

    def test_different_seeds_differ(self):
        a = _run(DemoProvider(seed=1).search_companies(make_query(), 25))
        b = _run(DemoProvider(seed=2).search_companies(make_query(), 25))
        assert [r.company_name for r in a] != [r.company_name for r in b]

    def test_every_record_flagged_synthetic(self):
        provider = DemoProvider()
        results = _run(provider.search_companies(make_query(), 100))
        assert len(results) > 0
        for record in results:
            assert record.is_synthetic is True
            assert record.source_provider == "demo"

    def test_synthetic_markers_unmistakable(self):
        provider = DemoProvider()
        results = _run(provider.search_companies(make_query(), 100))
        for record in results:
            if record.website:
                assert ".example.com" in record.website
            if record.public_email:
                assert record.public_email.endswith(".example.com")
            if record.phone:
                assert "555-01" in record.phone

    def test_filter_by_industry(self):
        provider = DemoProvider()
        results = _run(provider.search_companies(make_query(industry="Restaurants"), 100))
        assert len(results) > 0
        assert all(r.industry == "Restaurants" for r in results)

    def test_filter_by_country(self):
        provider = DemoProvider()
        results = _run(
            provider.search_companies(
                make_query(industry="Legal Services", country="Canada"), 100
            )
        )
        assert len(results) > 0
        assert all(r.country == "Canada" for r in results)

    def test_filter_by_region_and_city(self):
        provider = DemoProvider()
        results = _run(
            provider.search_companies(
                make_query(
                    industry="Software Publishers", region="Texas", city="Austin"
                ),
                100,
            )
        )
        assert len(results) > 0
        assert all(r.region == "Texas" and r.city == "Austin" for r in results)

    def test_filter_by_keywords(self):
        provider = DemoProvider()
        # "software" matches the industry of every Software Publishers record.
        results = _run(
            provider.search_companies(
                make_query(industry="Software Publishers", keywords="software"), 100
            )
        )
        assert len(results) > 0
        assert all(
            "software" in f"{r.company_name} {r.industry}".lower() for r in results
        )

    def test_dataset_size(self):
        assert DemoProvider().dataset_size == 100

    def test_filter_by_keywords_no_match(self):
        provider = DemoProvider()
        results = _run(
            provider.search_companies(make_query(keywords="xyznonexistent"), 100)
        )
        assert results == []

    def test_filter_no_matches_returns_empty(self):
        provider = DemoProvider()
        results = _run(provider.search_companies(make_query(city="Atlantis"), 10))
        assert results == []

    def test_zero_limit_returns_empty(self):
        provider = DemoProvider()
        assert _run(provider.search_companies(make_query(), 0)) == []

    def test_get_company_details_found(self):
        provider = DemoProvider()
        record = _run(provider.get_company_details("demo-0007"))
        assert isinstance(record, RawCompany)
        assert record.is_synthetic is True

    def test_get_company_details_missing(self):
        provider = DemoProvider()
        assert _run(provider.get_company_details("demo-9999")) is None
        assert _run(provider.get_company_details("bogus")) is None

    def test_extract_contacts(self):
        provider = DemoProvider()
        record = _run(provider.get_company_details("demo-0000"))
        contacts = provider.extract_contacts(record)
        assert contacts.email == record.public_email
        assert contacts.phone == record.phone

    def test_health_available(self):
        health = DemoProvider().health()
        assert isinstance(health, ProviderHealth)
        assert health.name == "demo"
        assert health.status == "available"


# ---------------------------------------------------------------------------
# HttpApiProvider
# ---------------------------------------------------------------------------


def make_http(**overrides):
    kwargs = {
        "base_url": "https://api.example.com",
        "api_key": "test-key-123",
        "timeout_s": 5.0,
    }
    kwargs.update(overrides)
    return HttpApiProvider(**kwargs)


class TestHttpProviderConfig:
    def test_not_configured_raises_with_instructions(self):
        provider = HttpApiProvider(base_url=None, api_key=None)
        assert provider.is_configured is False
        with pytest.raises(NotConfiguredError, match="LEADFORGE_HTTP_API_KEY"):
            _run(provider.search_companies(make_query(), 10))
        with pytest.raises(NotConfiguredError, match="LEADFORGE_HTTP_API_BASE_URL"):
            _run(provider.get_company_details("x"))

    def test_partially_configured_still_not_configured(self):
        assert HttpApiProvider(base_url="https://x.example", api_key=None).is_configured is False
        assert HttpApiProvider(base_url=None, api_key="k").is_configured is False

    def test_repr_redacts_api_key(self):
        provider = make_http()
        text = repr(provider)
        assert "test-key-123" not in text
        assert "***" in text

    def test_health_not_configured(self):
        health = HttpApiProvider(base_url=None, api_key=None).health()
        assert health.status == "not_configured"
        assert "LEADFORGE_HTTP_API_KEY" in health.detail


class FakeResponse:
    """Minimal urlopen context manager returning canned JSON."""

    def __init__(self, payload, status=200):
        self._body = json.dumps(payload).encode()
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestHttpProviderRequests:
    def test_search_success(self, monkeypatch):
        payload = [
            {"company_name": "Acme Corp", "website": "https://acme.example/"},
            {"company_name": "Beta LLC"},
        ]
        monkeypatch.setattr(
            "urllib.request.urlopen", lambda req, timeout=None: FakeResponse(payload)
        )
        results = _run(make_http().search_companies(make_query(), 10))
        assert len(results) == 2
        assert all(isinstance(r, RawCompany) for r in results)
        assert results[0].company_name == "Acme Corp"

    def test_search_sends_auth_header(self, monkeypatch):
        seen = {}

        def fake_urlopen(req, timeout=None):
            seen["auth"] = req.get_header("Authorization")
            seen["timeout"] = timeout
            return FakeResponse([])

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        _run(make_http().search_companies(make_query(), 5))
        assert seen["auth"] == "Bearer test-key-123"
        assert seen["timeout"] == 5.0

    def test_search_unexpected_payload(self, monkeypatch):
        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda req, timeout=None: FakeResponse({"unexpected": "shape"}),
        )
        results = _run(make_http().search_companies(make_query(), 5))
        assert results == []

    def test_details_success_and_none(self, monkeypatch):
        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda req, timeout=None: FakeResponse({"company_name": "Acme"}),
        )
        record = _run(make_http().get_company_details("acme-1"))
        assert record.company_name == "Acme"

        monkeypatch.setattr(
            "urllib.request.urlopen", lambda req, timeout=None: FakeResponse(None)
        )
        assert _run(make_http().get_company_details("acme-1")) is None

    def test_os_error_maps_to_provider_error(self, monkeypatch):
        def boom(req, timeout=None):
            raise OSError("socket exploded")

        monkeypatch.setattr("urllib.request.urlopen", boom)
        with pytest.raises(ProviderError, match="request failed"):
            _run(make_http().search_companies(make_query(), 5))

    def test_search_items_not_a_list(self, monkeypatch):
        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda req, timeout=None: FakeResponse({"items": "not-a-list"}),
        )
        with pytest.raises(ProviderError, match="unexpected search payload"):
            _run(make_http().search_companies(make_query(), 5))

    def test_details_not_a_dict(self, monkeypatch):
        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda req, timeout=None: FakeResponse([{"company_name": "Acme"}]),
        )
        with pytest.raises(ProviderError, match="unexpected details payload"):
            _run(make_http().get_company_details("acme-1"))

    def test_timeout_maps_to_provider_error(self, monkeypatch):
        def boom(req, timeout=None):
            raise TimeoutError("timed out")

        monkeypatch.setattr("urllib.request.urlopen", boom)
        with pytest.raises(ProviderError, match="timed out"):
            _run(make_http().search_companies(make_query(), 5))

    def test_connection_failure_maps_to_provider_error(self, monkeypatch):
        def boom(req, timeout=None):
            raise urllib.error.URLError("connection refused")

        monkeypatch.setattr("urllib.request.urlopen", boom)
        with pytest.raises(ProviderError, match="unreachable"):
            _run(make_http().search_companies(make_query(), 5))

    def test_http_error_maps_to_provider_error(self, monkeypatch):
        def boom(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

        monkeypatch.setattr("urllib.request.urlopen", boom)
        with pytest.raises(ProviderError, match="HTTP 401"):
            _run(make_http().search_companies(make_query(), 5))

    def test_non_json_response_maps_to_provider_error(self, monkeypatch):
        class BadBody(FakeResponse):
            def read(self):
                return b"<html>not json</html>"

        monkeypatch.setattr(
            "urllib.request.urlopen", lambda req, timeout=None: BadBody({})
        )
        with pytest.raises(ProviderError, match="non-JSON"):
            _run(make_http().search_companies(make_query(), 5))

    def test_error_messages_never_contain_key(self, monkeypatch):
        def boom(req, timeout=None):
            raise urllib.error.URLError("down")

        monkeypatch.setattr("urllib.request.urlopen", boom)
        try:
            _run(make_http().search_companies(make_query(), 5))
        except ProviderError as exc:
            assert "test-key-123" not in str(exc)

    def test_health_available_on_success(self, monkeypatch):
        monkeypatch.setattr(
            "urllib.request.urlopen", lambda req, timeout=None: FakeResponse({})
        )
        assert make_http().health().status == "available"

    def test_health_error_on_failure(self, monkeypatch):
        def boom(req, timeout=None):
            raise urllib.error.URLError("down")

        monkeypatch.setattr("urllib.request.urlopen", boom)
        health = make_http().health()
        assert health.status == "error"
        assert "test-key-123" not in health.detail

    def test_extract_contacts(self):
        contacts = make_http().extract_contacts(
            RawCompany(public_email="a@b.com", phone="123")
        )
        assert (contacts.email, contacts.phone) == ("a@b.com", "123")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _run(coro):
    """Drive an async provider method synchronously in tests."""
    import asyncio

    return asyncio.run(coro)
