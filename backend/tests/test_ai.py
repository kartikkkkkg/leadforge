"""Phase 10: optional AI enrichment.

Covers the AIProvider ABC, the NullAIProvider default, the key-gated
LLMProvider (mocked transports only — no real network calls anywhere),
credential hygiene, and the pipeline ENRICH stage: additive-only, tagged
``ai_derived`` fields, raw/source preservation, deterministic scoring
untouched, and graceful degradation when AI fails or is unconfigured.
"""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from leadforge import models
from leadforge.ai import (
    ENV_VAR,
    AIProvider,
    LLMProvider,
    NullAIProvider,
    get_ai_provider,
    tag_ai_fields,
)
from leadforge.ai.llm import SYSTEM_PROMPT
from leadforge.db import session_scope
from leadforge.main import create_app
from leadforge.schemas import JobCreate
from leadforge.services import jobs as job_service


@pytest.fixture
def client(engine):
    app = create_app(engine=engine)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _no_ai_key(monkeypatch):
    """AI tests run keyless unless they explicitly opt in."""
    monkeypatch.delenv(ENV_VAR, raising=False)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class ScriptedAIProvider(AIProvider):
    """Enabled test double returning scripted values and recording calls."""

    name = "scripted"
    enabled = True

    def __init__(self, fail=False, empty=False):
        self.fail = fail
        self.empty = empty
        self.calls: list[tuple[str, dict]] = []

    async def classify_company(self, company, industry):
        self.calls.append(("classify", dict(company)))
        if self.fail:
            raise RuntimeError("boom")
        if self.empty:
            return None
        return f"AI:{industry or 'Unknown'}"

    async def extract_company_information(self, text):
        self.calls.append(("extract", {"text": text}))
        if self.fail:
            raise RuntimeError("boom")
        if self.empty:
            return {}
        return {"city": "Springfield", "note": None}

    async def summarize_company(self, company):
        self.calls.append(("summarize", dict(company)))
        if self.fail:
            raise RuntimeError("boom")
        if self.empty:
            return None
        return f"AI summary of {company.get('company_name')}"


async def _fake_chat_factory(response: str):
    async def fake_chat(system: str, user: str) -> str:
        fake_chat.seen.append((system, user))
        return response

    fake_chat.seen = []
    return fake_chat


def _run_job(engine, ai_provider=None, **overrides):
    payload = {
        "industry": "Jewelry Stores",
        "country": "United States",
        "requested_leads": 10,
        "provider": "demo",
        "demo_delay_ms": 0,
        "enable_ai": True,
    }
    payload.update(overrides)
    with session_scope(engine) as session:
        job = job_service.create_job(session, JobCreate(**payload))
        session.commit()
        job_id = job.id
    return asyncio.run(
        job_service.run_job(job_id, engine=engine, ai_provider=ai_provider, delay_ms=0)
    ), job_id


def _results(engine, job_id):
    with session_scope(engine) as session:
        rows = (
            session.query(models.LeadResearchResult)
            .filter_by(job_id=job_id)
            .order_by(models.LeadResearchResult.id)
            .all()
        )
        return [
            {
                "ai_enriched": r.ai_enriched,
                "ai_fields": r.ai_fields,
                "score": r.quality_score,
                "name": r.company.company_name,
                "website": r.company.website,
            }
            for r in rows
        ]


# ---------------------------------------------------------------------------
# AIProvider ABC
# ---------------------------------------------------------------------------


class TestAIProviderABC:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            AIProvider()

    def test_abstract_methods(self):
        assert set(AIProvider.__abstractmethods__) == {
            "classify_company",
            "extract_company_information",
            "summarize_company",
        }

    def test_concrete_subclass_instantiates(self):
        assert isinstance(ScriptedAIProvider(), AIProvider)


# ---------------------------------------------------------------------------
# NullAIProvider (the default)
# ---------------------------------------------------------------------------


class TestNullAIProvider:
    def test_disabled_by_default(self):
        p = NullAIProvider()
        assert p.enabled is False
        assert p.name == "null"

    def test_works_with_no_key_and_no_network(self):
        p = NullAIProvider()
        assert asyncio.run(p.classify_company({}, "  jewelry store ")) == "Jewelry Stores"
        assert asyncio.run(p.classify_company({}, "")) == "Unknown"
        assert asyncio.run(p.extract_company_information("some text")) is None
        assert asyncio.run(p.summarize_company({})) is None

    def test_classify_is_rule_based_not_inference(self):
        p = NullAIProvider()
        # unknown labels pass through cleaned but unchanged — no guessing
        assert asyncio.run(p.classify_company({}, "Quantum Widgets")) == "Quantum Widgets"


# ---------------------------------------------------------------------------
# get_ai_provider selection
# ---------------------------------------------------------------------------


class TestGetAIProvider:
    def test_no_key_returns_null_provider(self):
        provider = get_ai_provider()
        assert isinstance(provider, NullAIProvider)
        assert provider.enabled is False

    def test_key_returns_llm_provider(self, monkeypatch):
        monkeypatch.setenv(ENV_VAR, "test-key")
        provider = get_ai_provider()
        assert isinstance(provider, LLMProvider)
        assert provider.enabled is True

    def test_blank_key_returns_null_provider(self, monkeypatch):
        monkeypatch.setenv(ENV_VAR, "   ")
        assert isinstance(get_ai_provider(), NullAIProvider)


# ---------------------------------------------------------------------------
# LLMProvider: key gating, mocked transport, malformed input, hygiene
# ---------------------------------------------------------------------------


class TestLLMProvider:
    def test_disabled_without_key(self):
        p = LLMProvider()
        assert p.enabled is False
        assert asyncio.run(p.classify_company({}, "x")) is None
        assert asyncio.run(p.extract_company_information("x")) is None
        assert asyncio.run(p.summarize_company({})) is None

    def test_enabled_with_key(self, monkeypatch):
        monkeypatch.setenv(ENV_VAR, "test-key")
        assert LLMProvider().enabled is True

    def test_mocked_classify(self):
        async def run():
            chat = await _fake_chat_factory(json.dumps({"industry": "Jewelry Stores"}))
            p = LLMProvider(api_key="k", chat=chat)
            assert await p.classify_company({"company_name": "Acme"}, "Jewelry") == (
                "Jewelry Stores"
            )
            system, _user = chat.seen[0]
            assert "Never invent" in system

        asyncio.run(run())

    def test_mocked_extract(self):
        async def run():
            chat = await _fake_chat_factory(
                json.dumps({"city": "Springfield", "phone": None})
            )
            p = LLMProvider(api_key="k", chat=chat)
            assert await p.extract_company_information("Acme in Springfield") == {
                "city": "Springfield",
                "phone": None,
            }

        asyncio.run(run())

    def test_mocked_summarize(self):
        async def run():
            chat = await _fake_chat_factory(json.dumps({"summary": "A jewelry store."}))
            p = LLMProvider(api_key="k", chat=chat)
            assert (
                await p.summarize_company({"company_name": "Acme"})
                == "A jewelry store."
            )

        asyncio.run(run())

    def test_malformed_response_returns_none(self):
        async def run():
            chat = await _fake_chat_factory("this is not json {{{")
            p = LLMProvider(api_key="k", chat=chat)
            assert await p.summarize_company({}) is None
            assert await p.classify_company({}, "x") is None
            assert await p.extract_company_information("x") is None

        asyncio.run(run())

    def test_non_string_response_returns_none(self):
        async def run():
            async def chat(system, user):
                return None  # type: ignore[return-value]

            p = LLMProvider(api_key="k", chat=chat)
            assert await p.summarize_company({}) is None

        asyncio.run(run())

    def test_transport_failure_returns_none(self):
        async def run():
            async def chat(system, user):
                raise ConnectionError("network down")

            p = LLMProvider(api_key="k", chat=chat)
            assert await p.classify_company({}, "x") is None

        asyncio.run(run())

    def test_no_transport_wired_returns_none(self, monkeypatch):
        async def run():
            monkeypatch.setenv(ENV_VAR, "test-key")
            p = LLMProvider()  # key set, but no chat transport
            assert await p.summarize_company({}) is None

        asyncio.run(run())

    def test_system_prompt_forbids_invention(self):
        for phrase in ("Never invent", "return null", "ONLY the information given"):
            assert phrase in SYSTEM_PROMPT

    def test_key_never_in_repr(self):
        p = LLMProvider(api_key="sk-secret-abc123")
        assert "sk-secret-abc123" not in repr(p)
        assert "sk-secret-abc123" not in str(p)

    def test_key_never_logged(self, monkeypatch, caplog):
        async def run():
            async def chat(system, user):
                raise ConnectionError("down")

            p = LLMProvider(api_key="sk-secret-abc123", chat=chat)
            await p.classify_company({}, "x")

        with caplog.at_level("WARNING"):
            asyncio.run(run())
        for record in caplog.records:
            assert "sk-secret-abc123" not in record.getMessage()


    def test_classify_empty_industry_returns_none(self):
        async def run():
            chat = await _fake_chat_factory(json.dumps({"industry": "  "}))
            p = LLMProvider(api_key="k", chat=chat)
            assert await p.classify_company({"company_name": "Acme"}, "Jewelry") is None

        asyncio.run(run())

    def test_classify_missing_industry_key_returns_none(self):
        async def run():
            chat = await _fake_chat_factory(json.dumps({"other": "value"}))
            p = LLMProvider(api_key="k", chat=chat)
            assert await p.classify_company({"company_name": "Acme"}, "Jewelry") is None

        asyncio.run(run())

    def test_summarize_empty_summary_returns_none(self):
        async def run():
            chat = await _fake_chat_factory(json.dumps({"summary": ""}))
            p = LLMProvider(api_key="k", chat=chat)
            assert await p.summarize_company({"company_name": "Acme"}) is None

        asyncio.run(run())

    def test_parse_json_tolerates_markdown_code_fence(self):
        async def run():
            fenced = '```json\n{"industry": "Jewelry Stores"}\n```'
            chat = await _fake_chat_factory(fenced)
            p = LLMProvider(api_key="k", chat=chat)
            assert await p.classify_company({"company_name": "Acme"}, "Jewelry") == (
                "Jewelry Stores"
            )

        asyncio.run(run())


class TestTagAIFiields:
    def test_wraps_each_field(self):
        tagged = tag_ai_fields({"summary": "hello", "city": None})
        assert tagged == {
            "summary": {"value": "hello", "ai_derived": True},
            "city": {"value": None, "ai_derived": True},
        }

    def test_nested_dict_tagged_leaf_by_leaf(self):
        tagged = tag_ai_fields({"extracted": {"city": "Springfield"}})
        assert tagged == {
            "extracted": {"city": {"value": "Springfield", "ai_derived": True}}
        }


# ---------------------------------------------------------------------------
# Pipeline ENRICH stage
# ---------------------------------------------------------------------------


class TestEnrichStage:
    def test_no_key_job_completes_without_ai_fields(self, engine):
        result, job_id = _run_job(engine)
        assert result.status == "completed"
        assert result.accepted == 10
        for row in _results(engine, job_id):
            assert row["ai_enriched"] is False
            assert row["ai_fields"] is None

    def test_stage_order_includes_extract_and_enrich(self, engine):
        seen: list[str] = []
        payload = {
            "industry": "Jewelry Stores",
            "country": "United States",
            "requested_leads": 10,
            "provider": "demo",
            "demo_delay_ms": 0,
            "enable_ai": True,
        }
        with session_scope(engine) as session:
            job = job_service.create_job(session, JobCreate(**payload))
            session.commit()
            job_id = job.id
        asyncio.run(
            job_service.run_job(
                job_id,
                engine=engine,
                delay_ms=0,
                on_progress=lambda stage, _snap: seen.append(stage),
            )
        )
        assert seen == [
            "DISCOVER",
            "EXTRACT",
            "NORMALIZE",
            "VALIDATE",
            "DEDUPLICATE",
            "ENRICH",
            "SCORE",
            "STORE",
            "DONE",
        ]

    def test_mock_ai_enriches_with_tagged_fields(self, engine):
        provider = ScriptedAIProvider()
        _result, job_id = _run_job(engine, ai_provider=provider)
        rows = _results(engine, job_id)
        assert len(rows) == 10
        for row in rows:
            assert row["ai_enriched"] is True
            fields = row["ai_fields"]
            assert fields["summary"] == {
                "value": f"AI summary of {row['name']}",
                "ai_derived": True,
            }
            assert fields["industry_suggestion"]["ai_derived"] is True
            # nested extracted dict tagged leaf-by-leaf
            assert fields["extracted"]["city"] == {
                "value": "Springfield",
                "ai_derived": True,
            }
        # provider saw every accepted record exactly once per method
        assert len([c for c in provider.calls if c[0] == "summarize"]) == 10

    def test_empty_ai_output_leaves_records_unenriched(self, engine):
        provider = ScriptedAIProvider(empty=True)
        result, job_id = _run_job(engine, ai_provider=provider)
        assert result.status == "completed"
        assert result.accepted == 10
        for row in _results(engine, job_id):
            assert row["ai_enriched"] is False
            assert row["ai_fields"] is None

    def test_ai_does_not_touch_source_data_or_scores(self, engine):
        _plain, plain_id = _run_job(engine, enable_ai=False)
        _ai, ai_id = _run_job(engine, ai_provider=ScriptedAIProvider())
        plain = {r["name"]: r for r in _results(engine, plain_id)}
        enriched = {r["name"]: r for r in _results(engine, ai_id)}
        assert set(plain) == set(enriched)
        for name, p_row in plain.items():
            e_row = enriched[name]
            # deterministic completeness scoring is untouched by AI
            assert e_row["score"] == p_row["score"]
            # raw/source company data is preserved verbatim
            assert e_row["website"] == p_row["website"]

    def test_ai_failure_does_not_fail_job(self, engine):
        provider = ScriptedAIProvider(fail=True)
        result, job_id = _run_job(engine, ai_provider=provider)
        assert result.status == "completed"
        assert result.accepted == 10
        for row in _results(engine, job_id):
            assert row["ai_enriched"] is False
            assert row["ai_fields"] is None

    def test_enrich_skipped_when_not_requested(self, engine):
        provider = ScriptedAIProvider()
        _result, job_id = _run_job(engine, ai_provider=provider, enable_ai=False)
        assert provider.calls == []
        for row in _results(engine, job_id):
            assert row["ai_enriched"] is False

    def test_null_provider_never_enriches(self, engine):
        _result, job_id = _run_job(engine, ai_provider=NullAIProvider())
        for row in _results(engine, job_id):
            assert row["ai_enriched"] is False
            assert row["ai_fields"] is None


# ---------------------------------------------------------------------------
# Provider health API
# ---------------------------------------------------------------------------


class TestAIHealth:
    def test_no_key_reports_not_configured(self, client):
        body = client.get("/api/providers/health").json()
        assert body["ai"]["status"] == "not_configured"
        assert "NullAIProvider" in body["ai"]["detail"]

    def test_key_reports_configured_without_probe(self, client, monkeypatch):
        monkeypatch.setenv(ENV_VAR, "test-key")
        body = client.get("/api/providers/health").json()
        assert body["ai"]["status"] == "configured"
        assert "no probe call was made" in body["ai"]["detail"]
        assert "test-key" not in body["ai"]["detail"]
