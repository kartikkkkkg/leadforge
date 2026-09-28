"""LeadForge command-line interface.

Commands:
    seed-demo   load the 100-company synthetic dataset
    reset-demo  wipe demo data (``--reseed`` to re-seed afterwards)
    run-demo    run the research pipeline headless
    export      export a completed job's dataset (CSV or styled XLSX)
    serve       run the API server
    worker      explain why no separate worker process exists (DESIGN.md A2)

Background execution: research jobs run in-process on the API server via
FastAPI BackgroundTasks (``services/jobs.run_job``). By design there is no
Celery/Redis queue and no separate worker container — see DESIGN.md A2.
``docker-compose.yml`` therefore runs only db + backend + frontend.
"""

from __future__ import annotations

import argparse
import asyncio


def _engine_with_tables():
    """Engine with all tables created (CLI entry point, no app lifespan)."""
    from .db import get_engine, init_db

    engine = get_engine()
    init_db(engine)
    return engine


def _cmd_seed_demo(args: argparse.Namespace) -> int:
    from .db import session_scope
    from .services import demo as demo_service

    engine = _engine_with_tables()
    with session_scope(engine) as session:
        count = demo_service.seed_demo_companies(session)
    print(f"Seeded {count} synthetic companies (demo dataset).")
    return 0


def _cmd_reset_demo(args: argparse.Namespace) -> int:
    from .db import session_scope
    from .services import demo as demo_service

    engine = _engine_with_tables()
    with session_scope(engine) as session:
        outcome = demo_service.reset_demo_data(session, reseed=args.reseed)
    print(
        f"Reset demo data: {outcome['jobs_deleted']} jobs, "
        f"{outcome['results_deleted']} results, "
        f"{outcome['rejected_records_deleted']} rejected records, "
        f"{outcome['companies_deleted']} companies deleted."
    )
    if outcome["reseeded"]:
        print(f"Re-seeded {outcome['companies']} synthetic companies.")
    return 0


def _cmd_run_demo(args: argparse.Namespace) -> int:
    from .db import session_scope
    from .schemas import JobCreate
    from .services import jobs as job_service

    engine = _engine_with_tables()
    create = JobCreate(
        industry=args.industry,
        country=args.country,
        region=args.region,
        city=args.city,
        keywords=args.keywords,
        requested_leads=args.leads,
        provider="demo",
        demo_delay_ms=0 if args.no_delay else 120,
    )
    with session_scope(engine) as session:
        job = job_service.create_job(session, create)
        session.commit()
        job_id = job.id
    print(f"Running demo research job {job_id} "
          f"({create.industry} / {create.country}, {create.requested_leads} leads)…")
    result = asyncio.run(job_service.run_job(job_id, engine=engine))
    print(
        f"Job {result.job_id} {result.status}: "
        f"discovered={result.discovered} accepted={result.accepted} "
        f"duplicates={result.duplicates} invalid={result.invalid}"
    )
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    """Export a completed job's dataset using the shared export service."""
    from .db import session_scope
    from .services import export as export_service
    from .services import jobs as job_service

    engine = _engine_with_tables()
    with session_scope(engine) as session:
        job = job_service.get_job(session, args.job)
        if job is None:
            print(f"LeadForge: no research job {args.job!r}.")
            return 1
        if job.status != "completed":
            print(
                f"LeadForge: job {args.job!r} is '{job.status}'; "
                "only completed jobs can be exported."
            )
            return 1
        rows = export_service.fetch_export_rows(session, args.job)
        payload = (
            export_service.render_csv(rows)
            if args.format == "csv"
            else export_service.render_xlsx(job, rows)
        )
    with open(args.out, "wb") as fh:
        fh.write(payload)
    print(
        f"Exported {len(rows)} records from job {job.id} "
        f"to {args.out} ({args.format})."
    )
    return 0


def _cmd_worker(args: argparse.Namespace) -> int:
    # There is deliberately no background worker process: the API server
    # executes research jobs in-process via FastAPI BackgroundTasks
    # (DESIGN.md A2 — no Celery/Redis by design). This command exists so the
    # answer is discoverable instead of a "not implemented" stub.
    print(
        "LeadForge runs research jobs in-process: the API server executes the "
        "pipeline via FastAPI BackgroundTasks (DESIGN.md A2 — no Celery/Redis "
        "by design), so no separate worker process or container is required.\n"
        "Use `python -m leadforge serve` to run the API server, or "
        "`python -m leadforge run-demo` for a headless pipeline run."
    )
    return 0


def _skeleton_handler(args: argparse.Namespace) -> int:
    if args.command == "serve":
        import uvicorn

        from .main import app

        uvicorn.run(app, host=args.host, port=args.port)
        return 0
    if args.command == "seed-demo":
        return _cmd_seed_demo(args)
    if args.command == "reset-demo":
        return _cmd_reset_demo(args)
    if args.command == "run-demo":
        return _cmd_run_demo(args)
    if args.command == "export":
        return _cmd_export(args)
    if args.command == "worker":
        return _cmd_worker(args)
    print(
        f"LeadForge: '{args.command}' "
        "is not implemented in this phase."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="leadforge",
        description="LeadForge — automated B2B lead research & data enrichment.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("seed-demo", help="Load the 100-company synthetic dataset.")

    reset_p = sub.add_parser("reset-demo", help="Wipe demo data.")
    reset_p.add_argument("--reseed", action="store_true", help="Re-seed after wiping.")

    run_p = sub.add_parser("run-demo", help="Run the research pipeline headless.")
    run_p.add_argument("--industry", default="Jewelry Stores")
    run_p.add_argument("--country", default="United States")
    run_p.add_argument("--region", default="California")
    run_p.add_argument("--city", default=None)
    run_p.add_argument("--keywords", default=None)
    run_p.add_argument("--leads", type=int, default=100, choices=[10, 50, 100, 500])
    run_p.add_argument("--no-delay", action="store_true",
                       help="Disable the demo pipeline delay.")

    exp_p = sub.add_parser("export", help="Export a completed job's dataset.")
    exp_p.add_argument("--job", required=True, help="Research job ID.")
    exp_p.add_argument("--format", choices=["csv", "xlsx"], default="xlsx")
    exp_p.add_argument("--out", required=True, help="Output file path.")

    serve_p = sub.add_parser("serve", help="Run the API server.")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8000)

    # No separate worker process exists by design: research jobs run in-process
    # on the API server via FastAPI BackgroundTasks (DESIGN.md A2 — no
    # Celery/Redis). `python -m leadforge worker` explains this; the compose
    # stack therefore runs only db + backend + frontend.
    sub.add_parser(
        "worker",
        help="Explain why LeadForge needs no separate worker process.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return _skeleton_handler(args)
