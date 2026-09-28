"""CSV + styled XLSX export engine (Phase 7).

Single source of truth for every export surface (API, CLI, Makefile): the
export service owns column ordering, filename sanitization, CSV formatting,
and XLSX styling. Callers never build exports themselves.

DESIGN.md §10:
- CSV: UTF-8 with BOM, header row = the 14 result columns, one row per
  accepted record, ``is_synthetic`` included for honesty.
- XLSX (openpyxl): sheet 1 ``Leads`` — styled header (bold, fill, bottom
  border), auto-filter, frozen top row, sensible column widths, score as a
  number with a band label, validation/verification status columns, source
  URL as a hyperlink, collection date formatted; sheet 2
  ``Research Summary`` — totals (discovered/accepted/duplicates/invalid),
  average completeness, research parameters, timestamp; sheet 3
  ``Parameters`` — the exact job inputs.
  Filename: ``leadforge_<industry>_<jobshortid>.xlsx``.

Rendering is deterministic: fixed column order, rows ordered by
``collected_at`` (then id), no timestamps inside the payload except the
explicit "Exported at" summary cell. The same inputs always produce the
same bytes, which is what the tests assert.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session, joinedload

from .. import models
from ..pipeline.stages.score import completeness_band

# ---------------------------------------------------------------------------
# public constants
# ---------------------------------------------------------------------------

#: The 14 result columns (DESIGN.md §10). Fixed order, used by CSV and as the
#: base of the XLSX ``Leads`` sheet. ``is_synthetic`` is included for honesty.
EXPORT_COLUMNS: tuple[str, ...] = (
    "company_name",
    "website",
    "industry",
    "country",
    "region",
    "city",
    "address",
    "phone",
    "public_email",
    "linkedin_url",
    "source_url",
    "quality_score",
    "validation_status",
    "is_synthetic",
)

#: Extra XLSX-only columns appended after the 14 base columns: the score band
#: label (§10 "score as number with conditional band label"), the
#: verification status column, and the formatted collection date.
XLSX_EXTRA_COLUMNS: tuple[str, ...] = (
    "score_band",
    "verification_status",
    "collected_at",
)

XLSX_LEADS_COLUMNS: tuple[str, ...] = EXPORT_COLUMNS + XLSX_EXTRA_COLUMNS

EXPORT_FORMATS: tuple[str, ...] = ("csv", "xlsx")

EXPORT_MEDIA_TYPES: dict[str, str] = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

_CSV_BOM = b"\xef\xbb\xbf"
_CSV_LINE_TERMINATOR = "\r\n"  # Excel-friendly line endings


# ---------------------------------------------------------------------------
# rows
# ---------------------------------------------------------------------------


def fetch_export_rows(session: Session, job_id: str) -> list[dict[str, Any]]:
    """Load a job's accepted results as plain row dicts, deterministic order.

    One dict per ``LeadResearchResult``, keys covering ``XLSX_LEADS_COLUMNS``
    (a superset of the CSV columns). Rows are ordered by ``collected_at``
    then id — the order the pipeline stored them — so repeated exports of the
    same job produce identical output.
    """
    results = (
        session.query(models.LeadResearchResult)
        .options(joinedload(models.LeadResearchResult.company))
        .filter(models.LeadResearchResult.job_id == job_id)
        .order_by(
            models.LeadResearchResult.collected_at.asc(),
            models.LeadResearchResult.id.asc(),
        )
        .all()
    )
    return [_row_for(result) for result in results]


def _row_for(result: models.LeadResearchResult) -> dict[str, Any]:
    company = result.company
    return {
        "company_name": company.company_name,
        "website": company.website,
        "industry": company.industry,
        "country": company.country,
        "region": company.region,
        "city": company.city,
        "address": company.address,
        "phone": company.phone,
        "public_email": company.public_email,
        "linkedin_url": company.linkedin_url,
        "source_url": company.source_url,
        "quality_score": result.quality_score,
        "validation_status": result.validation_status,
        "is_synthetic": company.is_synthetic,
        "score_band": completeness_band(result.quality_score),
        "verification_status": result.verification_status,
        "collected_at": result.collected_at,
    }


def _csv_cell(value: Any) -> str:
    """Render one CSV cell: null/None -> empty, bool -> true/false."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    return str(value)


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def render_csv(rows: list[dict[str, Any]]) -> bytes:
    """Render rows as UTF-8-with-BOM CSV (bytes, ready for download)."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator=_CSV_LINE_TERMINATOR)
    writer.writerow(EXPORT_COLUMNS)
    for row in rows:
        writer.writerow([_csv_cell(row[col]) for col in EXPORT_COLUMNS])
    return _CSV_BOM + buffer.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------
# XLSX
# ---------------------------------------------------------------------------

_HEADER_FONT = Font(bold=True, color="1F2937")
_HEADER_FILL = PatternFill(start_color="E5E7EB", fill_type="solid")
_HEADER_BORDER = Border(bottom=Side(style="thin", color="9CA3AF"))
_TITLE_FONT = Font(bold=True, size=14, color="111827")
_LINK_FONT = Font(color="1D4ED8", underline="single")
_DATE_FORMAT = "yyyy-mm-dd hh:mm:ss"
_MAX_COLUMN_WIDTH = 50


def _style_header_row(ws, n_columns: int) -> None:
    for col in range(1, n_columns + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.border = _HEADER_BORDER


def _autosize_columns(ws, headers: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    for idx, header in enumerate(headers, start=1):
        width = len(header)
        for row in rows:
            value = row.get(header)
            text = "" if value is None else str(value)
            width = max(width, min(len(text), _MAX_COLUMN_WIDTH))
        # Dates/URLs get breathing room; the score columns stay compact.
        width = max(12, min(width + 2, _MAX_COLUMN_WIDTH))
        ws.column_dimensions[get_column_letter(idx)].width = width


def _build_leads_sheet(wb: Workbook, rows: list[dict[str, Any]]) -> None:
    ws = wb.active
    ws.title = "Leads"
    ws.append(list(XLSX_LEADS_COLUMNS))
    _style_header_row(ws, len(XLSX_LEADS_COLUMNS))
    for row in rows:
        ws.append([row.get(col) for col in XLSX_LEADS_COLUMNS])

    # Source URL as a real hyperlink (blue, underlined); collection date formatted.
    url_col = XLSX_LEADS_COLUMNS.index("source_url") + 1
    date_col = XLSX_LEADS_COLUMNS.index("collected_at") + 1
    for r in range(2, ws.max_row + 1):
        url_cell = ws.cell(row=r, column=url_col)
        if url_cell.value:
            url_cell.hyperlink = str(url_cell.value)
            url_cell.font = _LINK_FONT
        date_cell = ws.cell(row=r, column=date_col)
        if isinstance(date_cell.value, datetime):
            date_cell.number_format = _DATE_FORMAT

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    _autosize_columns(ws, XLSX_LEADS_COLUMNS, rows)


def _build_summary_sheet(
    wb: Workbook, job: models.ResearchJob, rows: list[dict[str, Any]]
) -> None:
    ws = wb.create_sheet("Research Summary")
    ws["A1"] = "LeadForge research summary"
    ws["A1"].font = _TITLE_FONT

    scores = [
        row["quality_score"]
        for row in rows
        if isinstance(row.get("quality_score"), int)
    ]
    avg = round(sum(scores) / len(scores), 1) if scores else None

    summary_rows: list[tuple[str, Any]] = [
        ("Job ID", job.id),
        ("Industry", job.industry),
        ("Country", job.country),
        ("Region", job.region or ""),
        ("City", job.city or ""),
        ("Requested leads", job.requested_leads),
        ("Provider", job.provider),
        ("AI enrichment", "Enabled" if job.enable_ai else "Disabled"),
        ("Discovered", job.discovered),
        ("Accepted", job.accepted),
        ("Duplicates removed", job.duplicates),
        ("Invalid", job.invalid),
        ("Average completeness", avg if avg is not None else "n/a"),
        (
            "Exported at (UTC)",
            datetime.now(timezone.utc)
            .replace(tzinfo=None)
            .isoformat(sep=" ", timespec="seconds"),
        ),
    ]
    for label, value in summary_rows:
        ws.append([label, value])
    for r in range(3, ws.max_row + 1):
        ws.cell(row=r, column=1).font = Font(bold=True)
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 48


def _build_parameters_sheet(wb: Workbook, job: models.ResearchJob) -> None:
    ws = wb.create_sheet("Parameters")
    ws.append(["parameter", "value"])
    _style_header_row(ws, 2)
    for name in (
        "industry",
        "country",
        "region",
        "city",
        "keywords",
        "requested_leads",
        "provider",
        "enable_ai",
        "demo_delay_ms",
    ):
        value = getattr(job, name)
        ws.append([name, "" if value is None else value])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 48


def render_xlsx(job: models.ResearchJob, rows: list[dict[str, Any]]) -> bytes:
    """Render rows as a styled 3-sheet XLSX workbook (bytes, ready for download)."""
    wb = Workbook()
    _build_leads_sheet(wb, rows)
    _build_summary_sheet(wb, job, rows)
    _build_parameters_sheet(wb, job)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# filenames
# ---------------------------------------------------------------------------


def _sanitize_filename_part(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "job"


def export_filename(job: models.ResearchJob, format: str) -> str:
    """``leadforge_<industry>_<jobshortid>.<format>`` (DESIGN.md §10).

    The industry slug and the first 8 hex chars of the job id are safe on all
    normal filesystems, so the API can use a plain ``filename="..."``
    Content-Disposition without RFC 5987 encoding.
    """
    if format not in EXPORT_FORMATS:
        raise ValueError(f"unsupported export format {format!r}")
    short_id = job.id.replace("-", "")[:8]
    return f"leadforge_{_sanitize_filename_part(job.industry)}_{short_id}.{format}"
