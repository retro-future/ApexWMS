# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

ApexWMS is a multi-tenant (database-per-tenant) warehouse management system for phone stores: IMEI-level device tracking, append-only stock & financial ledgers, credit/installment sales. Full spec lives in `docs/prd.md` (772 lines) — read the relevant section before implementing a feature; this file only orients you, it doesn't replace the PRD.

The project is a uv workspace with one member so far: `backend/` (FastAPI). A `frontend/` (Next.js) is planned but not started.

## Commands

All backend commands run from `backend/` unless noted.

```bash
docker compose up -d                       # PostgreSQL 16 (repo root)
uv sync --all-packages --dev               # install workspace deps (repo root)

uv run pytest                              # full test suite
uv run pytest tests/domain/test_money.py   # one file
uv run pytest tests/domain/test_money.py::TestArithmetic::test_add_same_currency  # one test
uv run pytest -k "imei"                    # by keyword

uv run ruff check src tests                # lint (also CI's lint step)
uv run ruff check --fix src tests          # lint with autofix

uv run uvicorn main:app --reload           # dev server → http://localhost:8000/api/v1/health
```

`asyncio_mode = "auto"` is set in `backend/pyproject.toml`, so async test functions need no `@pytest.mark.asyncio` marker.

Settings load from environment variables prefixed `APEXWMS_` (see `backend/.env.example`), or from `backend/.env`.

## Architecture

### Layout is flat under `src/`, not `src/apexwms/`

`backend/src/` has no wrapping package — `domain/`, `application/`, `infrastructure/`, `presentation/`, `di/`, `main.py`, and `version.py` sit directly under `src/` and import as top-level modules (`from infrastructure.config import Settings`, not `from apexwms.infrastructure.config import Settings`). This is deliberate; do not reintroduce an `apexwms/` wrapper or `apexwms.`-prefixed imports.

This works because `backend/pyproject.toml` declares each subpackage explicitly for Hatchling and strips the `src/` prefix:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/domain", "src/application", "src/infrastructure", "src/presentation", "src/di"]
include = ["src/main.py", "src/version.py"]
sources = ["src"]
```

Adding a new top-level package under `src/` (e.g. a future `worker/`) means adding it to `packages` here too, or it won't ship.

### Clean Architecture — the dependency rule (PRD §7.3)

```
presentation ──▶ application ──▶ domain
      │                │             ▲
      └───▶ infrastructure ──────────┘
                (implements ports defined in application)
```

- **`domain/`** — pure Python entities and value objects (`Money`, `IMEI`), domain errors. **Zero imports from outside `domain/`** — no SQLAlchemy, no FastAPI, no Pydantic. If a value object can't validate itself without a database, the design is wrong.
- **`application/`** — use cases (one class, one `execute()`, one business operation) and the **ports** they need, as `Protocol`s (`DeviceUnitRepository`, `UnitOfWork`, `Clock`, ...). Depends on `domain` only. Currently empty — this is where M1+ work lands.
- **`infrastructure/`** — implementations of those ports: SQLAlchemy repositories, the tenant engine registry, JWT, PDF rendering. `application` never imports from here — the port lives in `application`, the implementation lives here, satisfying it (dependency inversion).
- **`presentation/`** — FastAPI routers, request/response schemas. Thin: parse, authorize, call a use case, serialize. Does **not** contain DI wiring (see below).
- **`di/`** — the composition root. The only package allowed to import from every other layer. `di/providers.py` holds Dishka `Provider`s; `di/container.py`'s `create_container()` assembles them. Add new providers here as milestones add dependencies — don't scatter container-building code elsewhere.

**Why ports live in `application`, not `infrastructure`:** the use case declares what it needs; infrastructure satisfies it. This lets `application` be tested with in-memory fakes and no database at all — keep it that way.

### Multi-tenancy: database-per-tenant (PRD §3)

This is the most consequential and expensive-to-reverse decision in the codebase — do not casually add a `tenant_id` column or a cross-tenant query as a shortcut.

- **MasterDB** — one database: `tenants`, `tenant_databases`, global `users`, `memberships`. The only database reachable without a tenant context; login happens here.
- **TenantDB** — one physical database per tenant, holding all business data. **No `tenant_id` column exists inside a tenant database** — isolation is physical, not a `WHERE` filter. A missing filter cannot leak another tenant's data because that data isn't in the connected database.
- Request lifecycle: JWT validated → `tenant_id` claim extracted → `TenantEngineRegistry.get(tenant_id)` (LRU, opens engine on miss) → `AsyncSession` bound to that engine at Dishka `REQUEST` scope → use case executes, never knowing a tenant exists → session committed/rolled back and closed by the DI container.
- The tenant is resolved **once, at the edge**. Nothing in `domain` or `application` takes a tenant parameter — that's what makes isolation structural rather than disciplinary.
- `infrastructure/tenancy.py` implements `TenantEngineRegistry`: a bounded LRU cache of `AsyncEngine`s (`APEXWMS_MAX_LIVE_TENANT_ENGINES`, default 50; `APEXWMS_TENANT_POOL_SIZE`, default 5 connections each). Evicted engines are disposed. This ceiling is intentional — beyond it, the answer is PgBouncer or a shared-schema rethink, not a bigger cache.
- `TenantContext` (tenant_id + db_url) is currently supplied as Dishka request context directly; from M1 on it will instead be derived from the validated JWT plus a MasterDB lookup. When wiring that up, replace the `from_context` in `TenantDbProvider`, don't add a second path.

### Dishka DI scopes (PRD §7.5)

- **`APP`** scope: `Settings`, `MasterEngine`, `TenantEngineRegistry`. Later: JWT service, PDF renderer.
- **`REQUEST`** scope: `MasterSession`, `TenantEngine`/`TenantSession` (resolved per-request from `TenantContext`). Later: authenticated user, `UnitOfWork`, repositories, use cases.

`MasterEngine`, `MasterSession`, `TenantEngine`, `TenantSession` are `NewType`-wrapped `AsyncEngine`/`AsyncSession` (`infrastructure/database.py`) purely so the container can't hand a repository the wrong database — keep using these aliases (not bare `AsyncEngine`/`AsyncSession`) whenever wiring new providers that touch either database.

Settings enter the container via `from_context` + `context={Settings: ...}` in `create_container()`, not a provider that closes over a constructor argument — follow that pattern for other request-scoped context values.

### Money and IMEI value objects

Two domain value objects exist today and set the pattern for future ones (`domain/value_objects/`):

- **`Money`** (`money.py`) — integer minor-unit amount + `Currency`. UZS and USD have *different* exponents (UZS=0, "so'm" has no minor unit despite ISO 4217 nominally saying 2; USD=2, cents) — never assume a shared exponent at a call site. Construct from major units only via `Money.from_major(str | int | Decimal, currency)` — floats are rejected everywhere (`InvalidMoneyError`), because binary floats can't represent decimal money exactly and a lost fraction in an inventory system is indistinguishable from theft. Arithmetic/comparison across currencies raises `CurrencyMismatchError` — there is no implicit conversion.
- **`IMEI`** (`imei.py`) — 15 digits with a valid Luhn check digit, validated in `__post_init__` with no I/O. `IMEI.parse()` tolerates scanner input (spaces, hyphens). Uniqueness is a database-level concern, deliberately not handled here.

Both are frozen dataclasses that cannot exist in an invalid state — follow this shape for new value objects rather than validating downstream.

### Delivery milestones (PRD §10)

The codebase is at **M0** (bootstrap: skeleton, health endpoint, Money/IMEI). Milestones are strictly ordered and each is independently demoable — M1 is tenancy/auth/provisioning, M2 catalog, M3 the stock+financial ledgers, M4 inbound (receiving), M5/M5b outbound + credit/installments, M6 counts/write-offs, M7 documents, M8 reporting, M9 month-end close. Check `docs/prd.md` §10 before assuming a feature belongs in the current milestone — earlier milestones' plumbing (engine registry, DI scopes) is deliberately built ahead of the features that will use it, but business logic for later milestones (repositories, use cases, JWT, PDF) does not exist yet.


## Code conventions

- Single Responsibility Principle: each class/function should be responsible for one thing only.
  If a method handles validation, DB writes, and logging all at once — split it into separate
  functions/classes. Example: `TenantRepository` shouldn't decide which tenant is active —
  that's the responsibility of `TenantContext`/middleware.
- Comments: only write comments where the code isn't self-explanatory (complex business logic,
  the reason behind a non-obvious decision, a workaround). Don't comment on obvious things
  (`# increment counter` above `i += 1`). A comment should explain "why", not "what".
