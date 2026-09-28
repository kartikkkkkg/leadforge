"""Pipeline orchestration: DISCOVER -> EXTRACT -> NORMALIZE -> VALIDATE ->
DEDUPLICATE -> ENRICH -> SCORE -> STORE.

The runner wires the provider layer (Phase 5) to the deterministic processing
stages (Phase 4) and persists via the existing SQLAlchemy models. Stages stay
independent — the runner *calls* the stage functions, never reimplements them.

AI enrichment (Phase 10)
------------------------
ENRICH is optional and strictly additive. It may attach tagged, AI-derived
fields (``{"value": ..., "ai_derived": True}``) to a result row — it never
modifies normalized records, never influences validation, deduplication, or
completeness scoring, and never converts AI output into source facts. When no
AI provider is enabled (the default) or the job did not request AI, ENRICH is
a no-op milestone. An AI failure degrades to ``ai_enriched=False``; the job
still completes.

Transaction boundaries (documented choice)
------------------------------------------
* Stage execution (discover/extract/normalize/validate/dedupe/enrich/score) is
  side-effect free: no database writes happen until STORE.
* STORE runs in a **single transaction**: companies, results, and rejected
  records are committed atomically. A store failure rolls everything back —
  no corrupt partial state.
* Job status transitions (queued -> running -> completed/failed) and progress
  milestones are committed in **separate small transactions**, so a failed job
  is always recorded as failed even when the store transaction rolled back.

No exports, no frontend coupling here.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from .. import models
from ..ai import AIProvider, get_ai_provider, tag_ai_fields
from ..db import get_engine, session_scope
from ..pipeline.stages import (
    completeness_score,
    find_duplicates,
    normalize_record,
    validate_record,
)
from ..providers import CompanyQuery, RawCompany, ResearchProvider, get_provider

log = logging.getLogger(__name__)

# job.stage values. progress_pct is a coarse *stage* milestone, not a precise
# fraction — the counters (discovered/invalid/duplicates/accepted) carry the
# exact numbers.
_STAGE_PROGRESS: dict[str, int] = {
    "DISCOVER": 12,
    "EXTRACT": 24,
    "NORMALIZE": 36,
    "VALIDATE": 48,
    "DEDUPLICATE": 60,
    "ENRICH": 70,
    "SCORE": 80,
    "STORE": 90,
}
_DONE_STAGE = "DONE"

_RUNNABLE_STATUSES = ("queued", "failed")  # failed jobs may be retried


class JobNotFoundError(LookupError):
    """No research job exists for the given id."""


class JobNotRunnableError(RuntimeError):
    """The job is not in a runnable state (already running/completed)."""


@dataclass
class JobResult:
    """Outcome of a finished pipeline run."""

    job_id: str
    status: str  # "completed" | "failed"
    discovered: int = 0
    processed: int = 0
    accepted: int = 0
    duplicates: int = 0
    invalid: int = 0
    needs_review: int = 0
    error: str | None = None


ProgressCallback = Callable[[str, dict[str, Any]], None]
"""Called after each stage: ``(stage_name, snapshot_dict)``."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class JobRunner:
    """Abstract pipeline runner."""

    async def run(self, job_id: str) -> JobResult:
        raise NotImplementedError


class PipelineRunner(JobRunner):
    """Executes a research job through the eight pipeline stages."""

    def __init__(
        self,
        engine=None,
        provider: ResearchProvider | None = None,
        ai_provider: AIProvider | None = None,
        delay_ms: int = 0,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        self._engine = engine or get_engine()
        self._provider = provider
        self._ai_provider = ai_provider
        self._delay_ms = max(0, delay_ms)
        self._on_progress = on_progress

    # -- public API ----------------------------------------------------------

    async def run(self, job_id: str) -> JobResult:
        """Run the full pipeline for ``job_id``.

        Records the failure on the job and re-raises — never swallows.
        """
        spec = self._start_job(job_id)  # marks running; raises if not runnable
        try:
            raws = await self._discover(spec)
            extracted = self._extract(spec, raws)  # aligned with `normalized`
            normalized = self._normalize(spec, raws)
            payload_by_id = {
                id(record): extracted[i] for i, record in enumerate(normalized)
            }
            valid, invalid, raw_by_index = self._validate(spec, normalized, raws)
            deduped = self._deduplicate(spec, valid)
            enriched = await self._enrich(spec, deduped.unique, payload_by_id)
            scored = self._score(spec, deduped.unique)
            stats = await self._store(
                spec, raws, valid, invalid, raw_by_index, deduped, enriched, scored
            )
        except Exception as exc:
            self._mark_failed(job_id, exc)
            raise
        self._mark_completed(job_id, stats)
        return JobResult(job_id=job_id, status="completed", **stats)

    # -- job lifecycle -------------------------------------------------------

    def _start_job(self, job_id: str) -> dict[str, Any]:
        """Load the job, refuse non-runnable states, mark it running.

        Returns a detached dict of the fields the run needs.
        """
        with session_scope(self._engine) as session:
            job = session.get(models.ResearchJob, job_id)
            if job is None:
                raise JobNotFoundError(f"no research job {job_id!r}")
            if job.status not in _RUNNABLE_STATUSES:
                raise JobNotRunnableError(
                    f"job {job_id!r} is {job.status!r}; only "
                    f"{'/'.join(_RUNNABLE_STATUSES)} jobs can run"
                )
            job.status = "running"
            job.stage = "DISCOVER"
            job.progress_pct = 5
            job.error = None
            job.completed_at = None
            spec = {
                "job_id": job.id,
                "industry": job.industry,
                "country": job.country,
                "region": job.region,
                "city": job.city,
                "keywords": job.keywords,
                "requested_leads": job.requested_leads,
                "provider_name": job.provider,
                "enable_ai": bool(job.enable_ai),
            }
        return spec

    def _set_progress(
        self, job_id: str, stage: str, counters: dict[str, int] | None = None
    ) -> None:
        with session_scope(self._engine) as session:
            job = session.get(models.ResearchJob, job_id)
            if job is None:  # pragma: no cover - defensive
                return
            job.stage = stage
            job.progress_pct = _STAGE_PROGRESS.get(stage, job.progress_pct)
            for key, value in (counters or {}).items():
                if hasattr(job, key):
                    setattr(job, key, value)
        if self._on_progress:
            self._on_progress(stage, {"job_id": job_id, **(counters or {})})

    def _mark_failed(self, job_id: str, exc: BaseException) -> None:
        # Secret-safe by contract: provider errors never carry credentials.
        detail = f"{type(exc).__name__}: {exc}"
        log.error("job %s failed: %s", job_id, detail)
        with session_scope(self._engine) as session:
            job = session.get(models.ResearchJob, job_id)
            if job is None:  # pragma: no cover - defensive
                return
            job.status = "failed"
            job.error = detail[:2000]

    def _mark_completed(self, job_id: str, stats: dict[str, int]) -> None:
        with session_scope(self._engine) as session:
            job = session.get(models.ResearchJob, job_id)
            if job is None:  # pragma: no cover - defensive
                return
            job.status = "completed"
            job.stage = _DONE_STAGE
            job.progress_pct = 100
            job.completed_at = _utcnow()
            for key in ("discovered", "processed", "accepted", "duplicates", "invalid"):
                setattr(job, key, stats.get(key, 0))
        if self._on_progress:
            self._on_progress(_DONE_STAGE, {"job_id": job_id, **stats})

    # -- stages ---------------------------------------------------------------

    async def _maybe_delay(self) -> None:
        if self._delay_ms > 0:
            await asyncio.sleep(self._delay_ms / 1000)

    def _resolve_provider(self, spec: dict[str, Any]) -> ResearchProvider:
        if self._provider is not None:
            return self._provider
        return get_provider(spec["provider_name"])

    async def _discover(self, spec: dict[str, Any]) -> list[RawCompany]:
        provider = self._resolve_provider(spec)
        query = CompanyQuery(
            industry=spec["industry"],
            country=spec["country"],
            region=spec["region"],
            city=spec["city"],
            keywords=spec["keywords"],
        )
        raws = await provider.search_companies(query, spec["requested_leads"])
        self._set_progress(spec["job_id"], "DISCOVER", {"discovered": len(raws)})
        await self._maybe_delay()
        return list(raws)

    def _extract(
        self, spec: dict[str, Any], raws: list[RawCompany]
    ) -> list[dict[str, Any]]:
        """Build the deterministic enrichment input for each raw record.

        Concatenates the record's already-available public fields into a
        ``source_text`` blob the ENRICH stage may feed to the AI provider.
        Purely deterministic — no network, no invention, no mutation.
        """
        extracted = []
        for raw in raws:
            data = raw.model_dump()
            parts = [
                str(data.get(key))
                for key in (
                    "company_name",
                    "website",
                    "industry",
                    "address",
                    "city",
                    "region",
                    "country",
                    "phone",
                    "public_email",
                )
                if data.get(key)
            ]
            extracted.append({"source_text": " | ".join(parts)})
        self._set_progress(spec["job_id"], "EXTRACT")
        return extracted

    def _normalize(self, spec: dict[str, Any], raws: list[RawCompany]) -> list[dict[str, Any]]:
        normalized = [normalize_record(raw.model_dump()) for raw in raws]
        self._set_progress(spec["job_id"], "NORMALIZE")
        return normalized

    def _validate(
        self, spec: dict[str, Any], normalized: list[dict[str, Any]], raws: list[RawCompany]
    ) -> tuple[list[dict[str, Any]], list[tuple[int, list[dict[str, str]]]], dict[int, dict[str, Any]]]:
        """Split into valid records and ``(index, issues)`` pairs for the invalid.

        Also returns the original raw dicts keyed by index for rejection rows.
        """
        valid: list[dict[str, Any]] = []
        invalid: list[tuple[int, list[dict[str, str]]]] = []
        raw_by_index = {i: raw.model_dump() for i, raw in enumerate(raws)}
        for i, record in enumerate(normalized):
            result = validate_record(record)
            if result.is_valid:
                valid.append(record)
            else:
                invalid.append((i, result.issues))
        self._set_progress(spec["job_id"], "VALIDATE", {"invalid": len(invalid)})
        return valid, invalid, raw_by_index

    def _deduplicate(self, spec: dict[str, Any], valid: list[dict[str, Any]]):
        deduped = find_duplicates(valid)
        self._set_progress(
            spec["job_id"], "DEDUPLICATE", {"duplicates": len(deduped.duplicates)}
        )
        return deduped

    async def _enrich(
        self,
        spec: dict[str, Any],
        unique: list[dict[str, Any]],
        payload_by_id: dict[int, dict[str, Any]],
    ) -> list[dict[str, Any] | None]:
        """Optionally enrich each unique record with tagged AI-derived fields.

        Returns a list aligned with ``unique``: a tagged ``ai_fields`` dict
        per enriched record, ``None`` where nothing was produced. The stage is
        a no-op when the job did not request AI or no AI provider is enabled.
        AI failures degrade per-record to ``None`` — the job never fails
        because of AI. Normalized records are never mutated here.
        """
        job_id = spec["job_id"]
        empty: list[dict[str, Any] | None] = [None] * len(unique)
        if not spec.get("enable_ai"):
            self._set_progress(job_id, "ENRICH")
            return empty
        provider = self._ai_provider or get_ai_provider()
        if not provider.enabled:
            log.info(
                "job %s requested AI enrichment but no AI provider is enabled",
                job_id,
            )
            self._set_progress(job_id, "ENRICH")
            return empty

        # ``unique`` holds the same dict objects as the normalized list, so the
        # identity map built in run() finds each record's extraction payload.
        results: list[dict[str, Any] | None] = []
        for record in unique:
            results.append(
                await self._enrich_one(
                    provider, record, payload_by_id.get(id(record), {})
                )
            )
        self._set_progress(job_id, "ENRICH")
        await self._maybe_delay()
        return results

    async def _enrich_one(
        self,
        provider: AIProvider,
        record: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Enrich one record; ``None`` when nothing usable came back."""
        try:
            industry = await provider.classify_company(
                record, str(record.get("industry") or "")
            )
            info = await provider.extract_company_information(
                payload.get("source_text", "")
            )
            summary = await provider.summarize_company(record)
        except Exception as exc:  # AI must never fail the job
            log.warning(
                "AI enrichment failed for a record: %s", type(exc).__name__
            )
            return None
        fields: dict[str, Any] = {}
        if industry:
            fields["industry_suggestion"] = industry
        if isinstance(info, dict) and info:
            fields["extracted"] = info
        if summary:
            fields["summary"] = summary
        if not fields:
            return None
        return tag_ai_fields(fields)

    def _score(
        self, spec: dict[str, Any], unique: list[dict[str, Any]]
    ) -> list[tuple[int, dict[str, int]]]:
        scored = [completeness_score(record) for record in unique]
        self._set_progress(spec["job_id"], "SCORE")
        return scored

    # -- store: one atomic transaction ------------------------------------------

    async def _store(
        self,
        spec: dict[str, Any],
        raws: list[RawCompany],
        valid: list[dict[str, Any]],
        invalid: list[tuple[int, list[dict[str, str]]]],
        raw_by_index: dict[int, dict[str, Any]],
        deduped,
        enriched: list[dict[str, Any] | None],
        scored: list[tuple[int, dict[str, int]]],
    ) -> dict[str, int]:
        job_id = spec["job_id"]
        removed = {m.index for m in deduped.duplicates}
        needs_review = {m.index for m in deduped.needs_review}

        self._set_progress(job_id, "STORE")
        with session_scope(self._engine) as session:
            job = session.get(models.ResearchJob, job_id)
            if job is None:  # pragma: no cover - defensive
                raise JobNotFoundError(f"no research job {job_id!r}")

            # 1. rejected: invalid records (validation stage)
            for index, issues in invalid:
                session.add(
                    models.RejectedRecord(
                        job=job,
                        stage="validate",
                        reason="; ".join(i["code"] for i in issues),
                        raw_data=raw_by_index[index],
                    )
                )

            # 2. rejected: exact duplicates (deduplicate stage)
            for match in deduped.duplicates:
                session.add(
                    models.RejectedRecord(
                        job=job,
                        stage="deduplicate",
                        reason=(
                            f"{match.rule} duplicate of input record "
                            f"#{match.matched_index} (confidence {match.confidence})"
                        ),
                        raw_data=raw_by_index[match.index],
                    )
                )

            # 3. companies + results for the unique records (order preserved)
            accepted = 0
            score_iter = iter(scored)
            enrich_iter = iter(enriched)  # aligned with `unique`, like `scored`
            for i, record in enumerate(valid):
                if i in removed:
                    continue
                score, factors = next(score_iter)
                ai_fields = next(enrich_iter)
                company = models.Company(
                    company_name=record.get("company_name") or "",
                    normalized_name=record.get("normalized_name"),
                    website=record.get("website"),
                    normalized_domain=record.get("normalized_domain"),
                    industry=record.get("industry"),
                    country=record.get("country"),
                    region=record.get("region"),
                    city=record.get("city"),
                    address=record.get("address"),
                    phone=record.get("phone"),
                    phone_normalized=record.get("phone_normalized"),
                    public_email=record.get("public_email"),
                    linkedin_url=record.get("linkedin_url"),
                    source_url=record.get("source_url"),
                    source_provider=record.get("source_provider")
                    or spec["provider_name"],
                    is_synthetic=bool(record.get("is_synthetic")),
                )
                session.add(company)
                session.flush()  # assign company.id for the result row
                session.add(
                    models.LeadResearchResult(
                        job=job,
                        company=company,
                        quality_score=score,
                        score_factors=factors,
                        validation_status="valid",
                        validation_issues=[],
                        verification_status="unverified",
                        ai_enriched=ai_fields is not None,
                        ai_fields=ai_fields,
                        dedupe_status=(
                            "needs_review" if i in needs_review else "unique"
                        ),
                    )
                )
                accepted += 1

            stats = {
                "discovered": len(raws),
                "processed": len(invalid) + len(deduped.duplicates) + accepted,
                "accepted": accepted,
                "duplicates": len(deduped.duplicates),
                "invalid": len(invalid),
                "needs_review": len(needs_review),
            }
            # Counters land on the job row inside the same transaction.
            job.discovered = stats["discovered"]
            job.processed = stats["processed"]
            job.accepted = stats["accepted"]
            job.duplicates = stats["duplicates"]
            job.invalid = stats["invalid"]

        await self._maybe_delay()
        return stats
