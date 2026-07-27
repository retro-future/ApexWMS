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

uv run ty check                            # type check src/ — see below, this is a real gate

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
- **`application/`** — CQRS: a `Command`/`Query` (one Pydantic message, one `IRequestHandler`, one business operation — `LoginCommand`/`LoginHandler`) and the **ports** a handler needs, as `Protocol`s (`UserRepository`, `UnitOfWork`, `Clock`, ...). `application/core/` holds the shared CQRS primitives (`IRequest`, `IRequestHandler`, `Command`, `Query`, `Result`/`ResultWithData`/`PagedResult`) — see `docs/prd.md` §7.3 for the full pattern and the DI-context-vs-CQRS-message DTO split. `application/commands/` and `application/queries/` hold one file per operation; `application/services/` holds collaborator services composed inside a handler but never invoked directly from a route (`ClaimsFactory`, `TokenIssuer`). Depends on `domain` for business rules, and on `pydantic` for its message layer — `domain` stays framework-free.
- **`infrastructure/`** — implementations of those ports: SQLAlchemy repositories, the tenant engine registry, JWT, PDF rendering. `application` never imports from here — the port lives in `application`, the implementation lives here, satisfying it (dependency inversion).
- **`presentation/`** — FastAPI routers, exception handlers. Thin: a route's request body **is** a `Command`/`Query` from `application` — no separate presentation-layer request/response schema. A router authorizes, calls the paired handler via `FromDishka[...]`, and returns what it returns (a `Result`/`ResultWithData[...]`, already a Pydantic model). Does **not** contain DI wiring (see below).
- **`di/`** — the composition root. The only package allowed to import from every other layer. `di/providers/` holds Dishka `Provider`s, one module per concern (`config.py`, `master_db.py`, `tenant_db.py`, `handlers.py`); `di/container.py`'s `create_container()` assembles them. As milestones add dependencies, add a new module under `di/providers/`, re-export it from its `__init__.py`, and register it in `create_container()` — don't scatter container-building code elsewhere.

**Why ports live in `application`, not `infrastructure`:** a handler declares what it needs; infrastructure satisfies it. This lets `application` be tested with in-memory fakes and no database at all — keep it that way.

### Multi-tenancy: database-per-tenant (PRD §3)

This is the most consequential and expensive-to-reverse decision in the codebase — do not casually add a `tenant_id` column or a cross-tenant query as a shortcut.

- **MasterDB** — the tenant registry (`tenants` with a unique `slug`, `tenant_databases`) **and platform identity**: `users`, `user_app_roles`, `user_tenant_access`, `invitations`, `refresh_tokens`. No operational data ever.
- **TenantDB** — one physical database per store: all business data plus `employees` (who works here, in what role). **No `tenant_id` column exists inside a tenant database** — isolation is physical, not a `WHERE` filter. A missing filter cannot leak another store's data because that data isn't in the connected database.
- **Identity is split, deliberately.** `User` (MasterDB, email unique platform-wide) is *who someone is*; `Employee` (TenantDB) is *what they may do at one store*. One person, one login, potentially several `Employee` rows with different roles.
- **`Employee.id` IS the master `User.id`** — not a fresh uuid, and no FK can enforce it across databases. It's what lets M3's `stock_movements.user_id` be a real tenant-local foreign key while login stays central. `employees.email`/`full_name` are denormalized copies so tenant-side reads never cross databases; MasterDB wins on conflict. `tests/architecture/test_database_split.py` guards all of this.
- **Two role namespaces** (`domain/roles.py`): `AppRole` (`app.superadmin`, `app.admin`, on `user_app_roles`) and `TenantRole` (`tenant.owner|manager|storekeeper|seller`, on `employees.role`). The prefixes are collision-avoidance — the string spaces cannot overlap. A SuperAdmin is just a `User` with `tenant_id = NULL` and an app role.
- **Authorization is permissions, not roles** (`domain/permissions.py`): one flat `Permission.<Module>.<Action>` catalog built by reflection, with `APP_ROLE_PERMISSIONS` / `TENANT_ROLE_PERMISSIONS` assigning subsets. Routers call `require(current, Permission.Users.Manage)` / `require_any(...)` from `presentation/security.py`, which raise `AuthorizationError` (403) against `CurrentUser.permissions`. PRD §2.1 is not hierarchical, so never compare role rank.
- **Tenants are created by SuperAdmin CLI only** (`apexwms create-tenant`, `create-superadmin`), never self-service — there is no sign-up endpoint. Provisioning writes the master `users` row, then seeds the matching `employees` row with a temporary password and `must_change_password`.
- **Login names no tenant.** Credentials authenticate against MasterDB; the `tenant` claim is stamped server-side by `ClaimsFactory` (`application/services/claims.py`) from `users.tenant_id`, or from `X-Tenant` when the user has access. A platform operator's token carries **no** tenant claim at all.
- Request lifecycle: tenant resolved from **`X-Tenant` header > JWT `tenant` claim** → looked up in MasterDB, must be `active` → `TenantEngineRegistry.get(...)` (LRU, opens engine on miss) → `AsyncSession` at Dishka `REQUEST` scope → the handler executes, never knowing a tenant exists → session committed/closed by the container.
- **The header wins over the claim** — that's what lets a multi-store user switch without re-authenticating — but it is *authorized*, not trusted: no `user_tenant_access` grant means `403` before any session opens. All in `di/providers/tenant_db.py`; no middleware, and nothing parses the request body.
- The tenant is resolved **once, at the edge**. Nothing in `domain` or `application` takes a tenant parameter. Two narrow exceptions: `ResolvedTenantId` is injected where a collaborator must stamp it (`InviteUser`), and `TenantScope` (`infrastructure/tenant_scope.py`) opens a store's database when the edge couldn't have known it — login, which learns the tenant only after reading the master user row.
- `infrastructure/tenancy.py` implements `TenantEngineRegistry`: a bounded LRU cache of `AsyncEngine`s (`APEXWMS_MAX_LIVE_TENANT_ENGINES`, default 50; `APEXWMS_TENANT_POOL_SIZE`, default 5 connections each). Evicted engines are disposed. This ceiling is intentional — beyond it, the answer is PgBouncer or a shared-schema rethink, not a bigger cache.
- `TenantContext` (tenant_id + db_url) is built in `TenantDbProvider.tenant` from the request plus a MasterDB lookup. If a third way to name a tenant is ever needed, extend that one resolver — don't add a second path.

### Dishka DI scopes (PRD §7.5)

- **`APP`** scope: `Settings`, `MasterEngine`, `TenantEngineRegistry`, `JwtTokenService`, `PasswordHasher`, `TenantProvisioner`. Later: PDF renderer.
- **`REQUEST`** scope: `MasterSession`, `TenantContext`/`TenantEngine`/`TenantSession`, `ResolvedTenantId`, `RequestedTenant`, `CurrentUser`, `TenantScope`, repositories, units of work, command/query handlers.

Identity repositories take `MasterSession`; only `EmployeeRepository` and `TenantSettingsRepository` take `TenantSession`. Getting that wrong is the single easiest way to reintroduce the bug this architecture exists to prevent.

`MasterEngine`, `MasterSession`, `TenantEngine`, `TenantSession` are `NewType`-wrapped `AsyncEngine`/`AsyncSession` (`infrastructure/types.py`) purely so the container can't hand a repository the wrong database — keep using these aliases (not bare `AsyncEngine`/`AsyncSession`) whenever wiring new providers that touch either database.

**A `NewType` is an identity function at runtime, so `uv run ty check` is the only thing that enforces any of this** — ruff does not type-check, and no test can catch a master session handed to a tenant repository. Treat a red `ty check` as a broken build. Code that hand-wires repositories outside the container (`infrastructure/cli.py`) must wrap its session explicitly: `MasterSession(session)`, never a bare `AsyncSession`. `tests/` is currently outside the checked set — the domain suites assert that invalid calls are rejected, and those lines carry mypy-style `# type: ignore[...]` codes ty doesn't recognise.

Settings enter the container via `from_context` + `context={Settings: ...}` in `create_container()`, not a provider that closes over a constructor argument — follow that pattern for other request-scoped context values.

### Money and IMEI value objects

Two domain value objects exist today and set the pattern for future ones (`domain/value_objects/`):

- **`Money`** (`money.py`) — integer minor-unit amount + `Currency`. UZS and USD have *different* exponents (UZS=0, "so'm" has no minor unit despite ISO 4217 nominally saying 2; USD=2, cents) — never assume a shared exponent at a call site. Construct from major units only via `Money.from_major(str | int | Decimal, currency)` — floats are rejected everywhere (`InvalidMoneyError`), because binary floats can't represent decimal money exactly and a lost fraction in an inventory system is indistinguishable from theft. Arithmetic/comparison across currencies raises `CurrencyMismatchError` — there is no implicit conversion.
- **`IMEI`** (`imei.py`) — 15 digits with a valid Luhn check digit, validated in `__post_init__` with no I/O. `IMEI.parse()` tolerates scanner input (spaces, hyphens). Uniqueness is a database-level concern, deliberately not handled here.

Both are frozen dataclasses that cannot exist in an invalid state — follow this shape for new value objects rather than validating downstream.

### Delivery milestones (PRD §10)

The codebase is at **M1** (tenancy, auth, provisioning — on top of M0's skeleton, health endpoint, Money/IMEI). Milestones are strictly ordered and each is independently demoable — **M2 (catalog) is next**, then M3 the stock+financial ledgers, M4 inbound (receiving), M5/M5b outbound + credit/installments, M6 counts/write-offs, M7 documents, M8 reporting, M9 month-end close. Check `docs/prd.md` §10 before assuming a feature belongs in the current milestone — earlier milestones' plumbing (engine registry, DI scopes) is deliberately built ahead of the features that will use it, but business logic for later milestones (catalog and ledger repositories, PDF) does not exist yet.


## Code conventions

- Single Responsibility Principle: each class/function should be responsible for one thing only.
  If a method handles validation, DB writes, and logging all at once — split it into separate
  functions/classes. Example: `TenantRepository` shouldn't decide which tenant is active —
  that's the responsibility of the tenant resolver in `di/providers/tenant_db.py`.
- Comments: only write comments where the code isn't self-explanatory (complex business logic,
  the reason behind a non-obvious decision, a workaround). Don't comment on obvious things
  (`# increment counter` above `i += 1`). A comment should explain "why", not "what".
