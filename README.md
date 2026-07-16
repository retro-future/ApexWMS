# ApexWMS

Multi-tenant (database-per-tenant) warehouse management system for phone stores.
IMEI-level device tracking, append-only stock & financial ledgers, credit/installment
sales. See [docs/prd.md](docs/prd.md) for the full PRD.

## Layout

```
backend/            # FastAPI + Dishka + SQLAlchemy (Clean Architecture)
  src/
    domain/         # entities, value objects (Money, IMEI), domain errors
    application/    # use cases, ports, DTOs
    infrastructure/ # SQLAlchemy, tenancy, JWT, PDF, Alembic
    presentation/   # FastAPI routers, schemas
    di/             # composition root: Dishka providers & container
    main.py         # ASGI entry point
  tests/
docs/prd.md         # product requirements
docker-compose.yml  # PostgreSQL 16
```

## Quickstart

```bash
docker compose up -d          # PostgreSQL
uv sync --all-packages --dev  # install
cd backend
uv run pytest                 # tests
uv run uvicorn main:app --reload   # http://localhost:8000/api/v1/health
```

Requires Python 3.14+, uv, Docker.
