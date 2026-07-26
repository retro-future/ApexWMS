# Plan: Author the ApexWMS MVP PRD (`docs/prd.md`)

## Context

`apexwms` is an empty repo (only `.idea/`). The goal is a **lightweight, multi-tenant warehouse management system for phone stores** — a niche where inventory is dominated by IMEI-identified devices, and where a store owner needs to know exactly which physical handset sits where, what it cost, and who bought it.

Before any code is written we need a PRD that fixes scope and the data model, because two of the decisions made in planning (**database-per-tenant** and **multi-currency money**) are effectively irreversible once code and data exist.

The **only deliverable of this task is the document `docs/prd.md`**. No application code, no scaffolding, no dependency installs. A follow-up task will implement from it.

### Decisions locked during planning

| Decision | Choice |
|---|---|
| Tenant isolation | **Database-per-tenant** + a shared control-plane DB |
| Stock model | **IMEI-serialized phones**, quantity-based accessories |
| v1 modules | Inbound receiving, outbound sales/issue, stock counts + write-offs |
| Out of v1 | Inter-location transfers (schema will anticipate them) |
| Locations | **Multi-location per tenant** from day one |
| Documents | Purchase Order, Sales Invoice, Return-to-Supplier (PDF) |
| Money | Multi-currency, integer minor units, rate captured per document |
| Scanning | Keyboard-wedge scanner → fast lookup-by-code API |
| Auth | Built-in JWT (access + refresh), argon2 hashing, tenant-scoped roles |
| Architecture | **Clean Architecture**, DI via Dishka. DDD introduced gradually, teaching as we go |
| Stack | Python 3.14, uv, FastAPI, SQLAlchemy 2 async + asyncpg, Alembic, Postgres |

## The PRD's content (what I'll write into `docs/prd.md`)

1. **Problem, goals, non-goals.** Explicitly names what v1 will *not* do (transfers, POS payments, repairs/service, e-commerce sync, accounting integration) so scope creep has something to push against.
2. **Personas & roles** — Owner, Manager, Storekeeper, Seller — and a permission matrix mapping each role to the operations below.
3. **Multi-tenancy architecture (database-per-tenant).** The section that carries the most engineering weight:
   - A **control-plane DB** holding `tenants`, `tenant_databases`, global `users` and tenant memberships. It is the only DB reachable without a tenant context.
   - A **tenant DB per tenant**, created at provisioning time, holding all business data. No `tenant_id` column anywhere inside it — isolation is physical.
   - A **connection registry**: an LRU cache of `AsyncEngine` per tenant, keyed by tenant id, with a bounded pool per tenant, resolved from the JWT's tenant claim by a Dishka request-scoped provider.
   - **Migrations fan out**: Alembic runs once against the control DB and once per tenant DB, driven by a CLI (`apexwms migrate --all-tenants`). This is the standing operational cost of this model and the PRD will say so plainly.
   - Provisioning flow: create tenant row → `CREATE DATABASE` → run migrations → seed default location/roles.
4. **Domain model.** Core entities and their relationships:
   - `Product` (a model/SKU: "iPhone 15 Pro 256GB Titanium") with `tracking_type` = `serial` | `quantity` — the single flag that forks the whole stock model.
   - `DeviceUnit` — one physical handset: IMEI (unique, validated by Luhn), optional second IMEI/serial, status (`in_stock`, `sold`, `returned`, `written_off`, `reserved`), current location, acquisition cost, source document.
   - `StockLevel` — `(product, location) → quantity` for accessories.
   - `Location`, `Supplier`, `Customer` (light).
   - **`StockMovement` as the append-only ledger** — every change to stock is a movement row (receipt, sale, write-off, count adjustment, return). Stock levels and unit statuses are *projections* of this ledger, never edited directly. This is the design decision that makes the system auditable and makes "how did this IMEI end up here?" answerable.
   - Documents: `PurchaseOrder`, `GoodsReceipt`, `SalesInvoice`, `SupplierReturn`, `StockCount`, `WriteOff` — each with `draft → confirmed → cancelled` lifecycle. **Stock only moves on confirm**; cancel writes compensating movements rather than deleting history.
   - Money: every amount is `(amount_minor: int, currency: char(3))`, with `exchange_rate` + `base_currency` captured on the document at confirm time so historical documents never shift when rates change.
5. **Functional requirements**, as numbered, testable statements grouped by module: Auth & tenancy, Catalog, Inbound (PO → receipt, IMEI scan-in, duplicate-IMEI rejection), Outbound (scan IMEI → sell, price, invoice), Returns to supplier, Stock counts & write-offs, Scanning & lookup, Documents/PDF, Reporting (stock on hand, movement history, IMEI trace, sales summary).
6. **Scanning UX contract** — the keyboard-wedge model, a `GET /scan/lookup?code=` endpoint that resolves an IMEI *or* an EAN in one call and tells the caller which it found, and scan-session semantics for receiving/counting (append codes to an open document, reject duplicates immediately, sub-200ms response so the operator can scan continuously).
7. **Clean Architecture layout + Dishka wiring.** Monorepo:
   ```
   apps/backend/src/apexwms/
     domain/        entities, value objects (IMEI, Money), domain errors — zero imports from outside
     application/   use-cases (interactors), ports (repository/uow/pdf/clock protocols), DTOs
     infrastructure/  SQLAlchemy models+repos, tenant engine registry, JWT, PDF renderer, Alembic
     presentation/  FastAPI routers, schemas, dependency wiring, exception handlers
   apps/frontend/   (Next.js — later)
   packages/        shared contracts if/when needed
   ```
   The dependency rule (inward only), a worked example tracing one use case (`ReceiveGoods`) across all four layers, and the Dishka provider scopes (`APP` for settings/engines, `REQUEST` for tenant session/UoW/current user). This section doubles as the teaching surface for DDD later — the PRD will flag *where* DDD concepts (aggregates, invariants) will be introduced as the project evolves.
8. **API surface** — endpoint table per module with method, path, auth, role.
9. **Non-functional requirements** — auth/authz, IMEI uniqueness within a tenant, audit trail, p95 latency targets (scan lookup < 200ms), pagination defaults, structured logging with tenant id, testing strategy (unit tests on pure domain; integration tests against a real Postgres in Docker with a throwaway tenant DB per test module).
10. **Delivery plan** — phased milestones from bootstrap → tenancy → catalog → inbound → outbound → counts → documents → reporting, each independently demoable.
11. **Open questions & risks** — carrying forward: the migration fan-out cost, tenant-DB connection-pool exhaustion at scale (mitigation: LRU-evict idle engines), PDF templating choice (WeasyPrint vs ReportLab), and Python 3.14 wheel availability for the dependency set (asyncpg 0.31+ ships cp314 wheels; psycopg3 is the fallback driver).

## Files

- **Create `docs/prd.md`** — the sole artifact.
- Nothing else is created or modified.

## Verification

The PRD is not executable, so verification is a review, not a test run:
1. Read `docs/prd.md` end to end and confirm every locked decision above appears and is justified.
2. Confirm the three "irreversible" choices (db-per-tenant, movement ledger, money-as-minor-units) are each stated with their cost, not just their benefit — if the tradeoff isn't written down, the doc is failing its job.
3. Confirm each functional requirement is phrased so it could become a test case (an actor, an action, an observable outcome).
4. Confirm the non-goals list is present and specific.

Sources consulted: [asyncpg releases](https://github.com/MagicStack/asyncpg/releases), [SQLAlchemy asyncio docs](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
