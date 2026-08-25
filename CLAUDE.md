# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

ApexWMS is a multi-tenant (database-per-tenant) warehouse management system for phone stores: IMEI-level device tracking, append-only stock & financial ledgers, credit/installment sales. It is also a CRM: customer records, credit/installment relationships, and customer-facing history are first-class alongside the inventory and ledger domain — not a bolted-on afterthought.

The project is a uv workspace with one member: `backend/` (FastAPI). Alongside it, `frontend/` is a Next.js app (App Router, Mantine, next-intl in en/ru/uz) that talks to the API only through its own BFF proxy at `/api/backend/*` — the browser never holds a token or learns the backend's address.

> **Full spec:** [docs/prd.md](docs/prd.md) (~1140 lines) — read the relevant section before implementing a feature; this file only orients you, it doesn't replace the PRD.
>
> **Finding code by feature?** [.claude/feature-map.md](.claude/feature-map.md) maps every feature area (Auth, Catalog, Ledgers, Purchase Orders/Goods Receipts, ...) to its command/query/model/service files.
>
> **Architecture deep-dive?** Start at [docs/architecture/overview.md](docs/architecture/overview.md), then the subsystem file you need: [clean-architecture.md](docs/architecture/clean-architecture.md), [multi-tenancy.md](docs/architecture/multi-tenancy.md), [tenant-resolution.md](docs/architecture/tenant-resolution.md), [value-objects.md](docs/architecture/value-objects.md), [ledgers.md](docs/architecture/ledgers.md), [documents.md](docs/architecture/documents.md), [milestones.md](docs/architecture/milestones.md).
>
> **Enforceable conventions?** [.claude/rules/backend/](.claude/rules/backend/) — path-scoped rules Claude Code auto-loads for matching files (provider hygiene, exception placement, handler helper placement, response-model placement).
>
> **Working in `backend/`?** Read [.claude/CLAUDE_PYTHON.md](.claude/CLAUDE_PYTHON.md) for the verification order (ruff, then ty, then pytest) and execution rules to follow before running tests.
>
> **Working in `frontend/`?** Read [.claude/CLAUDE_NEXTJS.md](.claude/CLAUDE_NEXTJS.md) for the verification order (eslint, then tsc, then vitest) and execution rules to follow before running tests.

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

Frontend commands run from `frontend/` (pnpm):

```bash
pnpm dev                                   # dev server → http://localhost:3000
pnpm typecheck && pnpm lint                # the two gates CI runs
pnpm test                                  # vitest (jsdom + Testing Library)
pnpm test src/lib/money.test.ts            # one file
```

`asyncio_mode = "auto"` is set in `backend/pyproject.toml`, so async test functions need no `@pytest.mark.asyncio` marker.

Settings load from environment variables prefixed `APEXWMS_` (see `backend/.env.example`), or from `backend/.env`.

## Architecture (first-pass facts)

- **Clean Architecture, one direction**: `presentation → application → domain`, with `infrastructure` implementing ports that `application` declares. `domain` has zero imports from outside itself. Full layer breakdown, the flat `src/` layout, and the Hatchling packaging quirk it requires: [clean-architecture.md](docs/architecture/clean-architecture.md).
- **CQRS**: one `Command`/`Query` + one `IRequestHandler` per file under `application/commands|queries/`, one response payload per file under `application/models/`. `.claude/rules/backend/handler-helpers.md` and `cqrs-response-models.md` enforce where helper logic and response classes live.
- **Multi-tenant, database-per-tenant**: MasterDB (tenant registry + platform identity) vs. TenantDB (one physical database per store, no `tenant_id` column anywhere). Identity is split (`User` in MasterDB vs. `Employee` in TenantDB, same id). Authorization is a flat `Permission` enum, not role hierarchy. Full detail, request lifecycle, and Dishka DI scopes: [multi-tenancy.md](docs/architecture/multi-tenancy.md).
- **`uv run ty check` is a real gate**, not advisory — it's the only thing that enforces the `NewType`-wrapped `MasterSession`/`TenantSession` distinction that keeps a repository from ever seeing the wrong database. Treat a red `ty check` as a broken build.
- **`domain/value_objects/`** (`Money`, `IMEI`, `CostPool`) are frozen dataclasses that validate themselves in `__post_init__` with no I/O — the pattern for any new value object. Detail: [value-objects.md](docs/architecture/value-objects.md).
- **Two append-only ledgers** (`stock_movements`, `financial_transactions`) are the source of truth; everything else (`stock_levels.quantity`, `device_units.status`, prices) is a projection written in the same transaction. `LedgerPoster` never commits — the calling handler owns the transaction. Detail, repository-base rules, verification CLI: [ledgers.md](docs/architecture/ledgers.md).
- **Documents** (`PurchaseOrder`, `GoodsReceipt`, `SalesInvoice` so far) share one lifecycle (`DRAFT → CONFIRMED → CANCELLED`) from a common `Document` base; each subclass states its own confirm invariants. The invoice's is deliberately thin, because re-resolving a price at confirm needs I/O and so belongs to `InvoicePoster`. Detail: [documents.md](docs/architecture/documents.md).
- **Frontend gates on permissions, never on role names**, mirroring §2.1's flat matrix (`src/lib/permissions.ts`, `useCan()`). Hiding a control is a courtesy — the server checks every request, and cost figures are *omitted from the payload* for Storekeeper/Seller (FR-1.7) rather than hidden in the UI.

Check [milestones.md](docs/architecture/milestones.md) for what's shipped and what's current.

## Code conventions

- Comments: write one only when the code genuinely needs it — a non-obvious business rule, the
  reason behind a decision, a workaround. Don't comment on obvious things (`# increment counter`
  above `i += 1`). A comment explains "why", never "what" the next line already says.
  Keep it minimal: one or two short sentences that state the essence, not a paragraph. If you
  can't say it in one or two sentences, the comment is doing too much — shorten it or move the
  explanation into a commit message/doc instead.
- **This applies to module and class docstrings too, not just inline `#` comments.** A module
  docstring is not the place for an essay: no restating what the module obviously does, no
  worked examples, no rhetorical build-up ("and that is the point", "the trap this table exists
  to close"), no walking through every caller and every edge case the code already shows by
  being read. State the one non-obvious fact (the business rule, the invariant, the reason this
  exists instead of the obvious alternative) in one to three sentences, then stop. If a fact
  needs more room than that to explain, it belongs in `docs/architecture/`, not in the source
  file — link to the doc instead of inlining the explanation.
- Before adding or editing a docstring/comment, read it back and cut anything that repeats the
  function/class name, describes control flow line by line, or exists only to sound thorough.
  A long docstring is a code smell the same way a long function is: if the "why" takes a
  paragraph, the design is probably not as settled as the comment claims.
