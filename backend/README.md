# LeadForge backend

FastAPI service: research-job lifecycle, 8-stage data pipeline, export engine.

## Layout

```
leadforge/
├── __main__.py / cli.py   # `python -m leadforge ...` (seed-demo, run-demo, export, serve)
├── config.py              # environment-driven settings
├── logging_config.py      # structured logging
├── main.py                # FastAPI app factory
├── db.py                  # SQLite default / PostgreSQL via DATABASE_URL
├── models.py              # SQLAlchemy models
├── schemas.py             # Pydantic request/response models
├── api.py                 # routers
├── pipeline/              # JobRunner + pure stage modules
├── providers/             # ResearchProvider ABC + demo / HTTP implementations
├── ai/                    # AIProvider ABC + null / LLM implementations
├── services/              # jobs orchestration, export engine
└── seed.py                # synthetic dataset generator
```

## Develop

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m leadforge --help
```
