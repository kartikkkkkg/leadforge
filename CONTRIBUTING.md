# Contributing to LeadForge

Thanks for your interest in contributing. This is a portfolio project, but thoughtful
contributions are welcome.

## Ground rules

1. **Working > complex.** Prefer small, readable changes over clever abstractions.
2. **No real scraping of third-party sites.** New research providers must use legitimate
   APIs with proper credentials, or clearly-labeled synthetic data. No CAPTCHA bypassing,
   no anti-bot evasion, no login-wall scraping — see `docs/data-privacy.md`.
3. **Never present synthetic data as real.** Demo data must keep `is_synthetic=True` and
   use reserved domains (`example.com`) and fictional phone ranges (`555-01XX`).
4. **Honest language.** "Data completeness score", never "verified lead", unless the data
   was actually verified.
5. **Tests for pipeline logic.** Changes to `pipeline/stages/` need unit tests.

## Workflow

1. Fork the repo and create a feature branch (`feature/short-name`).
2. Follow the existing module layout — one concern per module (see `DESIGN.md`).
3. Run `make test` before opening a PR; add tests for new behavior.
4. Update `CHANGELOG.md` under `Unreleased`.
5. Open a PR describing the problem, the approach, and how you verified it.

## Local setup

```bash
cp .env.example .env
make install        # backend + frontend dependencies
scripts/dev.sh      # run locally (SQLite, no Docker needed)
make test           # backend test suite
```

## Code style

- Python: type hints on public functions, docstrings on modules.
- TypeScript: strict mode; no `any` without justification.
- Keep functions small and pure where possible — especially in `pipeline/stages/`.
