# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

ApexWMS is a multi-tenant (database-per-tenant) warehouse management system for phone stores: IMEI-level device tracking, append-only stock & financial ledgers, credit/installment sales. It is also a CRM: customer records, credit/installment relationships, and customer-facing history are first-class alongside the inventory and ledger domain — not a bolted-on afterthought. Full spec lives in `docs/prd.md` (~1140 lines) — read the relevant section before implementing a feature; this file only orients you, it doesn't replace the PRD.

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
- **Authorization is permissions, not roles** (`domain/permissions/`): one flat `Permission.<Module>.<Action>` `StrEnum` (`catalog.py`), with `AppRolePermissionProvider`/`TenantRolePermissionProvider` (`providers.py`) assigning subsets and `PermissionEvaluator` (`evaluator.py`) resolving the union. Values are wire format — add members, never rename one. Routers call `require(current, Permission.USERS_MANAGE)` / `require_any(...)` from `presentation/security.py`, which raise `AuthorizationError` (403) against `CurrentUser.permissions`. PRD §2.1 is not hierarchical, so never compare role rank. Note `PRICING_SET` (stating what the store asks for a model or a handset) and `PRICING_OVERRIDE` (negotiating one invoice line) are separate acts, not one permission.
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

### The two ledgers and their projections (PRD §4.3, §4.6 — M3)

`stock_movements` (goods) and `financial_transactions` (money) are append-only and are the source of truth for everything else. Four rules, none negotiable:

- **Nothing mutates stock except by writing a movement.** `stock_levels.quantity`, `device_units.status`/`location_id`, `device_units.asking_price` and `products.default_sale_price` are *projections* — updated in the same transaction as the row that causes them, never assigned on their own.
- **Both ledgers move together or not at all** (FR-10.1). Everything goes through `application/services/ledger.py`'s `LedgerPoster`, which takes a `Posting` (a stock effect paired with its `MoneyEffect`s) and **never commits** — the calling handler owns the transaction. Don't give it a `UnitOfWork`; a service that could commit could commit half of something.
- **Cancellation compensates, never deletes.** `LedgerPoster.reverse(document_type, document_id)` appends negated copies. There is deliberately no `REVERSAL` movement type — a reversal keeps its type and flips its sign, so summing deltas is always right and no report has to remember to exclude a category.
- **Every aggregate is per currency.** `FinancialTransaction.amount` is a signed `Money`; the direction of §4.6 *is* the sign, not a second column.

**A repository base is a convenience for the majority, not a classification of tables.** There are exactly two under `infrastructure/persistence/tenant/repositories/base.py`, and adding a third is the mistake this rule exists to prevent:

- `TenantCrudRepository` — an aggregate whose whole persisted state is one `ActivatableRow`: the identity records and the M2 catalog. It supplies `get`/`add`/`update` through the `_to_entity`/`_to_model`/`_apply` hooks, plus `_browse_page`, the paging shape every catalog list endpoint shares.
- `TenantRepository` — **everything else**, and it is deliberately an open bucket with no hooks and no `get`/`add`/`update`: the two ledgers, the two price logs, `device_units` (whose amounts are denominated by the *product*, so every read joins and the entity is rebuilt from a `Row`), the settings row, and the documents M4 brings.

An aggregate that does not fit `TenantCrudRepository` inherits `TenantRepository` and writes the two or three methods its port declares. **It does not get a base of its own.** Four bases grew here once, because each misfit was answered with a new sibling — `TenantJoinedRepository` even carried a docstring denying the `is-a` its own declaration asserted — and a hierarchy that must have a box for every table grows with every table. `tests/architecture/test_repository_bases.py` is that rule as a test. When something is genuinely missing, widen `SqlRepository`'s mechanics (`persistence/repository.py` — one session, `_insert`, and reads that are generic *per method*, which is what lets a joined read need no separate class) or write the method locally.

The append-only rule lives in **one** place: `AppendOnlyRepository` in `application/ports/repository.py`, which is what handlers depend on and therefore what actually prevents editing history. A ledger's SQL class has no `update` simply because nobody wrote one — not because a base class withheld it.

Row ↔ entity mapping stays **methods on the repository** (PRD §7.3): no module-level mapping functions, and no auto-mapper. `Money` needs a currency that lives on a neighbouring table, `IMEI` must pass Luhn, and `DeviceUnit.__post_init__` checks fields against each other — none of which field-name matching can express.

`domain/services/` holds the three pure rules the ledgers rest on: `pricing.py` (FR-2.14's resolution — a unit whose `condition ≠ NEW` **never** inherits the catalog price; this is the single most load-bearing line in M3), `valuation.py` (weighted-average `CostPool`; an issue takes a *proportional share* so a sold-out pool lands on exactly zero), and `projection.py` (what the ledger implies for a unit's state — used by both the poster and `verify-projections`, so a reported mismatch is always real).

`apexwms verify-projections` and `apexwms verify-financials` (`application/services/verification.py`) audit all of it, per tenant or fleet-wide. Both **report and never repair**: a sweep that quietly rewrote a projection would destroy the evidence of whatever wrote it wrong. Note `_INVENTORY_SIGN` there — §4.6's signs describe *cash*, so `PURCHASE` and `SUPPLIER_RETURN_CREDIT` flip when read as inventory value.

`DeviceUnit.cash_paid_minor`/`cash_paid_currency` is a bare pair and **never a `Money`**, on purpose (§4.5b): it is the som actually handed over for a trade-in booked in dollars, it enters no ledger, total, or report, and `tests/application/test_cash_paid_is_inert.py` exists to catch the future report that sums it.

### Delivery milestones (PRD §10)

The codebase is at **M3** (both ledgers, `device_units`, the two price logs, projections, valuation, the verification CLI, and the unit-pricing API) on top of M0's skeleton, M1's tenancy/auth, and M2's catalog. Milestones are strictly ordered and each is independently demoable — **M4 (inbound: PO → Goods Receipt, IMEI scan-in) is next**, then M5/M5b outbound + credit, M6 counts/write-offs, M7 documents, M8 reporting, M9 month-end close. Check `docs/prd.md` §10 before assuming a feature belongs in the current milestone — earlier milestones' plumbing is deliberately built ahead of the features that will use it. In particular **no document type exists yet**: nothing creates a `DeviceUnit` over HTTP, and `LedgerPoster` is currently driven only by tests. M4 is what gives it its first caller.


## Code conventions

- Single Responsibility Principle: each class/function should be responsible for one thing only.
  If a method handles validation, DB writes, and logging all at once — split it into separate
  functions/classes. Example: `TenantRepository` shouldn't decide which tenant is active —
  that's the responsibility of the tenant resolver in `di/providers/tenant_db.py`.
- Comments: only write comments where the code isn't self-explanatory (complex business logic,
  the reason behind a non-obvious decision, a workaround). Don't comment on obvious things
  (`# increment counter` above `i += 1`). A comment should explain "why", not "what".
