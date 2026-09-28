"""LeadForge command-line interface.

Commands (Phase 2: argument parsing only — behavior lands in later phases):
    seed-demo   load the 100-company synthetic dataset
    reset-demo  wipe demo data
    run-demo    run the research pipeline headless
    export      export a completed job's dataset
    serve       run the API server
    worker      run the background job worker (Phase 6)
"""

from __future__ import annotations

import argparse


def _skeleton_handler(args: argparse.Namespace) -> int:
    print(
        f"LeadForge Phase 2 skeleton: '{args.command}' "
        "will be implemented in a later phase."
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

    sub.add_parser("worker", help="Run the background job worker (Phase 6).")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return _skeleton_handler(args)
