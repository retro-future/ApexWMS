# ApexWMS — Product Requirements Document

**Version:** 1.0 (MVP)
**Status:** Draft for implementation
**Last updated:** 2026-07-14

---

## 1. Problem, Goals, Non-Goals

### 1.1 Problem

A phone store's inventory is not a pile of interchangeable units. Every handset is a distinct object with its own IMEI, its own acquisition cost, its own warranty clock, and its own answer to "where is it right now?". Store owners today track this in spreadsheets or in their heads, which fails in three specific ways:

- **Nobody can trace a device.** A customer returns a phone claiming they bought it here. Was it sold here? On what invoice? For how much? At what cost? A spreadsheet cannot answer this reliably.
- **Stock and reality diverge silently.** Devices go missing, get "borrowed" for demos, or get written off informally. Without an audit trail, the discrepancy is only discovered at year-end, with no way to reconstruct when it happened.
- **Money is fuzzy.** Phones trade in USD and accessories in som, and the two are tracked in the same notebook. Costs, prices, and margins get mixed together across currencies until nobody can say what any part of the business actually earned.

### 1.2 Goals (MVP v1)

1. **Know every device.** Each physical handset is a first-class record, identified by IMEI, with a complete, immutable history from receipt to sale.
2. **Make stock changes auditable.** Every increase or decrease in stock is an entry in an append-only ledger. No exceptions, no silent edits.
3. **Work at scanner speed.** A storekeeper receiving 50 phones scans 50 barcodes without waiting for the UI. A seller scans one IMEI and sells it.
4. **Produce the paperwork.** Purchase Orders to suppliers, Sales Invoices to customers, Return-to-Supplier notes — as PDFs, with the tenant's own details on them.
5. **Isolate tenants completely.** One store's data is physically unreachable from another's.
6. **Record the money, not just the goods.** Every stock event that has a financial consequence — a purchase, a sale, a write-off, a supplier credit — writes a matching entry to a financial ledger. At month's end the owner gets a report on the state of the warehouse and store: what was bought, what was sold, what it cost, what's left on the shelves and what it's worth, and the margin earned.
7. **Sell on credit, and know who owes the store money.** Two credit paths exist. A **credit-company sale** (Uzum Nasiya and similar) is settled instantly — the company pays the store in full and collects from the customer itself; the system merely labels the sale with the company for reference. A **store-credit sale** opens a simple open balance **in soums**: the seller writes the total som debt, and the system tracks how much the customer has paid and how much is left. No schedules, no interest, no overdue engine — a shopkeeper's notebook, made auditable.

### 1.3 Non-Goals (explicitly NOT in v1)

Naming these is the point of this section. If a request falls in this list, it is a v2 conversation, not a scope adjustment.

| Not in v1 | Why / when |
|---|---|
| **Inter-location transfers** | The schema will model `Location` and record it on every movement, so transfers are additive in v2. Deliberately deferred to keep v1 shippable. |
| **Payment *processing*** | The system **records** payments received (cash handed over, a transfer that landed) against a store-credit balance — that's core to debt tracking (§4.7). It does **not** *process* payments: no card rails, no payment gateway, no cash drawer, no till reconciliation. "Customer paid 2,000,000 today" is a recorded fact, not a transaction the system executes. |
| **Lending mechanics** | Store credit is an **open balance only** (§4.7): no schedules, no due dates, no interest/APR, no late fees, no credit scoring, no overdue engine, no repossession workflow. The credit company's own repayment plan is its business, not this system's. |
| **Automated used-price valuation** | A used handset's price is **entered by a human, per handset** (§4.5b). The system does not derive it from a condition grade, a percentage of the new price, a depreciation curve, or a market feed. A computed price for used goods is a false precision the owner would override on every unit — and a price that is always overridden is worse than no price, because it looks calculated. |
| **Repairs / service tickets** | A separate domain with its own workflow. Out of scope. |
| **E-commerce / marketplace sync** | No Shopify, no marketplace feeds. |
| **External accounting integration** | The system keeps its *own* internal financial ledger (§4.6) and produces a month-end report (§5.10). What it does **not** do in v1: export to QuickBooks/1C, file taxes, run a chart of accounts, or do full double-entry bookkeeping. It is an inventory-and-margin ledger, not a general ledger. |
| **Purchase-order approval workflows** | A PO is created and sent. No multi-step approval chain. |
| **Customer CRM** | `Customer` exists as a name + phone number on an invoice. Nothing more. |
| **Mobile native app** | Web only. The scanner is a keyboard-wedge device attached to a browser. |

### 1.4 Success criteria

MVP is done when a store owner can, on real hardware: create a PO, receive the goods by scanning IMEIs, sell a device by scanning its IMEI, print the invoice, run a stock count that surfaces a discrepancy, write off the missing unit, and pull up the full movement history of any IMEI — all without touching a spreadsheet.

---

## 2. Personas & Roles

| Role | Who they are | What they need |
|---|---|---|
| **SuperAdmin / Admin** | Us — the people who operate ApexWMS. Not customers, and not staff at any store. | Create tenants, suspend them, see the fleet. They hold an **`AppRole`** (`app.superadmin`, `app.admin`), which is a different namespace from the store roles below and cannot appear in a store token (§3.5). There is no separate SuperAdmin entity — it is a `User` with that role assigned. |
| **Owner** | Runs the business, may own several stores. | Everything, plus reporting, plus user management and settings. |
| **Manager** | Runs one or more locations day to day. | All stock operations, documents, reporting. Cannot manage billing or delete the tenant. |
| **Storekeeper** | Physically handles goods. | Receiving, stock counts, write-offs. Should not see margins or set prices. |
| **Seller** | Sells to customers on the floor. | Look up stock, sell, generate invoice. Should not see acquisition cost. |

### 2.1 Permission matrix

*Roles **within** a store (`TenantRole`: `tenant.owner`, `tenant.manager`, `tenant.storekeeper`, `tenant.seller`). App-level roles are absent on purpose — they live in a separate namespace (see §3.5).*

This table is not decoration: it is the source for the **permission catalog** in `domain/permissions.py`, where each row becomes a `Permission.<Module>.<Action>` string and each column becomes a subset of that one catalog. Authorization compares permissions, never role names — the matrix is not hierarchical, so there is no rank to compare.

| Operation | Owner | Manager | Storekeeper | Seller |
|---|:--:|:--:|:--:|:--:|
| Manage users & roles | ✅ | ❌ | ❌ | ❌ |
| Manage tenant settings (timezone, letterhead) | ✅ | ❌ | ❌ | ❌ |
| Manage locations | ✅ | ✅ | ❌ | ❌ |
| Manage catalog (products, suppliers) | ✅ | ✅ | ❌ | ❌ |
| Create / send Purchase Order | ✅ | ✅ | ❌ | ❌ |
| Receive goods (scan-in) | ✅ | ✅ | ✅ | ❌ |
| **See acquisition cost / margin** | ✅ | ✅ | ❌ | ❌ |
| Sell / issue stock | ✅ | ✅ | ❌ | ✅ |
| Set / override sale price | ✅ | ✅ | ❌ | ❌ |
| Price a unit at intake / reprice it in stock (§4.5b) | ✅ | ✅ | ❌ | ❌ |
| Change a product's catalog price (§4.5b) | ✅ | ✅ | ❌ | ❌ |
| Sell via credit company / store credit | ✅ | ✅ | ❌ | ✅ |
| Manage credit companies (reference list) | ✅ | ❌ | ❌ | ❌ |
| Record a customer payment | ✅ | ✅ | ❌ | ✅ |
| Reverse a payment | ✅ | ✅ | ❌ | ❌ |
| View customer balances & debtor list | ✅ | ✅ | ❌ | ✅¹ |
| Return to supplier | ✅ | ✅ | ❌ | ❌ |
| Run stock count | ✅ | ✅ | ✅ | ❌ |
| Confirm count adjustments | ✅ | ✅ | ❌ | ❌ |
| Write off stock | ✅ | ✅ | ❌ | ❌ |
| Cancel a confirmed document | ✅ | ✅ | ❌ | ❌ |
| Look up stock / IMEI | ✅ | ✅ | ✅ | ✅ |
| Operational reporting | ✅ | ✅ | ❌ | ❌ |
| **Financial ledger & month-end report** | ✅ | ✅ | ❌ | ❌ |
| Set a product's currency (at creation) | ✅ | ✅ | ❌ | ❌ |

> **Note on cost visibility:** hiding acquisition cost from Storekeeper and Seller is a *response-shaping* requirement, not just a UI concern. The API must omit cost fields for those roles — not send them and rely on the frontend to hide them.
>
> ¹ A Seller sees the balance of the customer they are serving (needed to take a payment); the *full debtor list across all customers* — a business-health figure — is Owner/Manager only.

---

## 3. Multi-Tenancy Architecture — Database-per-Tenant

This is the single most consequential decision in this document, and the most expensive one to reverse. It is written down here with its costs, not only its benefits.

### 3.1 The model

- **One master database (MasterDB).** The tenant registry — `tenants` (id, name, **`slug`**, status), `tenant_databases` — **and platform identity**: `users`, `user_app_roles`, `user_tenant_access`, `invitations`, `refresh_tokens`. It holds no operational data of any kind.
- **One database per tenant.** Created at provisioning. Holds *all* business data — products, device units, movements, documents, locations, suppliers, customers — **and `employees`**, the rows saying who works here and in what role. **There is no `tenant_id` column anywhere inside a tenant database** — isolation is physical, not a `WHERE` clause. A missing filter cannot leak another tenant's data because that data is not in the database you are connected to.

**Identity is split across the two databases, on purpose.** "Who is this person" (`User`, MasterDB, one row ever, email unique platform-wide) is a different question from "what may they do at store X" (`Employee` + `TenantRole`, that store's database, one row per store they work at). A person managing two shops has **one login** and two `Employee` rows — possibly with different roles, which is exactly what the model is for.

Three consequences worth stating outright:

- **`Employee.id` *is* the master `User.id`.** Not a foreign key — the databases are different, so no constraint can express it — but a contract, asserted by an architecture test. It is what lets M3's `stock_movements.user_id` and `documents.created_by` be real, enforceable foreign keys into a tenant-local table while the login identity stays central. Break the equality and every ledger join breaks silently.
- **`employees.email`/`full_name` are copied** from the master user. Deliberate denormalization: listing a store's staff, and later joining the ledger to a name, must never require a cross-database read. MasterDB is the source of truth if they disagree.
- **`refresh_tokens` and `invitations` are master-side.** A refresh token proves *who* you are, which is not a per-store fact; an invitation must be acceptable by someone who has no tenant context yet, which is only possible if it is stored centrally.

### 3.2 What this costs us

| Cost | Mitigation |
|---|---|
| **Migrations fan out.** Every schema change must run against the master DB *and* every tenant DB. With 200 tenants, that's 201 migration runs, and a failure halfway leaves the fleet on mixed schema versions. | A migration CLI (`apexwms migrate --all-tenants`) that runs tenant migrations idempotently, records per-tenant schema version, is resumable, and reports the fleet's version spread. Treat a partial migration as an expected state, not an emergency. |
| **Connection pools multiply.** Each tenant needs its own `AsyncEngine` and pool. 200 tenants × 5 connections = 1000 connections; Postgres will refuse. | A bounded **LRU engine registry**: at most *N* live engines (default 50), each with a small pool (default 5). Idle engines are disposed on eviction. Scale beyond that requires PgBouncer or a shift to shared-schema — a known ceiling, documented here so it isn't a surprise. |
| **Cross-tenant queries are hard.** "Total devices sold across all tenants" requires querying N databases. | Accepted. v1 has no cross-tenant reporting requirement. If one appears, it needs an analytics pipeline, not a JOIN. |
| **Provisioning is a real operation** that can fail halfway (DB created, migrations failed). | Provisioning is a state machine on the `tenants` row: `pending → provisioning → active | failed`. A tenant is not usable until `active`. Failed provisioning is retryable and idempotent. |

**Why we accept these costs:** physical isolation of retail inventory and customer data, per-tenant backup/restore, and the ability to hand a tenant their own database if they leave. For a system whose entire value is "the record is trustworthy," a bug class that can cross-contaminate tenants is worth engineering away structurally.

### 3.3 Request lifecycle

**Login names no tenant.** Email is unique platform-wide, so credentials alone identify the person; the store their token speaks for is stamped in server-side from `users.tenant_id`. The client never chooses it.

```
Login (email + password)  →  authenticate against MasterDB
        → claims factory: tenant = X-Tenant (if any) else user.tenant_id
        → no tenant either way?  → platform operator: token carries NO tenant claim
        → otherwise: read that store's `employees` row for the role
        → JWT issued with the tenant and role baked in

Every tenant-scoped request:
        → resolve the tenant:  X-Tenant header  >  JWT `tenant` claim
        → look it up in MasterDB (status must be active)
        → EngineRegistry.get(tenant_id)   [LRU cache; opens engine on miss]
        → AsyncSession bound to that engine   [Dishka REQUEST scope]
        → Use case executes; it never knows a tenant exists
        → Session committed/rolled back and closed by the DI container
```

`X-Tenant` accepts a slug (`acme`) or a UUID.

**The header wins over the claim**, and that asymmetry is the point: it lets someone with `user_tenant_access` at several stores switch between them **without re-authenticating**. The token proves *who* they are; the header decides *whose data* they are looking at.

A header naming a store the caller has no grant for is a **403, checked before any session opens** — not trusted and left to return an empty result. (This is a deliberate hardening over the reference implementation this design is ported from, which trusts the header and relies on the tenant database coming back empty.)

The tenant is resolved **once**, at the edge. Nothing in the `domain` or `application` layer takes a tenant parameter. This is what makes the isolation structural rather than disciplinary. The one exception is `TenantScope`, a narrow port for reaching a store the edge could not have resolved — login, which learns the tenant only after reading the master user row.

### 3.4 Provisioning flow

A tenant is created by a **SuperAdmin**, via `apexwms create-tenant --name --slug --owner-email --owner-name`. There is no public sign-up.

1. Insert the `tenants` row (`status = pending`, with its unique slug) **and the Owner's master `users` row** — with a generated temporary password, `must_change_password = true`, and `tenant_id` pointing at the new store. Commit.
2. `CREATE DATABASE apexwms_tenant_<uuid>` (autocommit, outside a transaction — Postgres requires this).
3. Record connection info in `tenant_databases`.
4. Run Alembic to head against the new DB.
5. Seed: a default `Location` ("Main Store"), the tenant's timezone, and **the Owner's `employees` row — carrying the user id minted in step 1**, so the two match.
6. Mark `status = active`.

Steps 2–5 are idempotent and retryable; step 1 commits first so a crash during provisioning leaves a `pending`/`failed` tenant that can simply be provisioned again. The temporary password is returned once, to the operator running the command, and is never stored in plaintext; the Owner must replace it via `POST /auth/change-password`, which also revokes every session opened with it. Delivering it by welcome email is v2 (§3.5) — today the CLI prints it and the operator hands it over.

Platform operators are seeded the same way, minus a store: `apexwms create-superadmin` writes a `users` row with `tenant_id = NULL` and an `app.superadmin` row in `user_app_roles`.

Adding staff to an *existing* store goes through invitations instead (FR-1.5), where the invitee chooses their own password — the safer path, and the one to prefer wherever a temporary password is avoidable.

`suspended` is a fifth tenant status, outside the provisioning state machine: an operator decision (unpaid, abuse) applied to an already-active tenant and reversible with `apexwms activate-tenant`. The database and its data are untouched; only access stops.

### 3.5 The two role systems, and what is deliberately deferred

**Two role namespaces, kept apart by their prefixes.** `AppRole` (`app.superadmin`, `app.admin`) lives in MasterDB on `user_app_roles`; `TenantRole` (`tenant.owner`, `tenant.manager`, `tenant.storekeeper`, `tenant.seller`) lives in each store's database on `employees.role`. The prefixes are the collision-avoidance mechanism: the two string spaces cannot overlap, so a role or permission check can never accidentally match across the systems. A guard fails at import time if a member is ever added without its prefix.

Both draw from **one flat permission catalog** (`domain/permissions.py`). `Permission.<Module>.<Action>` constants are grouped into nested "module" classes and the full list is derived by reflection, so the catalog cannot drift from a second hand-maintained list. Two independent maps assign subsets: `APP_ROLE_PERMISSIONS` (superadmin → everything; admin → everything except managing other admins) and `TENANT_ROLE_PERMISSIONS` (the four §2.1 columns). A tenant role can only ever reference the shared catalog, never an app-role name, and vice versa — which is what keeps future per-store custom roles from colliding with platform ones. `register_tenant_role()` is the hook for that, unused while §2.1 fixes the four.

**This model was settled during M1, after one wrong turn.** An earlier M1 draft collapsed identity into the tenant databases — one `users` table per store carrying credentials *and* role, with no master identity at all. The stated reason was that M3's `stock_movements.user_id` needs a real foreign key, which a cross-database UUID cannot provide.

That reasoning was wrong, and the fix is the `Employee.id == User.id` mirror described in §3.1: the tenant database holds a row keyed by the master user id, so the ledger's foreign keys are tenant-local *and* enforceable while the login identity stays central. Both properties, no trade. The collapsed model also cost multi-tenant users, gave SuperAdmin no data model at all, and forced every login to name a store before it could authenticate.

**What this buys back.** FR-1.3 returns: one person, one login, several stores, switched with `X-Tenant` and authorized by `user_tenant_access`. Login gets simpler, not harder — no store handle in the login form.

**Deliberately NOT built yet** — the groundwork is documented here so it isn't reinvented, but building it now would be premature:

| Deferred to v2 | Why not now |
|---|---|
| **SuperAdmin admin portal** — a UI to create/edit tenants and change subscription plans. | The CLI covers every operation it would. A portal is a second frontend before the first one exists. |
| **`/admin/*` HTTP API.** | Platform operators already exist as real accounts and can authenticate (their token simply carries no tenant claim), so no new auth realm is needed when the portal lands — only routes. Until then the CLI is the whole surface. |
| **Billing / subscription metadata** — `Subscription`, `SubscriptionPlan`, `PlanFeature`, and the subscription check that would run right after tenant resolution. | Nothing reads it yet. It belongs in MasterDB when it arrives — an application-level concern, not a store's business data. |
| **Per-store custom roles** — `TenantRole` as DB rows with free-form claims rather than a fixed enum. | §2.1 fixes the four roles, and the reference implementation this is ported from does not exercise dynamic roles either. `register_tenant_role()` is the seam; the schema change is additive when it is needed. |
| **API keys, feature flags, impersonation** — the remaining master-side tables in the reference. | No ApexWMS feature reads any of them. |
| **Welcome email** carrying the temporary password. | No transactional email infrastructure exists in the project. The flow (temp password + forced change) is built; only delivery is manual. |
| **Server-side hard gate on `must_change_password`** — blocking every other endpoint until the password is changed. | The MVP surfaces the flag on login and `/auth/me` and provides the change endpoint. The exposure is a user who already knows their own temporary password. Worth tightening, not worth blocking M2 on. |

---

## 4. Domain Model

### 4.1 The forking decision: `tracking_type`

```
Product.tracking_type ∈ { SERIAL, QUANTITY }
```

- `SERIAL` — a phone. Every physical unit is its own row in `device_units`, with an IMEI. You do not have "3 iPhone 15 Pro"; you have three specific handsets with three specific IMEIs, each with its own cost and history.
- `QUANTITY` — a case, a charger, a screen protector. Tracked as `(product, location) → integer quantity`. Nobody wants to serialize a box of 200 screen protectors.

A single flag on `Product` decides which path every stock operation takes. Both paths write to the same ledger.

### 4.2 Entities

**`Product`** — a catalog entry, not a physical thing. *"iPhone 15 Pro 256GB Titanium"*. Fields: `sku`, `name`, `brand`, `model`, `tracking_type`, `barcode` (EAN/UPC, for quantity items), `default_sale_price` (Money, **nullable**, **and changeable — every change is logged**, see §4.5b), `is_active`.

**`DeviceUnit`** — one physical handset. The heart of the system.
- `imei` — unique within the tenant, **validated with the Luhn check digit** at the boundary. A typo'd IMEI is worse than no IMEI.
- `imei2`, `serial_number` — optional (dual-SIM devices, non-phone serialized goods).
- `product_id` — what model it is.
- `status` ∈ `IN_STOCK | RESERVED | SOLD | RETURNED_TO_SUPPLIER | WRITTEN_OFF | RECEIPT_CANCELLED`. The last is where a handset lands when the Goods Receipt that brought it in is cancelled (§4.4) — it was neither destroyed nor sent back under a supplier return, and booking it as `WRITTEN_OFF` would make the write-off report count a loss the store never took.
- `location_id` — where it physically is (null once sold).
- `acquisition_cost` (Money) — what *this specific unit* cost. Two identical iPhones bought a month apart have different costs; average costing would destroy that.
- `asking_price` (Money, **nullable**) — what *this specific unit* is offered at. The mirror image of `acquisition_cost`, and for the same reason: two used handsets of the same model are not worth the same money (§4.5b). `NULL` means "no unit price — use the catalog price, if the resolution rule allows it".
- `condition` ∈ `NEW | REFURBISHED | USED`. Not decoration: it is what decides whether this unit may inherit the catalog's price (§4.5b).
- Provenance: the receipt document that brought it in.

- `cash_paid_minor` + `cash_paid_currency` (both **nullable**) — what physically changed hands, when that is not the same as `acquisition_cost`. A trade-in bought from a walk-in for som against a USD catalog row is the case this exists for (§4.5b). **Informational only: it enters no ledger, no total, and no report figure** — see the trade-in subsection of §4.5b before touching it.

Both `acquisition_cost` and `asking_price` are stored as a bare `BIGINT` minor amount and **inherit the product's currency** — there is no per-unit currency column, because a unit cannot be denominated differently from the catalog row it belongs to (§4.5 rule 3).

**`StockLevel`** — `(product_id, location_id) → quantity`, for `QUANTITY` products only. **A projection, never a source of truth** (see §4.3).

**`Location`** — a store, a stockroom, a warehouse. Present from day one even though transfers are v2, because retrofitting a location column onto a populated movements table is a migration nobody wants.

**`Supplier`** — name, contact. *(No currency field — currency belongs to products, §4.5, not to suppliers or documents.)* A Goods Receipt's supplier is **nullable**: used stock arrives from walk-in customers, not suppliers, and that receipt names no supplier at all (`acquisition_source`, §4.4).

**`CreditCompany`** — a third-party financing partner (§4.7): name, contact, active flag. A label on financed sales, nothing more — the company pays in full at sale time, so no money is tracked against it.

**`Customer`** — name, phone. Deliberately anemic; this is not a CRM.

### 4.3 `StockMovement` — the append-only ledger

**This is the backbone of the system.**

Every single change to stock — every receipt, sale, write-off, count adjustment, supplier return — is an **immutable row** in `stock_movements`:

```
id, occurred_at, movement_type, product_id, device_unit_id (nullable),
location_id, quantity_delta (+/-), document_type, document_id, user_id, note
```

**Stock levels and device statuses are projections of this ledger.** They are derived from it and updated in the same transaction as the movement that causes them — never edited independently.

The rules, which are non-negotiable:

1. **Nothing mutates stock except by writing a movement.** There is no code path that sets `StockLevel.quantity = 5`. There is only "write a movement of `+2`, and the projection follows."
2. **Movements are never deleted or updated.** Cancelling a confirmed document does not remove its movements — it writes **compensating movements** in the opposite direction. The history of the mistake is part of the history.
3. **Every movement names its cause** (`document_type` + `document_id`) and its author (`user_id`).

**What this buys us:** the question *"how did this IMEI end up here, and who touched it?"* is answerable by selecting one table ordered by time. Reconciliation between "what the system says" and "what the ledger implies" is a query, not an investigation. Auditability is not a feature we add later; it is a consequence of the shape of the data.

**What this costs us:** more writes per operation, and a projection that can theoretically drift from the ledger if someone bypasses the rules. Mitigation: a `verify-projections` CLI command that recomputes levels from the ledger and reports mismatches — run it in CI against test fixtures, and on demand in production.

### 4.4 Documents

Six document types, all sharing one lifecycle:

```
DRAFT  ──confirm──▶  CONFIRMED  ──cancel──▶  CANCELLED
  │                                              ▲
  └──────────────── delete ─────────▶ (gone)     │
                                                 │
                        (compensating movements written)
```

| Document | Direction | Effect on confirm |
|---|---|---|
| **`PurchaseOrder`** | → supplier | **None.** A PO is an intention to buy, not a stock event. |
| **`GoodsReceipt`** | ← supplier **or trade-in** | Creates `DeviceUnit`s (serial) / increments levels (qty). `+` movements. |
| **`SalesInvoice`** | → customer | Marks units `SOLD` / decrements levels. `−` movements. |
| **`SupplierReturn`** | → supplier | Marks units `RETURNED_TO_SUPPLIER` / decrements levels. `−` movements. |
| **`StockCount`** | internal | Writes adjustment movements for every discrepancy found. `±` movements. |
| **`WriteOff`** | internal | Marks units `WRITTEN_OFF` / decrements levels. `−` movements. |

**Stock only moves on confirm.** A draft document is a shopping list; it touches nothing. This means a half-finished receipt sitting open on someone's screen has zero effect on the books.

**A document is editable only while `DRAFT` — and, while `DRAFT`, it is freely editable.** Lines may be added, removed, and repriced as many times as the operator likes, because nothing downstream has happened yet: no movement, no financial transaction, no PDF, no customer debt. That freedom is the entire purpose of the draft state.

**Confirming ends it.** From `CONFIRMED` onward the document is **immutable** — every field, every line, every amount. There is no "small correction" path: a confirmed document that is wrong is **cancelled** (which writes compensating movements, §4.3) and re-entered. This is not strictness for its own sake — a confirmed document has already written rows into two append-only ledgers and, for a sale, may have opened a customer debt. Editing it after the fact would leave the ledgers describing a document that no longer exists, and the whole audit chain of §4.3 rests on that never happening.

**Cancel writes compensating movements**, never deletes. A cancelled sale is *two* sets of movements (the sale, and its reversal), not zero.

Documents carry a human-readable, per-tenant sequential number (`PO-2026-0001`, `INV-2026-0042`).

**A Goods Receipt states where the goods came from**, because for used stock the answer is not "a supplier":

```
GoodsReceipt.acquisition_source ∈ { SUPPLIER, TRADE_IN }
GoodsReceipt.supplier_id — required for SUPPLIER, and NULL for TRADE_IN
```

Used handsets are bought from **walk-in customers**, and the earlier draft of this document had nowhere to put them: `GoodsReceipt` was defined as strictly *← supplier*, so a trade-in would have had to be received against a fictitious supplier row named "Trade-in". That works and costs no schema, but it makes the supplier report lie and turns *"what did we make on trade-ins?"* — the question a store that buys used stock asks constantly — into a filter on a supplier's **name**. One enum column, added while the schema is still being written, makes it a real query instead. A trade-in receipt may optionally name the `Customer` it was bought from; a PO can never be linked to one (there is no order for a phone that walked in the door).

`SUPPLIER` remains the default and the new-goods flow is untouched.

### 4.5 Money — UZS and USD

> #### The complete money model, in seven rules
>
> This box is the final word. Every money question in this document reduces to one of these rules; if a future change contradicts one, that change reopens the model — otherwise the model is closed.
>
> 1. **Two currencies exist: `USD` and `UZS`. There is no exchange rate anywhere in the system.** Nothing converts, ever.
> 2. **An amount is an integer in minor units plus a currency** (`BIGINT`; USD exponent 2 = cents, UZS exponent 0 = whole som). Floats are rejected. A bare int is not money.
> 3. **Currency belongs to the product** (phones default USD, accessories default UZS) and is immutable once the product has movement history.
> 4. **Documents may mix lines of both currencies; every total anywhere is per-currency.** Two subtotals side by side, never added together, never converted.
> 5. **Margin is same-currency subtraction**: a phone's USD price minus its own USD cost (specific identification); an accessory's UZS price minus its UZS weighted-average cost.
> 6. **All customer debt is one som number**: the seller writes the total som debt at the counter; `remaining = debt − Σ payments`. Credit-company sales settle instantly and create no debt.
> 7. **Reports show a USD column and a UZS column** and re-running any past report yields identical figures — structurally, because rule 1 leaves nothing that could drift.
>
> Rules 1–2 and 5's arithmetic guard are already **implemented and tested** in `domain/value_objects/money.py` (42 domain tests passing as of M0).

The system supports exactly **two currencies in v1: `UZS` (Uzbek som) and `USD`**. This is not a placeholder for "any currency" — it is the real shape of an Uzbek phone business:

- **Phones are bought *and* sold in USD** — *booked* in USD, more precisely: a used handset traded in by a walk-in customer may be **paid for in som**, and the owner states its cost in dollars while the som actually handed over is recorded as an inert, unsummable fact (§4.5b). No rate enters the system; the owner's own valuation does.
- **Accessories, cases, and chargers are bought *and* sold in UZS.**

**Each line of business is internally single-currency, so no conversion ever happens.** A phone costing $500 and selling for $600 has a margin of $100 — both sides are already USD. A case costing 30,000 so'm and selling for 50,000 so'm has a margin of 20,000 so'm. Subtraction works because the units already match.

> **This is the single most important simplification in the document.** An earlier draft assumed devices were bought in USD and sold in UZS, forcing *every* sale to carry an exchange rate. That machinery is **gone**: there is no tenant base currency, no rate on ordinary sales or purchases, no conversion at report time, and no FX settings screen. Reports present **separate totals per currency, side by side, never merged** (§5.10). Confirmed with the target users: phone sellers are content with a USD total and a UZS total and do not want them combined into one number.
>
> Even credit needs no rate: a credit company pays the store in full at sale time (nothing to convert), and a store-credit debt is written directly in som by the seller — the som figure *is* the debt, no conversion field involved (§4.7).

Every monetary amount is stored as:

```
amount_minor : BIGINT   -- integer, in the currency's minor unit
currency     : CHAR(3)  -- 'UZS' | 'USD'
```

**Never a float.** Floats lose fractions, and lost fractions in an inventory system are indistinguishable from theft.

#### The exponent trap

The two currencies **do not have the same number of decimal places**, and getting this wrong corrupts every amount in the system by a factor of 100:

| Currency | Minor unit | Exponent | `1,000` stored as | Reads as |
|---|---|---|---|---|
| **USD** | cent | **2** | `100000` | $1,000.00 |
| **UZS** | — (tiyin is defunct) | **0** | `1000` | 1 000 so'm |

ISO 4217 nominally assigns UZS an exponent of 2 (tiyin), but tiyin have been out of circulation for years — nobody prices a phone at 12,000,000.50 so'm. **We treat UZS as exponent 0.** Amounts are whole som.

The consequence: **the code may never assume a fixed exponent.** `Money` is a value object that knows its currency's exponent and refuses to be constructed, compared, or added without it. `Money(1000, UZS)` is one thousand som; `Money(1000, USD)` is ten dollars. A bare integer with no currency attached is not money and must not exist in the domain.

UZS amounts are large (a mid-range phone is ~12,000,000 so'm; annual turnover runs into the trillions). `BIGINT` is required — a 32-bit int overflows at ~2.1 billion, which is roughly 175 phones.

#### Currency is a property of the product

A **`Product` carries a `currency`**, chosen when the product is created:

- **`SERIAL` products (phones) default to `USD`.**
- **`QUANTITY` products (accessories) default to `UZS`.**

The default is a convenience, not a constraint — a tenant who buys accessories in USD can say so. Like `tracking_type`, **a product's currency is immutable once any stock movement references it** (§FR-2.1): changing the currency of a product that already has purchase and sale history would silently reinterpret every past amount by a factor of ~12,600.

Everything downstream inherits this currency: the product's cost on a receipt, its sale price on an invoice, its COGS, and its share of inventory value are all denominated in the product's own currency, start to finish.

#### Documents may mix currencies; totals are per currency

**A document has no single currency of its own.** Each line carries the currency of *its* product, and the document totals are **one subtotal per currency present**:

```
INVOICE INV-2026-0042
  iPhone 15 Pro   IMEI 35…21     $600.00
  Silicone case                 50 000 so'm
  ─────────────────────────────────────────
  TOTAL:  $600.00  ·  50 000 so'm      ← two totals, never added together
```

A customer buying a phone and a case is **one sale on one invoice**. The system does not force the counter to split a single basket into two documents just to satisfy its own bookkeeping.

**This is the same "separate totals" principle already applied to reports (§5.10), applied consistently here:** amounts of different currencies sit side by side and are never merged into one number. Nothing is converted; there is simply more than one total.

**Credit does not complicate this.** Mixed currencies exist only on the *revenue* side (per-currency subtotals, per-currency margin). The *debt* side is untouched: a store-credit sale's debt is a single som figure the seller enters for the whole invoice, whatever mix of currencies its lines carry (§4.7). One invoice, two revenue subtotals, one som debt.

**What this costs us:** every money field is two columns (`amount_minor` + `currency`), and every comparison must check currency — the `Money` value object enforces this. **What it saves us:** no exchange rates, no conversion, no rate-freezing, no FX settings, and reports whose numbers are reproducible because nothing is ever recalculated.

### 4.5b Sale price — catalog price vs per-unit price

> This section decides **where a sale price lives**. It does not touch §4.5's seven rules: a price is still an amount in the product's currency, still never converted, still never summed across currencies. Nothing here reopens the money model.

#### The problem: used handsets are not interchangeable

`Product.default_sale_price` is a **model-level** price, and for new goods that is exactly right — every sealed "iPhone 15 Pro 256GB Titanium" in the box is the same thing, so one price serves all of them.

Used stock breaks that assumption, and this store trades used stock. Two handsets of the same model:

| Unit | Battery | Screen | Box | Bought for | Priced at |
|---|---|---|---|---|---|
| **A** | 95% | clean | yes | $380 | **$520** |
| **B** | 78% | scratched | no | $300 | **$400** |

Same catalog row, same SKU, same `Product` — **different money**. One price field on the catalog entry cannot express that, and no amount of care at the call site will make it able to.

#### The decision: the price lives where the cost lives

The system already solved this exact shape once, on the cost side. `DeviceUnit.acquisition_cost` is per-unit because *"two identical iPhones bought a month apart have different costs; average costing would destroy that"* (§4.2), and COGS for phones is specific identification (§4.6). The sale price of a used handset is the same problem viewed from the other side, and it gets the same answer:

> **A serialized unit's sale price is a property of the unit, not of the catalog entry.** `DeviceUnit.asking_price` sits next to `acquisition_cost`, in the same currency, set by the same person, at the same moment.

This is deliberately *not* symmetric with new goods. New goods keep the catalog price, because for new goods the catalog price is correct and re-entering it on every unit would be pure friction.

#### Resolving the price of a line — one rule, and its one hard edge

When a unit is added to a Sales Invoice (FR-4.2), its price is resolved in exactly this order:

```
price_for(unit, product):
    1. unit.asking_price is not None          →  unit.asking_price
    2. unit.condition is NEW
       and product.default_sale_price is not None
                                              →  product.default_sale_price
    3. otherwise                              →  PriceNotSetError  (the line is refused)
```

**Step 2's `condition is NEW` guard is the whole point of the rule, and it is not optional.**

The obvious version — *"unit price, else catalog price"* — is a silent-corruption trap. A used iPhone 15 Pro worth $500, received without an asking price, against a catalog row holding the **new** price of $900, would be quoted at **$900** at the counter. There is no error, no empty field, no visual cue: the invoice has a number on it, the ledger books $900 of revenue, and the margin report shows a $600 profit that never existed. The failure is invisible precisely because a plausible figure appeared. **A unit whose condition is not `NEW` never inherits the catalog price.** It carries its own price or it cannot be sold.

**A `QUANTITY` line has no unit, so it has no step 1.** An accessory resolves to `product.default_sale_price` or the line is refused — the same `PriceNotSetError`, reached one step earlier. A catalog row with no price is therefore *sellable* only if it is `SERIAL`: a `QUANTITY` product without a catalog price cannot be sold at all, because there is nowhere else a price could come from (§4.1). This is stated because the `SERIAL` phrasing above reads as if every unpriced product were rescuable by pricing its units, and for accessories that is not true.

Two useful consequences fall out of the rule for free:

- **A model the store only ever trades used** — an iPhone 11 nobody sells new any more — is just a catalog row with `default_sale_price = NULL`. Step 2 then never fires for any of its units, so every one of them must be priced individually. **No "is this a used-only product" flag is needed**; the absence of a catalog price already says it.
- **A specific *new* unit can still be discounted individually** — an opened box, a display model, a unit with a damaged carton — by giving it an `asking_price`. Step 1 takes precedence over the catalog for every condition, so this needs no separate mechanism.

#### The price is set at intake, and enforced at both ends

The owner prices a used handset **when they acquire it** — that is the only moment when the phone is in their hands, the battery health is on screen, and the purchase price was just negotiated. So a Goods Receipt's per-unit scan row carries, for a serialized line, `(imei, acquisition_cost, condition, asking_price?)` rather than `(imei)` alone.

Two guards, at deliberately different layers:

1. **A Goods Receipt cannot be confirmed** while any of its serialized units has `condition ≠ NEW` and no `asking_price`. Unpriced used stock never reaches the shelf.
2. **An invoice line refuses to resolve** (`PriceNotSetError`) when the rule above falls through to step 3. Redundant on the happy path — and necessary anyway, because a unit can enter stock **without passing through a receipt at all**: a stock count's *unexpected* list (FR-6.3) creates units for handsets the system did not know it had, and those arrive with no price by construction.

Pricing is an Owner/Manager permission (§2.1) — a Storekeeper *"should not see margins or set prices"* (§2). The practical consequence is stated plainly rather than discovered later: **a receipt containing used units needs an Owner or Manager to price it before it can be confirmed.** That matches how the business actually runs, since the owner is the one who buys the trade-in and decides what it is worth.

#### Markdowns are an append-only log, and `asking_price` is its projection

Used stock that does not move gets cut, then cut again. That is the core discipline of the trade, and *"we paid $300, asked $420, cut it twice, sold at $360"* is a question the owner will ask — of a specific handset, months later.

So repricing is not an `UPDATE`. It is a row:

```
device_unit_price_changes:
  id, device_unit_id, occurred_at,
  old_price_minor (nullable — the first pricing has no predecessor),
  new_price_minor, reason, user_id
```

`DeviceUnit.asking_price` is **the latest row of that log**, exactly as `StockLevel` is a projection of `stock_movements` (§4.3) and a customer's balance is a projection of debt-minus-payments (§4.7). The initial pricing at intake writes the first row (`old = NULL`), so the log is complete from the unit's first moment and the projection is never seeded out of band. Same discipline, same reason, same `verify-projections` sweep — this introduces a table, not a concept.

Constraints worth naming: only a unit that is `IN_STOCK` or `RESERVED` may be repriced (repricing a sold handset is meaningless and would corrupt its trace), and a price cannot be **un**set — there is no reprice-to-`NULL`.

#### The catalog price changes too, and it is logged the same way

New goods are repriced constantly — a model gets cheaper as its successor ships, a supplier's cost moves, a competitor across the bazaar cuts first. So `Product.default_sale_price` is **not fixed at product creation**; an Owner or Manager changes it whenever the shelf price changes, under the same permission as unit pricing (§2.1).

The change is a row, not an `UPDATE`:

```
product_price_changes:
  id, product_id, occurred_at,
  old_price_minor (nullable — a product created without a catalog price has no predecessor),
  new_price_minor, reason, user_id
```

`Product.default_sale_price` is the latest row of that log, exactly as `DeviceUnit.asking_price` is the latest row of *its* log. Same shape, same discipline, same `verify-projections` sweep.

**Why this is not over-engineering.** The asymmetry of the alternative is what condemns it: cutting one used handset by $40 would be an immutable row naming its author, while changing the price of a model — an act that governs **every future sale of every unit of it** — would be a silent overwrite. The catalog price is the higher-leverage of the two by a wide margin, and it is the one the store touches most often. *"Why was this iPhone sold at $850 in March when the catalog says $780?"* is answerable only if March's catalog price is recoverable, and a confirmed invoice's own snapshot (FR-4.5b) answers it for **that** invoice while saying nothing about what the shelf price was for the twenty invoices that did not get written.

Two things this deliberately does **not** do:

- **It does not touch confirmed documents.** A confirmed invoice snapshotted its own prices (FR-4.5b) and is immutable (§4.4); changing a catalog price cannot reach backwards into one. Revenue already booked never moves.
- **It does not reprice units.** A `NEW` unit with no `asking_price` inherits the catalog price *at resolution time*, so it follows the catalog automatically; a unit carrying its own `asking_price` is unaffected, because step 1 always wins. There is no cascade, and no bulk rewrite of `device_units` — which is the point of resolving a price rather than storing it twice.

**Currency cannot change with the price.** A product's currency is immutable once it has movement history (§4.5 rule 3, FR-2.1), so a repricing is always a new amount in the currency the product already had.

#### A trade-in paid for in som

Phones are quoted and resold in USD, but a used handset is bought from whoever walks in, and that person is often paid in **som**. Taken literally this contradicts §4.5's line that *"phones are bought and sold in USD"* — and if the fix were a currency column on the unit's cost, it would contradict rules 3 and 5 as well: COGS in som against `SALE_REVENUE` in dollars makes a unit's margin **uncomputable**, breaks the ageing report's implied margin (FR-9.4) and the month-end gross margin (FR-10.5), and leaves FR-10.7's per-currency reconciliation holding a som inventory value for a handset whose revenue lands in the USD column. That is not a column; that is reopening the money model.

The resolution keeps all seven rules intact:

> **The owner states the acquisition cost in the product's currency. The system never converts anything.** A handset bought for `4 200 000 so'm` is received at the USD figure the owner names — `$330`, because that is what they were thinking when they made the offer. The som actually handed over is recorded next to it, in `cash_paid_minor` / `cash_paid_currency`, as **a fact about the deal and not an amount in any ledger**.

The exchange judgement happens **once, in the owner's head, at the moment of negotiation** — which is exactly where it belongs and the only place it is ever accurate. It does not become a rate table, a settings screen, a daily fixing, or a field that has to be right for the books to balance. Rule 1 is untouched: there is still no exchange rate anywhere in the system, because nothing in the system divides one currency by another.

What `cash_paid` is for: the IMEI trace (FR-9.2) and the unit's own page show *"paid 4 200 000 so'm · booked at $330"*, so months later the owner can see what actually left the till for this specific phone. What it is **not** for: it enters no `FinancialTransaction`, no inventory value, no margin, no month-end figure, and no `SUM()` anywhere. `PURCHASE` is booked at `acquisition_cost`, in the product's currency, like every other receipt line. **Any report that adds `cash_paid` to anything is a bug** — it is deliberately denormalized, deliberately inert, and exists only to be read one row at a time.

*(This is also why the field is a pair and not a `Money` on the domain entity's arithmetic path: it must be impossible to accidentally include in a total that a `Money` would otherwise happily participate in.)*

#### What an asking price is *not*

- **It is not the price the unit sold for.** The `SalesInvoice` line snapshots its own `unit_price` at confirm, and *that* is what revenue is booked from (§4.6). The asking price only ever *seeds* the line. A later markdown cannot retroactively change what a past invoice says — which is why the two are separate fields with separate names.
- **It is not an inventory value.** On-hand value and COGS are computed from `acquisition_cost`, always (§4.6). **A markdown below cost does not write inventory down** — v1 carries stock at cost, with no lower-of-cost-or-market rule. The loss on a bad buy is recognised when the unit sells, as a thin (or negative) margin, not when the owner changes the sticker.
- **It is not a financial transaction.** Repricing moves no money, so it writes **no** `FinancialTransaction` row. The money ledger records what happened, and nothing happened.
- **It does not exist for `QUANTITY` products.** Accessories have no per-unit identity to hang a price on (§4.1); they are priced from the catalog, full stop. This entire section concerns `SERIAL` products only.

#### A draft does not reserve a price — resolution happens again at confirm

A draft invoice can sit open for hours, and prices move underneath it: the owner marks the very handset in it down from $520 to $480, or cuts the catalog price of the model. **The draft line is re-resolved at confirm** (§4.5b's rule, run again), so the customer pays $480.

The alternative — the price freezing at the moment the scanner beeped — is worse in both directions. The customer is charged a price the store has already publicly abandoned; and because a confirmed line records what the system *resolved* alongside what was *charged* (below), the frozen $520 against the live $480 would be written into the deviation report as a **+$40 deviation nobody made**. The report exists to surface human decisions, and it is worthless the moment it starts inventing them.

The rule is one line: **`charged` is the explicit override if a Manager made one, otherwise the freshly resolved price; `resolved` is always recomputed at confirm.** A draft therefore holds no price of its own until someone deliberately types one — which is also why repricing a `RESERVED` unit is allowed (FR-2.16): the open draft simply picks the new price up.

One consequence, stated rather than discovered: if a Manager overrides a line to $300 and the unit is *then* marked down to $480, the confirmed line reads *charged $300, resolved $480* — the deviation is measured against the shelf price at the moment of sale, not against the price the Manager was looking at. That is the correct denominator for *"what did we give up on this sale?"*, and the case is rare enough not to warrant a second stored figure to answer a question nobody asks.

#### Overriding a price on one sale — the deviation is recorded, not policed

Repricing a unit in stock is logged with its author (above). **Selling one handset below its price is the same economic act by an easier route** — edit the invoice line, leave the shelf price alone — so leaving that route unlogged would make the log above trivially avoidable. It is recorded too.

But not as edit history. A draft's line may be repriced freely and untracked (FR-4.5c); what is recorded is **one fact at confirm**: what the system resolved (FR-2.14), what was actually charged, and **who approved the difference**. Last writer wins — there is no history of a person trying three figures before settling.

The author matters because the two acts can be different people: a Manager approves the discount, a Seller confirms the invoice. Without this, the ledger's `user_id` names the Seller and **misattributes the decision** — worse than recording nothing.

**No threshold, no approval workflow, no mandatory justification.** A note may be given and is kept, but is never required: a field demanded on every $20 haggle becomes a dash within a week and then means nothing. And the right threshold differs between new goods (a deviation is an exception) and used (a deviation is the negotiation the asking price always anticipated) — v1 does not pretend to know it. **The system makes the deviation visible; the owner decides what it means** — the same stance as the debtor list, which sorts by age and issues no penalties.

Naming is deliberately neutral: a **deviation**, not a discount. Selling a sought-after model *above* its asking price is the same event, and equally worth seeing.

**What this buys us:** used stock is priced honestly, per handset, by the person who valued it; the new-goods flow is untouched; **every price anything ever carried — a handset or a whole model — is recoverable from one table ordered by time**; a trade-in paid for in som is recorded truthfully without an exchange rate entering the system; and no price concession can be made without a name attached to it.

**What this costs us:** one nullable price column and one inert cash-paid pair on the unit, **two** small append-only tables (one per price that can move), one enum on the receipt, three columns on an invoice line, a price resolution that runs twice per sale rather than once, and a receipt that a Storekeeper cannot finish alone when it contains used goods.

> **On timing:** `device_units` does not exist yet (M2 is catalog; the table lands in M3). Deciding this now costs a few columns in schemas still being written. Deciding it at M5 costs a migration plus a backfill of prices onto used stock already on the shelf — figures nobody recorded, which would have to be guessed. The catalog-price log is the sharper version of the same point: it lands in **M2**, with the products table itself, and every day it is deferred is a day of price history that does not exist and cannot be reconstructed.

### 4.6 `FinancialTransaction` — the money ledger

The stock ledger (§4.3) answers *"what happened to the goods?"*. It cannot answer *"what happened to the money?"* — a receipt of 10 phones and a receipt of 10 phones at double the cost look different financially but similar in units. So the money gets its own append-only ledger, built on exactly the same principles as the stock ledger.

**Every confirmed document with a financial consequence writes one or more `FinancialTransaction` rows, in the same transaction as its stock movements.** The two ledgers move together or not at all.

```
id, occurred_at, txn_type, direction (+/-),
amount_minor, currency,          -- the product's own currency; never converted
category, document_type, document_id,
location_id, product_id (nullable), device_unit_id (nullable),
user_id, note
```

**Every aggregate over this ledger is grouped by `currency`.** There is no total that spans both — a `SUM(amount_minor)` without a `GROUP BY currency` is a bug, and adding 500 (USD cents) to 30000 (som) is meaningless arithmetic the `Money` value object exists to prevent.

**Transaction categories** (the vocabulary the month-end report groups by):

| `txn_type` | Sign | Written when | Meaning |
|---|:--:|---|---|
| `PURCHASE` | − | Goods Receipt confirmed | Money owed to / spent on suppliers (inventory acquired). |
| `SALE_REVENUE` | + | Sales Invoice confirmed | Revenue earned from the customer. |
| `COGS` | − | Sales Invoice confirmed | Cost of the specific goods sold (see valuation below). |
| `WRITE_OFF_LOSS` | − | Write-Off confirmed | Book value of stock destroyed/lost. |
| `SUPPLIER_RETURN_CREDIT` | + | Supplier Return confirmed | Value credited back for goods sent to the supplier. |
| `COUNT_ADJUSTMENT` | ± | Stock Count confirmed | Value of surplus (+) or shortage (−) found in a physical count. |
| `PAYMENT_RECEIVED` | + | A customer pays down a store-credit balance (§4.7) | **Cash collected**, always UZS, not revenue. Settles debt; does **not** re-book revenue. |

The same rules as the stock ledger apply, and for the same reasons:

1. **Nothing records money except by writing a transaction.** No code sets a running total directly.
2. **Transactions are immutable.** Cancelling a document writes **reversing transactions**, never deletes.
3. **Every transaction names its cause and author**, and records the amount in the product's own currency — the report never converts anything, so historical figures cannot drift.

> **Revenue is not cash — and this is the trap credit introduces.** `SALE_REVENUE` (and its `COGS`) is booked in full **the moment a sale is confirmed**, whether or not a single som has been paid. That is *accrual* accounting, and it is what makes margin correct: the profit on a phone is earned when it is sold, not dribbled in as the customer pays. `PAYMENT_RECEIVED` is a separate, *cash* dimension — it settles the debt the sale created. **A payment must never write `SALE_REVENUE`**, or every store-credit payment would inflate revenue and the books would double-count. The month-end report (§5.10) therefore presents two distinct views: an **accrual view** (revenue, COGS, margin — unchanged by credit) and a **debt/cash view** (who owes what, what was collected).

#### Inventory valuation — how COGS and on-hand value are costed

This is the one genuinely new decision the financial ledger forces, and it differs by tracking type:

- **Serialized phones → specific identification.** Every `DeviceUnit` carries *its own* `acquisition_cost`. When that exact unit sells, its COGS is its own cost — exact, no estimation. This is the payoff of serializing: valuation is not a model, it's a fact.
- **Quantity accessories → weighted-average cost.** A box of cases has no per-unit identity, so on-hand value is `average_unit_cost × quantity`, where the average is maintained from the purchase ledger. When accessory prices move, the average moves; COGS uses the average at time of sale. Simple, standard, and computable from the ledger.

**On-hand inventory value** at any instant is reported **per currency**: (Σ `acquisition_cost` of every `IN_STOCK` device unit) in USD, and (Σ `avg_cost × qty` for every accessory stock level) in UZS — shown side by side, never summed together.

**What this buys us:** the month-end report (§5.10) is a *grouping query over one ledger*, and closing inventory value can be independently recomputed from stock and cross-checked. Money and goods reconcile by construction.

**What this costs us:** a second ledger write on every confirm, a valuation rule to maintain for accessories, and a reconciliation check to run. Accepted — without it, "how did the store do this month?" has no answer.

### 4.7 Credit Sales & Customer Debt

A phone can leave the store before the customer has paid for it, in exactly two ways — and they could hardly be more different in what the system must do:

| `payment_type` | What happens | What the store must track |
|---|---|---|
| `PAID_IN_FULL` | Paid on the spot. The ordinary sale. | Nothing. Settled. |
| `CREDIT_COMPANY` | A third-party credit company (Uzum Nasiya, Alif Nasiya, …) finances the customer and **pays the store the full price immediately**. The customer's monthly schedule is calculated and collected by the company. | **Nothing about the money.** From the store's side this is a settled sale — it differs from `PAID_IN_FULL` only by a label: *which company* financed it, and optionally their contract number, for later lookup ("which sales went through Uzum?"). |
| `STORE_CREDIT` | The store itself lets the customer pay later. | **An open balance in UZS**: total owed, paid so far, remaining. No schedule, no due dates, no interest. |

Two decided simplifications, stated so nobody re-complicates them later:

- **Credit-company sales carry no financial machinery.** The company pays in full, immediately. No receivable, no payout tracking, no commission, no exchange rate. If a company ever starts paying less than full price or paying late, that becomes a v2 conversation — the schema records which sales were financed by whom, so history survives such a change.
- **Store credit is an open balance, not a schedule.** The system answers "how much has this customer paid and how much is left" — the exact question asked — and nothing more. No installment rows, no due dates, no overdue computation. The debtor list shows days-since-sale, so old debts are still plainly visible.

#### Store credit: the debt is written in soums

**The debt of a store-credit sale is always denominated in UZS, even when the phone itself is priced in USD.** At the counter, the seller enters the **total som amount the customer will pay** (e.g. phone priced `$600`, debt written as `7 800 000 so'm`), plus any down payment in som. That som figure *is* the debt — there is no rate field and no conversion; whatever conversion happened was in the seller's head when they quoted the price, which is how these deals are actually struck.

The invoice line keeps its USD price, so **revenue and margin are booked in USD exactly as for a cash sale** (§4.6, accrual). The som debt is the *collection* side, tracked separately — the same accrual-vs-cash separation the ledger already makes everywhere.

```
invoice_debt_uzs      (entered at sale)  −  Σ payments_uzs  =  invoice_remaining_uzs
customer_balance_uzs  =  Σ invoice_remaining_uzs over their open invoices
```

**All customer debt in the entire system is a single som number per customer.** No per-currency balances, no schedules — a shopkeeper's notebook, made auditable.

#### Entities

**`CreditCompany`** — reference data, Owner-maintained: `name`, contact, `is_active`. A `CREDIT_COMPANY` invoice stores `credit_company_id` + optional `contract_ref`. That is the entire model.

**`Payment`** — an **append-only** record of money received from a customer against a store-credit invoice: `occurred_at`, `amount` (UZS), `method` (cash / transfer / card — a *label*, not a processed transaction), `invoice_id`, `user_id`, `note`. Confirming a payment writes a `PAYMENT_RECEIVED` financial transaction (§4.6) and reduces the remaining balance. A payment cannot exceed the invoice's remaining balance. **Payments are never edited; a mistaken payment is reversed by a compensating negative payment**, same as every other ledger in this system.

#### Balances are projections, not stored counters

`customer_balance_uzs` and `invoice_remaining_uzs` are always derived from the append-only pair *(debt entered at sale) − (payments recorded)* — no code ever assigns `customer.balance = X`. Same discipline as the stock and money ledgers, same reason: a balance recomputable from immutable history is a balance you can trust. A `verify-balances` check (sibling of `verify-projections`) recomputes every balance from the ledger and asserts it against any cached projection.

**A customer financed by a credit company owes the store nothing** — their balance correctly reads zero, with the sale visible in their history labelled with the company. Attributing the company's debt to the customer would be the most misleading thing this system could do.

**The phone leaves at confirm on every payment type** — units go `SOLD`, full `SALE_REVENUE`/`COGS` booked (§4.6). The only difference between the three types is who, if anyone, still owes the store money afterwards: nobody, nobody, the customer.

---

## 5. Functional Requirements

Each requirement is phrased as *actor → action → observable outcome*, so it converts directly into a test case.

### 5.1 Authentication & Tenancy

- **FR-1.1** A SuperAdmin creates a tenant with a name, a unique slug, and an owner email (`apexwms create-tenant`); the tenant is unusable until provisioning reaches `active`. **There is no public sign-up** — an anonymous visitor cannot create a tenant. *(Test: `POST /auth/signup` is `404`.)*
- **FR-1.1b** Provisioning seeds exactly one Owner — a master `users` row plus the matching `employees` row in the new store, sharing an id — with a generated temporary password. At first login the response reports `must_change_password`, and the Owner changes it via `POST /auth/change-password`, which revokes all sessions opened with the temporary one.
- **FR-1.2** A user authenticates with email + password **naming no tenant**; the store their token speaks for is stamped in server-side from their own record. They receive an access token (short-lived) and a refresh token (long-lived). Passwords are hashed with argon2id.
- **FR-1.3** One person has **one login identity**, and may work at several stores. The issued token carries at most one `tenant_id` and the role held *at that store*; `X-Tenant` switches between stores the user has access to, **without re-authenticating**. A platform operator's token carries no tenant claim at all. *(Test: one identity, two stores, two different roles.)*
- **FR-1.3b** A request naming no tenant, by header or claim, receives `400`; one naming an unknown store receives `404`. Naming a store the caller has no `user_tenant_access` grant for receives `403`, checked before any tenant session opens.
- **FR-1.4** A request with a token for tenant A can never read or write data in tenant B — **including its staff list**. *(Test: issue a token for A, attempt every endpoint, assert no row from B is reachable.)*
- **FR-1.5** An Owner can invite someone by email and assign a role; the invitee sets their own password via a signed, single-use, expiring link. The invitation is stored centrally so it can be accepted by someone with no tenant context, and grants a role only at the store that issued it. Accepting as an existing user adds a store rather than creating a second account.
- **FR-1.6** A request lacking the **permission** an operation requires receives `403`, and the operation has no side effect. Authorization compares permissions drawn from one catalog, never role names — §2.1 is not hierarchical.
- **FR-1.7** Responses omit `acquisition_cost`, `cash_paid`, and margin fields entirely for Storekeeper and Seller roles. *(`cash_paid` is what the store paid for a trade-in, §4.5b — a cost figure, and hidden as one.)*

### 5.2 Catalog & Reference Data

- **FR-2.1** A Manager can create a product with a `tracking_type` **and a `currency`**; both are **immutable** once any stock movement references the product.
- **FR-2.2** A Manager can create locations, suppliers, and customers.
- **FR-2.3** A product with `tracking_type = QUANTITY` may carry a barcode (EAN/UPC), unique within the tenant.
- **FR-2.4** Deactivating a product prevents new movements against it but preserves all history.

### 5.2b Currency (UZS / USD)

- **FR-2.5** Only `UZS` and `USD` are accepted. **There is no tenant base currency and no exchange rate anywhere in the system** — a store-credit debt is written directly in som by the seller (§4.7), not converted.
- **FR-2.6** Every product is created with a currency, **defaulting to `USD` for `SERIAL` (phones) and `UZS` for `QUANTITY` (accessories)**. The user may override the default at creation.
- **FR-2.7** A document (PO, Goods Receipt, Sales Invoice, Supplier Return) **may contain lines in both currencies**. Each line takes its currency from its product, and the document presents **one subtotal per currency present**, never a combined total. *(Test: create an invoice, add a USD phone and a UZS accessory, confirm it — the document reports exactly two totals, `$600.00` and `50 000 so'm`, and no field anywhere holds their sum.)*
- **FR-2.8** A document's amounts are stored and reported **as transacted, with no conversion**. *(Test: confirm a $500 purchase; re-read it a year later — it is still exactly `$500`, having passed through no rate at all.)*
- **FR-2.9** Amounts are stored in minor units with **per-currency exponents: USD = 2, UZS = 0**. *(Test: `Money(1000, "UZS")` renders as `1 000 so'm`; `Money(1000, "USD")` renders as `$10.00`.)*
- **FR-2.10** Adding or comparing two `Money` values of different currencies raises a domain error. There is no implicit conversion anywhere in the domain.
- **FR-2.11** **Every monetary total in every report is grouped by currency and presented per currency.** No figure anywhere sums USD and UZS into a single number. *(Test: a report over a period containing both phone and accessory sales returns a USD total and a UZS total as separate values — never one combined figure.)*

### 5.2c Sale Price — catalog vs per-unit (§4.5b)

- **FR-2.12** A product's `default_sale_price` is **optional**. A `SERIAL` product created without one is valid and sellable — its units simply must each carry their own price. A `QUANTITY` product without a catalog price is **not** sellable, because an accessory has no unit to hang a price on (§4.1) and no other source exists; its lines are refused by FR-2.14 until the catalog price is set. *(Test: create a serialized product with no catalog price — it saves and its individually-priced units sell; create a quantity product with no catalog price — it saves, but adding it to an invoice is refused with "price not set".)*
- **FR-2.13** A `SERIAL` `DeviceUnit` may carry an `asking_price`, denominated in **its product's currency** — there is no per-unit currency, and a price in any other currency is rejected. `QUANTITY` products have no per-unit price at all. *(Test: attempt to price a unit of a USD product in UZS — rejected with a currency error.)*
- **FR-2.14** A `SERIAL` invoice line's price is resolved as: **the unit's own `asking_price`; else the product's `default_sale_price` — but only if the unit's `condition` is `NEW`; else the line is refused** with a "price not set" error. **A unit whose condition is not `NEW` never inherits the catalog price.** A `QUANTITY` line has no unit and therefore no first step: it resolves to `default_sale_price` or is refused by the same error. *(Test: a `USED` unit with no asking price, whose product's catalog price is $900, is refused — it must not be quoted at $900. Then price the unit at $500 and confirm the line takes $500.)*
- **FR-2.15** Setting or changing a unit's asking price requires the pricing permission (Owner/Manager, §2.1) and **appends a `device_unit_price_change` row** recording old price, new price, reason, actor, and timestamp. `DeviceUnit.asking_price` is the latest such row and is never written independently. *(Test: price a unit at intake, cut it twice — the unit shows the third price and its history shows three rows in order, the first with a null old price.)*
- **FR-2.16** Only a unit that is `IN_STOCK` or `RESERVED` may be repriced, and a price cannot be unset. *(Test: reprice a `SOLD` unit — rejected, stating the unit's status.)*
- **FR-2.17** Repricing writes **no** `FinancialTransaction` and does **not** change the unit's `acquisition_cost` or any inventory value — including when the new price is below cost. *(Test: mark a unit down below what it cost; the financial ledger is unchanged and on-hand value still reports the acquisition cost.)*
- **FR-2.18** A unit's `condition` is set at intake and may afterwards be changed only by Owner/Manager — it is a pricing input, not a description. Changing it away from `NEW` while the unit holds no asking price makes it unsellable by FR-2.14 rather than silently repricing it, and the unit is surfaced as needing a price (FR-9.6). *(Test: flip a `NEW` unit with no unit price to `USED`, then attempt to sell it — refused, not quoted at the catalog price.)*
- **FR-2.19** A product's `default_sale_price` **may be changed at any time** by Owner/Manager (§2.1), including being set on a product that had none. Every change **appends a `product_price_change` row** recording old price, new price, reason, actor, and timestamp; `Product.default_sale_price` is the latest such row and is never written independently (§4.5b). The new price is denominated in the product's own currency — currency is immutable (FR-2.1), so a repricing never changes it. *(Test: create a product at $900, cut it to $850 then $780 — the product shows $780 and its history shows three rows in order, the first with a null old price; then attempt to reprice it in UZS — rejected with a currency error.)*
- **FR-2.20** Changing a catalog price affects **only prices resolved after the change**. Confirmed invoices are immutable and keep their snapshots (FR-4.5b); units carrying their own `asking_price` are unaffected (FR-2.14 step 1 wins); `NEW` units without one follow the catalog automatically, with **no bulk write to `device_units`**. *(Test: confirm an invoice at the $900 catalog price, then cut the catalog to $780 — the confirmed invoice and its `SALE_REVENUE` still read $900, an unpriced `NEW` unit in stock now quotes $780, and a unit asking $850 still quotes $850.)*
- **FR-2.21** Units may be repriced **in bulk** — a list of `(unit, new price)` pairs with one shared reason — applied atomically in a single transaction, appending one `device_unit_price_change` per unit under the same permission and constraints as FR-2.15/FR-2.16. Each unit's new price is stated explicitly; there is no percentage or formula applied across a list (§1.3). *(Test: mark down eight units from the ageing report in one call — eight log rows, eight updated projections; add one `SOLD` unit to the same call and the whole call is rejected with nothing written.)*

### 5.3 Inbound — Purchase Orders & Receiving

- **FR-3.1** A Manager creates a Purchase Order: supplier and lines of `(product, quantity, unit_cost)` — each line's currency comes from its product (FR-2.7); the document has no currency of its own. It is a `DRAFT`.
- **FR-3.2** Confirming a PO fixes its numbers and generates a PDF. **It does not change stock.**
- **FR-3.3** A Storekeeper creates a Goods Receipt, optionally from a PO (which pre-fills its lines).
- **FR-3.3b** A Goods Receipt states an `acquisition_source` of `SUPPLIER` (the default, requiring a supplier) or `TRADE_IN` (no supplier, optionally naming the `Customer` the handset was bought from) — §4.4. A receipt created from a PO is always `SUPPLIER`. *(Test: create a trade-in receipt with no supplier — it saves and confirms; attempt a `SUPPLIER` receipt with no supplier — rejected; attempt to link a PO to a `TRADE_IN` receipt — rejected.)*
- **FR-3.4** For a `SERIAL` line, the Storekeeper scans one IMEI per unit. The system validates the Luhn check digit and rejects malformed IMEIs **at scan time**, not on submit.
- **FR-3.4b** Each scanned unit carries its own `acquisition_cost`, `condition`, and — where the condition is not `NEW` — its own `asking_price` (§4.5b). Cost and price are visible and settable only to Owner/Manager (§2.1); a Storekeeper scans IMEIs and states condition.
- **FR-3.4c** A scanned unit's `acquisition_cost` is always stated in **its product's currency** (§4.5 rule 3). Where the store actually paid in a different currency — a trade-in bought for som against a USD catalog row — the amount handed over may additionally be recorded in `cash_paid_minor` / `cash_paid_currency`. **The system performs no conversion between the two and derives neither from the other**; the owner states both. *(Test: receive a trade-in at `$330` with `cash_paid = 4 200 000 so'm`; the `PURCHASE` financial entry is exactly `−$330`, the unit's inventory value is `$330`, and no figure anywhere equals or contains 4 200 000.)*
- **FR-3.4d** `cash_paid` is **informational only**: it appears on the unit's detail and in the IMEI trace (FR-9.2) and **enters no financial transaction, no inventory value, no margin, and no report total**. *(Test: run the month-end report over a period containing a som-paid trade-in — every figure is identical to the same report with `cash_paid` cleared.)*
- **FR-3.5** Scanning an IMEI that already exists in this tenant is rejected immediately with a message naming the existing unit's status and location. *(A duplicate IMEI is either a scanning error or a stolen-goods red flag. Never silently accept it.)*
- **FR-3.6** For a `QUANTITY` line, the Storekeeper enters a count.
- **FR-3.7** Confirming a Goods Receipt creates the `DeviceUnit`s with their per-unit acquisition cost, increments quantity levels, and writes one `+` movement per line. Units enter as `IN_STOCK` at the receipt's location.
- **FR-3.8** A receipt whose serial line has fewer scanned IMEIs than its declared quantity cannot be confirmed.
- **FR-3.9** Receiving against a PO records the linkage, and the PO reports its received-vs-ordered state (`pending`, `partial`, `complete`).
- **FR-3.10** A Goods Receipt **cannot be confirmed** while any of its serialized units has `condition ≠ NEW` and no `asking_price`. The error names the offending IMEIs, so the pricing gap is fixed in one pass rather than discovered one unit at a time. *(Test: receive two units, one `NEW` and one `USED` with no price — confirm is refused and names only the used unit; price it, and confirm succeeds.)*
- **FR-3.11** Confirming a receipt writes the initial `device_unit_price_change` row for every unit given an asking price at intake (FR-2.15), so a unit's price history begins at the moment it enters stock.
- **FR-3.12** A receipt's lines, scanned IMEIs, costs, conditions, and asking prices are editable **only while it is `DRAFT`** (§4.4); a `CONFIRMED` receipt is immutable and is corrected by cancellation, not by patching. A draft may sit with units unpriced or unscanned indefinitely — the completeness checks (FR-3.8, FR-3.10) run at confirm, not at scan. *(Test: leave a used unit unpriced in a draft receipt — the draft saves fine; confirm is refused until it is priced.)*

### 5.4 Outbound — Sales & Issue

- **FR-4.1** A Seller creates a Sales Invoice: customer (optional) and location. Line currencies come from their products (FR-2.7); the invoice has no currency of its own.
- **FR-4.2** The Seller scans an IMEI; the system resolves it to a `DeviceUnit` and adds it as a line at that unit's **resolved price** (FR-2.14): its own `asking_price` if it has one, otherwise the product's `default_sale_price` — the latter only for a `NEW` unit.
- **FR-4.2b** A scan that resolves to no price is **rejected at scan time** with a "price not set" error naming the unit, in the same spirit as FR-3.4's Luhn rejection — never added as a zero-priced or catalog-priced line. The Seller cannot fix it (pricing is Owner/Manager, §2.1), so the message says who can. *(Test: scan a `USED` unit with no asking price whose product has a catalog price; the line is refused and no invoice line is created.)*
- **FR-4.2c** An **accessory** line may also be added by picking the product from the catalog and stating a quantity, for a till with no scanner or an accessory with no printed barcode. This resolves the price and merges into one line per product exactly as scanning the barcode does (`_sell_accessory`). **A phone is never added this way** — a sale is of one named handset, identified by its IMEI (FR-4.2); the manual path refuses a `SERIAL` product. *(Test: add an accessory to a draft by product id and quantity 3 — one line for 3 at the catalog price; try the same with a phone's product id — refused.)*
- **FR-4.2d** Adding an accessory line, by scan or by catalog pick (FR-4.2c), is **rejected at that moment** if the store holds fewer of the product at the invoice's location than the line would then sell — the same on-hand rule the confirm enforces (FR-4.7), applied early so the seller is told while the customer is at the counter. The confirm re-checks, because stock can fall while the draft is open. *(Test: receive 2 of an accessory, then add 3 to a draft — refused, and no line is created.)*
- **FR-4.3** Scanning an IMEI that is not `IN_STOCK` is rejected, stating the actual status. *(You cannot sell a phone that is already sold.)*
- **FR-4.4** Scanning an IMEI held at a different location than the invoice's is rejected.
- **FR-4.5** Only Owner/Manager may override a line's price. A Seller's invoice uses the resolved price (FR-4.2) unchanged. An override edits **that invoice line only** — it is a negotiation on one sale, and it does not reprice the unit in stock or write a `device_unit_price_change`. *(Test: override a line to $480, then cancel the invoice — the unit returns to stock still asking its original price.)*
- **FR-4.5b** Confirming an invoice **snapshots each line's `unit_price`**; revenue is booked from the snapshot (§4.6), and no later change to the unit, the catalog, or anything else can reach back into it. *(Test: a unit asking $520 is sold with the line overridden to $480 — the confirmed invoice and its `SALE_REVENUE` both read $480, while the unit's own price history still ends at $520.)*
- **FR-4.5b1** The snapshot is taken by **re-resolving the price at confirm** (FR-2.14), not by reusing what was resolved when the line was scanned: **a draft reserves no price.** A line the operator has not explicitly overridden takes the freshly resolved price, so a markdown made while the draft was open reaches the customer. An explicit override survives re-resolution and is what is charged. *(Test: scan a unit asking $520 into a draft, mark the unit down to $480, then confirm — the invoice books $480 and reports no deviation. Repeat with the line overridden to $300 before the markdown — the invoice books $300 and reports the deviation against $480.)*
- **FR-4.5b2** A line whose price **stops resolving** between scan and confirm — its unit was flipped to `USED` while the draft sat open (FR-2.18) — makes the confirm fail with the same "price not set" error, naming the line. *(Test: scan a `NEW` unit priced from the catalog, change its condition to `USED`, then confirm — refused, and nothing is written to either ledger.)*
- **FR-4.5c** A line may be added, removed, or repriced **only while the invoice is `DRAFT`**, and while `DRAFT` it may be repriced any number of times — a draft has written nothing, so there is nothing to keep consistent. No history is kept of edits within a draft. *(Test: reprice a draft line three times, then confirm — the invoice books the third price and nothing records the first two.)*
- **FR-4.5d** Any attempt to add, remove, or edit a line on a `CONFIRMED` or `CANCELLED` invoice is **rejected with no side effect** (§4.4): a wrong confirmed invoice is cancelled and re-entered, never patched. *(Test: confirm an invoice, then `PATCH` one of its lines — rejected, and re-reading the invoice, the stock ledger, and the financial ledger shows all three byte-identical to before the attempt.)*
- **FR-4.5e** A line's price must be **zero or positive** in the product's own currency. A negative price is rejected — a giveaway is a zero-priced line, and money flowing the other way is a return, not a sale. *(Test: override a line to a negative amount — rejected with a domain error, not stored.)*
- **FR-4.5f** Every confirmed line stores the price the system **resolved at confirm** (FR-2.14, FR-4.5b1) alongside the price actually **charged**. Where they differ, the line also stores **`price_approved_by`** — the user who last overrode it — and an **optional** free-text note. The approver is stamped when the override is made, not at confirm, because **the person who approves a discount and the person who confirms the invoice need not be the same** — without it the ledger's `user_id` names the confirmer and misattributes the decision. *(Test: a Manager overrides a $520 line to $300 and a Seller confirms — the line reports resolved $520, charged $300, approved by the Manager, while the `SALE_REVENUE` row still names the Seller as the confirmer.)*
- **FR-4.5g** The note is **never mandatory** — no threshold, no approval workflow, no justification gate (§4.5b). *(Test: override a line with no note; the invoice confirms normally and the deviation is still fully attributed.)*
- **FR-4.6** Confirming the invoice marks each unit `SOLD`, decrements quantity lines, writes one `−` movement per line, and generates the invoice PDF.
- **FR-4.7** Confirming an invoice whose line quantity exceeds available stock is rejected atomically — no partial fulfilment.
- **FR-4.8** Cancelling a confirmed invoice returns the units to `IN_STOCK` **by writing compensating `+` movements**. The original movements remain.

### 5.5 Returns to Supplier

- **FR-5.1** A Manager creates a Supplier Return, scans the IMEIs of units being sent back, and states a reason (defective, unsold, wrong item).
- **FR-5.2** Only units currently `IN_STOCK` may be added.
- **FR-5.2b** A unit may only be added to a return whose supplier is the one that delivered it — proven by the Goods Receipt that put the unit in stock. A unit taken in as a trade-in and a unit a Stock Count discovered are both refused: neither names a supplier. Accessory (quantity) lines are not checked, because a quantity line records no origin. Refused on the scan, and re-checked at confirm.
- **FR-5.3** Confirming marks units `RETURNED_TO_SUPPLIER`, writes `−` movements, and generates the Return-to-Supplier PDF.

### 5.6 Stock Counts & Write-Offs

- **FR-6.1** A Storekeeper opens a Stock Count for a location; the system snapshots expected stock at that moment.
- **FR-6.2** The Storekeeper scans every IMEI physically present and enters counts for quantity products.
- **FR-6.3** On close, the system reports three lists: **matched**, **missing** (expected, not scanned), and **unexpected** (scanned, not expected — including IMEIs unknown to the system entirely).
- **FR-6.4** Only Owner/Manager may confirm the count's adjustments. Confirming writes `±` adjustment movements bringing the system in line with reality.
- **FR-6.4b** A unit created from the **unexpected** list enters stock with **no `asking_price`** — nothing about a surprise handset says what it is worth. It is therefore unsellable until priced (FR-2.14), and appears on the "needs pricing" list (FR-9.6). *(Test: confirm a count that found an unknown IMEI, then attempt to sell it — refused for want of a price, not quoted from the catalog.)*
- **FR-6.5** A Manager can write off units (damage, loss, theft) with a mandatory reason, producing `−` movements. Units become `WRITTEN_OFF`.

### 5.7 Scanning & Lookup

- **FR-7.1** `GET /scan/lookup?code=<x>` resolves a scanned string to *either* a `DeviceUnit` (by IMEI) *or* a `Product` (by barcode/SKU), and **states which kind it found**. One call — the operator's scanner does not know what it just scanned.
- **FR-7.2** The lookup returns, for a device: model, status, location, **condition, and the price it would sell at** (its resolved price per FR-2.14, or an explicit "not priced"), plus — role permitting — its cost and margin. The price is what the Seller actually needs at the counter; the cost is what they must not see (FR-1.7). This is the "customer walks in with a phone" screen.
- **FR-7.3** Lookup responds within **200ms at p95**. A storekeeper scanning 50 units must never wait on the system.
- **FR-7.4** An unrecognized code returns a clear "not found" — not a 500, not an empty 200.

### 5.8 Documents (PDF)

- **FR-8.1** Confirming a PO, Sales Invoice, or Supplier Return generates a PDF carrying the tenant's name, address, and logo.
- **FR-8.2** Invoice lines show the IMEI for serialized items. *(This is the customer's proof of which handset they bought.)*
- **FR-8.3** A document's PDF is **immutable once confirmed**; regenerating it produces byte-identical content. Cancellation overlays a "CANCELLED" mark rather than deleting the file.
- **FR-8.4** Each document line shows its amount in its own currency, correctly formatted (`$1,000.00` vs `1 000 so'm`), and the document footer shows **one subtotal per currency present** — never a combined total, and never a converted one.

### 5.9 Reporting

- **FR-9.1** **Stock on hand** — by location, by product, by brand. Includes total cost value (Owner/Manager only).
- **FR-9.2** **IMEI trace** — given an IMEI, the complete chronological movement history: received on which document, **from which supplier or as a trade-in from which customer** (FR-3.3b), at what cost — and, where they differ, **what was actually paid in cash** (FR-3.4c) — **every price it was ever offered at and who changed it** (§4.5b), sold on which invoice, to whom, for how much, by which user. *(Test: a handset traded in for 4 200 000 so'm and booked at $330, priced at $420, cut to $390 then $360, and sold at $350 renders every one of those events, in order, on one timeline, with the som figure shown beside the booked cost and included in no total.)*
- **FR-9.2b** **Catalog price history** — for a product, every `default_sale_price` it has carried, with actor, timestamp, and reason (FR-2.19). Answers *"what was the shelf price of this model in March?"*, which no individual invoice can. *(Test: reprice a product twice, then read its history — three entries in order, the first with a null old price.)*
- **FR-9.3** **Sales summary** — over a date range, by location: units sold, revenue, cost of goods, margin.
- **FR-9.4** **Ageing** — units `IN_STOCK` for longer than N days, each with its **acquisition cost, current asking price, implied margin, and how many times it has been marked down**. *(Dead stock is the phone retailer's core financial risk, and a used handset that has been cut twice and still has not moved is the sharpest form of it.)*
- **FR-9.5** **Movement log** — the raw ledger, filterable by product, location, user, date, movement type.
- **FR-9.6** **Needs pricing** — every `IN_STOCK` unit that resolves to no price (FR-2.14): used units received before anyone priced them, and units surfaced by a stock count (FR-6.4b). This is the worklist that keeps unsellable stock from being discovered at the counter with a customer standing there.
- **FR-9.7** **Price deviations** — over a date range, every confirmed line whose charged price differed from the resolved one (FR-4.5f): the handset, the two prices, the difference, **who approved it**, the customer, and the note if one was given. Sortable by approver and by customer, because *"one manager, one customer, over and over"* is the pattern this report exists to make visible. It reports deviations in **both** directions — a model sold above its asking price is information too.
- **FR-9.8** **Selling below cost** — FR-2.19 read backwards: active quantity accessories whose weighted-average cost has reached or passed their `default_sale_price`, by location, each with its on-hand quantity and per-unit shortfall. Every further sale of one books a loss until an Owner/Manager reprices it. A worklist, not a block — selling below cost can be deliberate. Confirming a goods receipt or a sales invoice that touches such an accessory returns the same alert on its response, shown to whoever confirmed; neither confirm is blocked.

### 5.10 Financial Ledger & Month-End Report

- **FR-10.1** Every confirmed document that has a financial consequence writes its `FinancialTransaction` row(s) **in the same database transaction** as its stock movements. A confirm either records both goods and money, or neither.
- **FR-10.2** Cancelling a confirmed document writes **reversing** financial transactions; the originals remain. *(Test: confirm a sale, cancel it, and assert the net financial effect for that document is zero while both transactions are visible in the ledger.)*
- **FR-10.3** An Owner/Manager can pull a **financial transaction log** over any date range, filterable by category, location, and document — the raw money ledger, mirroring the movement log.
- **FR-10.4** An Owner/Manager can run a **Month-End Report** for a given month and location (or consolidated across all locations). **Every figure in it is reported per currency — a USD column and a UZS column, side by side, never merged into one number.**
- **FR-10.5** The Month-End Report presents the following, **each as a pair of independent per-currency figures (USD for the phone business, UZS for accessories)**:
  - **Opening inventory value** (= previous period's closing).
  - **Purchases** — value of goods received.
  - **COGS** — cost of goods sold (specific-identification for phones, weighted-average for accessories, per §4.6).
  - **Sales revenue** and **gross margin** (revenue − COGS), with margin % — **accrual, i.e. all sales confirmed in the period, paid or not.**
  - **Write-offs** and **count adjustments** — value lost or corrected.
  - **Supplier-return credits**.
  - **Closing inventory value** (= opening + purchases − COGS − write-offs − returns ± adjustments).
  - **Customer debt movement** (UZS): opening debt, + store-credit sales booked, − payments collected, = **closing debt outstanding**.
  - **Cash collected on store credit** in the period (Σ `PAYMENT_RECEIVED`, UZS) — distinct from revenue, so the owner sees the gap between what was earned and what actually came in.
  - **Sales by financing type** — counts and revenue split across paid-in-full / credit-company (by company) / store-credit, so the owner sees how the store actually sells.
- **FR-10.6** The report breaks the closing inventory figure down **by location** — the warehouse's stock value and each store's stock value shown separately, then totalled — so the owner sees where the value physically sits.
- **FR-10.7** The report's **closing inventory value must equal the independently-computed on-hand value** at period end, **checked per currency** (USD serialized units against the USD figure, UZS accessory value against the UZS figure). A mismatch is surfaced as a reconciliation error, not silently reconciled. *(This is the money-side analogue of `verify-projections`.)*
- **FR-10.7b** The report's **closing customer debt must equal the sum of every customer's balance** (§4.7) at period end — the `verify-balances` check, run as part of the report. All debt is UZS, so this is a single-figure reconciliation.
- **FR-10.8** All period boundaries are computed in the **tenant's timezone**: a month runs `[00:00 on the 1st, 00:00 on the 1st of next month)` in that timezone, so a sale at 23:30 on the 31st lands in the correct month.
- **FR-10.9** The Month-End Report is exportable as a PDF carrying the tenant's letterhead and the period.
- **FR-10.10** Because no figure is ever converted (§4.5), **re-running a past month's report always yields identical numbers.** Reproducibility here is structural: there is no rate that could have moved. *(Test: generate March's report twice, months apart — byte-identical figures.)*

> **On "opening = previous closing":** in v1 both are computed live from the ledger since inception — the ledger is complete and immutable, so no stored month-end snapshot is required for correctness. Snapshotting closing balances is a v2 performance optimization (see risks), not a correctness need.

### 5.11 Credit Sales & Payments

- **FR-11.1** When creating a Sales Invoice, a Seller chooses a `payment_type` of `PAID_IN_FULL`, `CREDIT_COMPANY`, or `STORE_CREDIT`. `PAID_IN_FULL` behaves exactly as the existing outbound flow.
- **FR-11.2** The phone leaves at confirm on every payment type: units are marked `SOLD` and the full `SALE_REVENUE`/`COGS` is booked in the product's own currency, whether or not any money has been received.
- **FR-11.3** An Owner can maintain the **credit companies** reference list (name, contact, active).
- **FR-11.4** A `CREDIT_COMPANY` sale records the company and an optional contract reference, and is **settled at confirm** — it creates no debt, no receivable, and no schedule. *(Test: confirm a financed sale; the customer's balance is zero and no open debt exists anywhere; the sale is filterable by company.)*
- **FR-11.5** For a `STORE_CREDIT` sale, the Seller enters the **total debt in UZS** (regardless of the line currencies) and an optional **down payment in UZS**. Confirming books revenue/COGS as usual, opens the debt, and **records the down payment as the first `Payment`** (writing its `PAYMENT_RECEIVED` entry) — so the projection formula `remaining = debt − Σ payments` holds with no special case, and the down payment appears in "cash collected" like any other payment. *(Test: sell a $600 phone with `debt = 7 800 000 so'm`, `down = 800 000` — revenue is $600, one payment of 800 000 exists, and the customer owes exactly 7 000 000 so'm.)*
- **FR-11.6** A user with the right role can **record a payment** (UZS, date, method label) against an open store-credit invoice, reducing its remaining balance. A payment exceeding the remaining balance is rejected.
- **FR-11.7** Recording a payment writes a `PAYMENT_RECEIVED` transaction and **never** a `SALE_REVENUE` one. *(Test: pay a store-credit sale down to zero across several payments — total `SALE_REVENUE` for the sale equals its price exactly once.)*
- **FR-11.8** A mistaken payment is reversed by a compensating negative payment; the original stays in the ledger.
- **FR-11.9** Any user (cost-visibility aside) can view a **customer's account**: open invoices with entered debt, paid so far, remaining, and days since sale; plus their financed sales labelled by company (informational, zero balance).
- **FR-11.10** An Owner/Manager can run a **debtor list**: every customer with a balance > 0, their total UZS balance, and the age of their oldest open invoice, sorted worst-first. *(This is the "who owes what" answer — no buckets, no schedule needed.)*
- **FR-11.11** Cancelling a store-credit invoice reverses stock, revenue, and COGS as in FR-4.8 and voids the remaining debt. Payments already received are surfaced for refund handling, never silently deleted. Cancelling a credit-company sale is the plain FR-4.8 flow — there was no debt to void.

---

## 6. Scanning Contract

The scanner is a **keyboard-wedge** device: it types the code into whatever input has focus, then sends `Enter`. There is no driver, no SDK, no backend hardware integration. Any $20 USB or Bluetooth scanner works.

This puts the entire burden on the API being fast and unambiguous:

- **One lookup endpoint, two possible answers.** The client sends a string; the server says "this is a device unit" or "this is a product" or "I don't know this code." The client does not need to guess whether 15 digits means IMEI.
- **Scan-session semantics.** While a Goods Receipt or Stock Count is open, scanned codes are appended to it one at a time via a dedicated endpoint. Each append returns immediately with accept/reject and the running count.
- **Reject at scan time, not on submit.** A duplicate or malformed IMEI must be rejected on the scan that caused it, while the operator still has the physical phone in their hand. Discovering 3 bad scans when submitting a 50-unit receipt is a broken workflow.
- **Idempotency.** Scanners double-fire. An identical scan of the same code into the same open document within a short window is a no-op, not an error.
- **Sub-200ms p95.** Non-negotiable. Below this, the operator scans continuously; above it, they stop and watch the screen, and the workflow collapses.

---

## 7. Architecture

### 7.1 Stack

| Concern | Choice |
|---|---|
| Language | Python 3.14 |
| Package/env manager | **uv** |
| Web framework | FastAPI |
| Validation & serialization | **Pydantic v2** — CQRS commands/queries/results in `application` (§7.3), `pydantic-settings` for `Settings` in `infrastructure`. **Never imported by `domain`** (§7.3). |
| DI | **Dishka** |
| ORM | SQLAlchemy 2.x (async) |
| Driver | **asyncpg** (0.31+ ships cp314 wheels; **psycopg3** is the fallback) |
| Migrations | Alembic |
| Database | PostgreSQL 16+ |
| Auth | JWT (access + refresh), argon2id password hashing |
| PDF | WeasyPrint (HTML/CSS templates) — see §10 |
| Tests | pytest, pytest-asyncio, testcontainers |

### 7.2 Monorepo layout

```
apexwms/
├── apps/
│   ├── backend/
│   │   ├── src/
│   │   │   ├── domain/          # entities, value objects, domain errors
│   │   │   ├── application/     # CQRS commands/queries/handlers, ports (protocols), DTOs
│   │   │   ├── infrastructure/  # SQLAlchemy, tenancy, JWT, PDF, Alembic
│   │   │   ├── presentation/    # FastAPI routers, schemas
│   │   │   ├── di/              # composition root: Dishka providers & container
│   │   │   └── main.py          # ASGI entry point
│   │   ├── tests/
│   │   └── pyproject.toml
│   └── frontend/                # Next.js — later
├── packages/                    # shared contracts, if/when needed
├── docs/
│   └── prd.md
├── docker-compose.yml
└── pyproject.toml               # uv workspace root
```

### 7.3 Clean Architecture — the dependency rule

**Dependencies point inward. Always.**

```
presentation ──▶ application ──▶ domain
      │                │             ▲
      └───▶ infrastructure ──────────┘
                (implements ports defined in application)
```

- **`domain/`** — pure Python. Entities (`DeviceUnit`, `StockMovement`), value objects (`IMEI`, `Money`), domain errors. **Zero imports from anything outside `domain/`.** No SQLAlchemy, no FastAPI, no Pydantic. If `IMEI` can't validate its own Luhn digit without a database, the design is wrong.
- **`application/`** — CQRS: a `Command`/`Query` (one Pydantic message, one business operation: `ReceiveGoodsCommand`, `SellDevicesCommand`, `ConfirmStockCountCommand`) paired with an `IRequestHandler` that executes it (`ReceiveGoodsHandler`, ...). `application/core/` holds the shared primitives (`IRequest`, `IRequestHandler`, `Command`, `Query`, `Result`/`ResultWithData`/`PagedResult`). It also defines **ports** — `Protocol` classes describing what a handler needs (`DeviceUnitRepository`, `UnitOfWork`, `PdfRenderer`, `Clock`). It depends on `domain` for business rules, and on `pydantic` for its message layer only — `domain` stays framework-free.
- **`infrastructure/`** — the implementations. SQLAlchemy models and repositories, the tenant engine registry, the JWT service, the PDF renderer. It *implements* the ports that `application` declared. The arrow points inward: `application` never imports from `infrastructure`.
- **`presentation/`** — FastAPI routers and exception handlers, Dishka wiring. Thin: a route parses no JSON of its own — the request body **is** a `Command`/`Query` from `application`, so the router authorizes, calls the paired handler, and returns what it returns.

**Why the ports live in `application`, not `infrastructure`:** this is the inversion in "dependency inversion," and it's the bit people get backwards. The use case *declares its needs*; infrastructure *satisfies them*. Consequence: `application` can be tested with in-memory fakes and no database at all.

#### Data shapes across the layers — where Pydantic v2 lives, and what a DTO is

Data-carrying classes split by **role, not by layer** — the message layer (CQRS commands/queries/results) and the DI-context layer are both in `application`, and are **not interchangeable**:

| Kind | Class kind | Example | Job |
|---|---|---|---|
| CQRS message | **Pydantic v2 `Command`/`Query`, and their `Result`/`ResultWithData[TData]` payloads** (`application`) | `ConfirmInvoiceCommand`, `InvoiceData` | Parse and validate the request (structural: types, required fields, ranges) — the request body **is** the command, there is no separate presentation schema; carry the handler's output back out. This is also where **role-based field omission** happens (FR-1.7): a Staff-facing query simply returns a leaner `TData` with no cost fields. |
| DI-context DTO | **frozen `@dataclass`es** (`application`) | `CurrentUser`, `IssuedClaims` | Carry data across DI boundaries — never on an HTTP wire. No behavior, no validation logic, no framework imports. |
| Domain object | **Entities & value objects** (`domain`) | `Money`, `IMEI`, `GoodsReceipt` | Not DTOs at all — they hold *behavior and invariants*. An `IMEI` validates itself; a DTO never does. |
| Persistence model | **SQLAlchemy models** (`infrastructure`) | `DeviceUnitModel` (mapped to `device_units`) | The *persistence* shape of an entity. **Never escapes the repository**: each repository maps row ↔ domain entity internally, so `application` never sees the ORM. |

**Who maps what:** row ↔ entity mapping lives **inside repositories** (`infrastructure`) — the repository's public signatures speak domain types only. Entity → `TData` mapping lives in **`application`**, next to the payload class it builds — see `.claude/rules/backend/cqrs-response-models.md` for exactly where and how. No mapping code exists in `domain` — that layer is mapped *to*, never mapping itself.

**Why CQRS messages are Pydantic and DI-context DTOs stay dataclasses:** `application` depends on `domain` only for *business logic* — that rule is unchanged, and `domain` remains 100% framework-free. But a command or query is inescapably a validated, serializable message: carrying structural validation (types, required fields, ranges) at the one place a request enters a handler is exactly what Pydantic is for, and duplicating that validation with a second presentation-side schema was pure ceremony. Semantic validation (a well-formed IMEI, a non-negative Money, a confirmable receipt) still happens in the domain, unchanged. DI-context values that never reach a wire (`CurrentUser`, `RequestedTenant`, internal token/claims carriers) stay frozen dataclasses — nothing about them benefits from a validation framework.

The flow for one request:

```
HTTP JSON ──▶ Command/Query (application: shape, types — Pydantic)
          ──▶ entities & value objects (domain: invariants)
          ──▶ Result / ResultWithData[TData] (application) ──▶ JSON
```

**When a command/query needs a field, and when it needs none.** Every handler's `__call__` takes exactly one `Command`/`Query` — even `GetMeQuery`, which carries no client-supplied fields at all, because identity comes from `CurrentUser` injected into the handler's constructor instead. A message earns real fields once the input is *compound* — `CreateInvoiceCommand` with customer, location, payment type, and a list of lines — or needs its own structural constraint (`Field(min_length=..., ge=...)`). Fields sourced from context (the authenticated user, the resolved tenant) are constructor-injected into the handler, never smuggled onto the command as a client-supplied field; a URL path segment is the one exception, added with a default and merged in by the router before dispatch (see `application/commands/change_user_role.py`). The rule mirrors §7.6: no field exists before there's a concrete value that needs carrying.

### 7.4 A command end to end: `ReceiveGoods`

Tracing one operation through every layer, because this is the pattern every other operation copies:

1. **`presentation/routers/receipts.py`** — `POST /receipts/{id}/confirm`. The request body **is** `ConfirmReceiptCommand` (parsed and structurally validated by Pydantic before the route body runs); the router checks the role, asks Dishka for a `ConfirmReceiptHandler`, and returns what it returns — no separate request/response schema.
2. **`application/commands/confirm_receipt.py`** — `ConfirmReceiptHandler.__call__(request: ConfirmReceiptCommand) -> ResultWithData[ReceiptData]`. Depends only on ports: `GoodsReceiptRepository`, `DeviceUnitRepository`, `StockMovementRepository`, `UnitOfWork`, `Clock`, plus `CurrentUser` for the acting user. It loads the receipt, asks the domain to validate it, creates the `DeviceUnit`s, writes the movements, commits, and returns `ResultWithData[ReceiptData].succeed_with_data(...)`.
3. **`domain/entities/goods_receipt.py`** — `GoodsReceipt.confirm()` enforces the invariants: not already confirmed; every serial line has exactly as many scanned IMEIs as its declared quantity; no IMEI appears twice; **no unit with `condition ≠ NEW` lacks an `asking_price`** (FR-3.10). **These rules live in the domain and are testable with no I/O whatsoever** — the pricing guard in particular is a pure function of the receipt's own lines, needing neither the catalog nor a database.
4. **`infrastructure/persistence/`** — the SQLAlchemy repositories that actually satisfy those ports, and the `UnitOfWork` that wraps it all in one transaction against *this tenant's* database.

The handler does not know a tenant exists. It does not know Postgres exists. That is the entire point.

### 7.5 Dishka scopes

| Scope | Provides |
|---|---|
| `APP` | Settings, the MasterDB engine, the tenant `EngineRegistry`, the JWT service, the PDF renderer. |
| `REQUEST` | The authenticated user, the resolved tenant, that tenant's `AsyncSession`, the `UnitOfWork`, repositories, and every command/query handler. |

The tenant-scoped `AsyncSession` is the linchpin: it's provided at `REQUEST` scope by pulling the tenant from the validated JWT and asking the registry for that tenant's engine. Everything downstream — every repository, every handler — is automatically bound to the right database without a single line of code below `presentation` mentioning tenancy.

### 7.6 On DDD (a note on how this will be taught)

This document uses Clean Architecture, which is a *structural* discipline: where code lives and which way imports point. DDD is a *modelling* discipline: how you find the right objects in the first place. They're complementary, not the same thing, and you do not need to understand DDD to build v1.

DDD concepts will be introduced **against real code, at the moment the code needs them**, not up front:

- **Value objects** — arrive immediately, in `IMEI` and `Money`. The simplest DDD idea and the one with the fastest payoff: an `IMEI` that cannot exist in an invalid state deletes an entire class of bugs.
- **Entities & identity** — `DeviceUnit` is the obvious teaching case: two handsets of the same model are *not* equal, even with identical attributes, because identity is not attributes.
- **Aggregates & invariants** — when we build `GoodsReceipt.confirm()`. A receipt and its lines are one consistency boundary: you cannot confirm a receipt whose lines don't add up, so they must be loaded, validated, and saved as a unit. This is where "aggregate" stops being jargon and starts being obvious. The store-credit invoice (whose remaining balance must always equal entered debt minus its payments, never negative) is the second worked example, at M5b.
- **Domain events** — deferred. Not needed in v1. When a stock movement needs to trigger a low-stock alert, that's the moment to introduce them, and not before.

The rule: no DDD concept enters this codebase before there's a concrete problem in *this* system that it solves.

---

## 8. API Surface

All routes are prefixed `/api/v1`. Tenant-scoped routes require a bearer token carrying a `tenant` claim. **No route requires a tenant header** — `X-Tenant` is optional everywhere, and only matters for someone who works at more than one store (§3.3).

There is no tenant-management API: tenants are created and administered with the `apexwms` CLI (§3.4). An `/admin/*` surface arrives with the v2 portal (§3.5).

### Auth & Tenancy
| Method | Path | Requires |
|---|---|---|
| `POST` | `/auth/login` | anon (`X-Tenant` optional, to pick a store) |
| `POST` | `/auth/refresh` | anon (valid refresh token; `X-Tenant` optional) |
| `POST` | `/auth/accept-invite` | anon (valid invite token) |
| `POST` | `/auth/change-password` | any (own password) |
| `GET` | `/auth/me` | any |
| `GET` / `POST` | `/users`, `/users/invite` | `Permission.Users.View` / `.Manage` (Owner) |
| `PATCH` | `/users/{id}/role` | `Permission.Users.Manage` (Owner) |

### Catalog
| Method | Path | Role |
|---|---|---|
| `GET` / `POST` | `/products` | read: any · write: Manager |
| `GET` / `PATCH` | `/products/{id}` | read: any · write: Manager (a `default_sale_price` change requires the pricing permission and appends to the log, FR-2.19) |
| `GET` | `/products/{id}/price-history` | Manager (FR-9.2b) |
| `GET` / `POST` | `/locations` | read: any · write: Manager |
| `GET` / `POST` | `/suppliers` | Manager |
| `GET` / `POST` | `/customers` | Seller+ |

### Inbound
| Method | Path | Role |
|---|---|---|
| `GET` / `POST` | `/purchase-orders` | Manager |
| `POST` | `/purchase-orders/{id}/confirm` | Manager |
| `GET` | `/purchase-orders/{id}/pdf` | Manager |
| `GET` / `POST` | `/receipts` | Storekeeper+ |
| `POST` | `/receipts/{id}/scan` | Storekeeper+ (append one IMEI + condition; `acquisition_cost` and `asking_price` require the pricing permission) |
| `DELETE` | `/receipts/{id}/scan/{imei}` | Storekeeper+ (undo a scan) |
| `POST` | `/receipts/{id}/confirm` | Storekeeper+ |

*(A receipt's `POST /receipts` body carries `acquisition_source`; `supplier_id` is required for `SUPPLIER` and rejected for `TRADE_IN` — FR-3.3b.)*

### Stock & Unit Pricing

| Method | Path | Role |
|---|---|---|
| `GET` | `/device-units/{id}` | any (cost and `cash_paid` omitted for Storekeeper/Seller, §2.1) |
| `PATCH` | `/device-units/{id}/price` | **pricing permission** (Owner/Manager) — set or cut one unit's `asking_price`; appends a `device_unit_price_change` (FR-2.15) |
| `GET` | `/device-units/{id}/price-history` | Manager |
| `POST` | `/device-units/price` | **pricing permission** — reprice many units in one call, each with its own new price and a shared reason |
| `PATCH` | `/device-units/{id}/condition` | **pricing permission** (FR-2.18) |

The bulk route exists because the ageing report (FR-9.4) and the needs-pricing worklist (FR-9.6) both hand the owner a *list* of handsets to act on, and pricing them one HTTP call at a time is the interaction those reports were built to avoid. It is **not** a different kind of write: it appends one `device_unit_price_change` row per unit in one transaction, under the same permission and the same `IN_STOCK`/`RESERVED` constraint (FR-2.16). There is no "cut everything by 10%" — a percentage across a list of handsets in different conditions is exactly the automated valuation §1.3 rejects; each unit's new price is stated.

### Outbound
| Method | Path | Role |
|---|---|---|
| `GET` / `POST` | `/invoices` | Seller+ |
| `POST` | `/invoices/{id}/scan` | Seller+ |
| `PATCH` | `/invoices/{id}/lines/{line_id}` | Manager (price override; **`DRAFT` only** — `409` on a confirmed invoice) |
| `POST` | `/invoices/{id}/confirm` | Seller+ (body carries `payment_type`; for store credit: som debt total + down payment; for credit company: company + contract ref) |
| `POST` | `/invoices/{id}/cancel` | Manager |
| `GET` | `/invoices/{id}/pdf` | Seller+ |

### Credit Sales & Payments
| Method | Path | Role |
|---|---|---|
| `GET` / `POST` | `/credit-companies` | read: Seller+ · write: Owner |
| `POST` | `/invoices/{id}/payments` | Seller+ (record a UZS payment on store credit) |
| `POST` | `/payments/{id}/reverse` | Manager |
| `GET` | `/customers/{id}/account` | Seller+ (open debts, paid, remaining; financed sales labelled, zero balance) |
| `GET` | `/reports/debtors` | Manager (every customer with balance > 0, worst-first) |

### Returns, Counts, Write-offs
| Method | Path | Role |
|---|---|---|
| `GET` / `POST` | `/supplier-returns` | Manager |
| `POST` | `/supplier-returns/{id}/scan` | Manager |
| `POST` | `/supplier-returns/{id}/confirm` | Manager |
| `GET` | `/supplier-returns/{id}/pdf` | Manager |
| `POST` | `/stock-counts` | Storekeeper+ |
| `POST` | `/stock-counts/{id}/scan` | Storekeeper+ |
| `POST` | `/stock-counts/{id}/close` | Storekeeper+ (produces discrepancy report) |
| `POST` | `/stock-counts/{id}/confirm` | Manager (applies adjustments) |
| `POST` | `/write-offs` | Manager |
| `POST` | `/write-offs/{id}/confirm` | Manager |

### Scanning & Reporting
| Method | Path | Role |
|---|---|---|
| `GET` | `/scan/lookup?code=` | any |
| `GET` | `/devices/{imei}/history` | any (cost hidden by role; includes the price-change timeline) |
| `POST` | `/devices/{imei}/reprice` | Manager (append a price change: new price + reason) |
| `GET` | `/reports/needs-pricing` | Manager (in-stock units that resolve to no price) |
| `GET` | `/reports/price-deviations?from=&to=` | Manager (lines charged off their resolved price, with the approver) |
| `GET` | `/reports/stock-on-hand` | Manager |
| `GET` | `/reports/sales-summary` | Manager |
| `GET` | `/reports/ageing` | Manager |
| `GET` | `/reports/movements` | Manager |
| `GET` | `/reports/financial-ledger?from=&to=&category=&location=` | Manager |
| `GET` | `/reports/month-end?year=&month=&location=` | Manager |
| `GET` | `/reports/month-end/pdf?year=&month=&location=` | Manager |
| `GET` / `PUT` | `/settings/tenant` | read: any · write: Owner (timezone, letterhead) |
| `GET` / `PUT` | `/settings/tenant/logo` | read: any · write: Owner (base64 PNG/JPEG; an empty body clears it) |

---

## 9. Non-Functional Requirements

**Security**
- Argon2id password hashing. Access tokens ≤ 15 min; refresh tokens rotate on use and are revocable.
- Authorization is enforced **server-side, per endpoint**. The frontend hiding a button is not a permission.
- Cost/margin fields are **omitted from the response payload** for Storekeeper/Seller — not sent-and-hidden.
- Every mutating request is logged with `user_id`, `tenant_id`, action, and target.

**Data integrity**
- IMEI is unique within a tenant, enforced by a database constraint — not only by application code.
- Confirm/cancel operations are atomic: the movements, the projections, and the document status change in one transaction, or none of them do.
- Documents are append-only after confirmation. No edits — cancel and reissue.

**Performance**
- `/scan/lookup` — **p95 < 200ms**.
- List endpoints paginate by default (page size 50, max 200).
- Indexes on: `device_units.imei` (unique), `stock_movements(product_id, occurred_at)`, `stock_movements(device_unit_id)`, `products.barcode`.

**Observability**
- Structured JSON logs, every line carrying `tenant_id` and `request_id`.
- Health endpoint reports master-DB reachability and the count of live tenant engines.

**Testing**
- **Domain layer: pure unit tests, no I/O.** If a domain test needs a database, the domain is wrong.
- **Application layer:** use cases tested against in-memory fake repositories — fast, no Postgres.
- **Infrastructure/API:** integration tests against a real Postgres (testcontainers), each test module provisioning a throwaway tenant database — which also continuously exercises the provisioning path.
- **A dedicated cross-tenant isolation test suite** that, with a token for tenant A, attempts to reach tenant B's data through every endpoint. This is the test that protects the system's core promise.
- `verify-projections` runs in CI: recompute all stock levels from the ledger, assert they match the projections.
- `verify-balances` runs in CI: recompute every customer's outstanding balance from the sale/payment ledgers, assert it matches any cached projection.

**Financial correctness invariants** (asserted by tests, since a wrong number here is invisible until it's expensive)
- Revenue is booked once per sale, never per payment — total `SALE_REVENUE` for a sale equals its price regardless of how many payments were recorded.
- A fully-paid store-credit sale nets the customer's balance to 0; a cancelled-with-payment sale is flagged, never silently zeroed.
- A credit-company sale creates no debt anywhere — the customer's balance is unchanged by it.
- An invoice's remaining balance never goes negative (overpayment rejected).

---

## 10. Delivery Plan

Each milestone is independently demoable.

| # | Milestone | Delivers |
|---|---|---|
| **M0** | **Bootstrap** | uv workspace, FastAPI + Dishka skeleton, the four-layer structure, docker-compose (Postgres), CI. Demo: `/health` responds. |
| **M1** | **Tenancy & Auth** | MasterDB registry + identity, per-store `employees`, SuperAdmin provisioning CLI, engine registry, migration fan-out, JWT, two role namespaces, permission catalog. Demo: `apexwms create-tenant` twice; prove store A cannot see store B; then show one person holding one login and two different roles across both. |
| **M2** | **Catalog** | Products (both tracking types, **per-product currency** with USD/UZS defaults, **optional catalog sale price** and the `product_price_changes` log it projects from, §4.5b), locations, suppliers, customers. Demo: build a catalog, cut a model's price twice, and read back when it changed and who did it. |
| **M3** | **The ledgers** | `StockMovement` **and** `FinancialTransaction`, projections, valuation rules, `verify-projections` + financial reconciliation. Also the `device_units` table itself — including `condition`, the nullable `asking_price`, the inert `cash_paid` pair (§4.5b), and the `device_unit_price_changes` log it projects from, because these are columns in a schema being written now and a migration later. Demo: a confirm writes both a stock movement and its money entry, and both reconcile. |
| **M4** | **Inbound** | PO → Goods Receipt, **`acquisition_source` (supplier vs trade-in, FR-3.3b)**, IMEI scan-in, Luhn + duplicate rejection, per-unit cost/condition/asking price, som-paid trade-in cost (FR-3.4c), the unpriced-used-unit confirm guard (FR-3.10), `PURCHASE` financial entries. Demo: **scan 10 phones into stock with a real scanner** — some new from a supplier, some traded in from walk-ins, paid for in som, booked in dollars, and individually priced. |
| **M5** | **Outbound** | Sales Invoice, scan-to-sell, **price resolution (FR-2.14) with its refusal to fall back on used units**, **re-resolution at confirm (FR-4.5b1)**, confirm, cancel-with-compensation, **line-price overrides carrying their approver** (FR-4.5f), `SALE_REVENUE` + `COGS` entries. Demo: scan a phone, sell it, cancel, watch both goods and money reverse — then scan an unpriced used handset and watch the counter refuse it rather than quote the new-goods price. |
| **M5b** | **Credit sales & customer debt** | `payment_type` on sales, `CreditCompany` reference list, som-denominated store-credit debt, `Payment` ledger, customer accounts, debtor list, `verify-balances`. Demo: **sell a $600 phone on store credit for 7.8M som with an 800k down payment, record two payments, show the remaining balance — then sell another via a credit company and show it settled with zero debt.** |
| **M6** | **Counts, write-offs, supplier returns** | Full discrepancy → adjustment flow with `WRITE_OFF_LOSS` / `COUNT_ADJUSTMENT` / `SUPPLIER_RETURN_CREDIT` entries. Demo: hide a phone, run a count, watch the system find it missing and book the loss. |
| **M7** | **Documents** | PDF generation for PO, Invoice, Supplier Return. Demo: print a real invoice with an IMEI on it. |
| **M8** | **Reporting** | Stock on hand, IMEI trace (**including its full price history**), sales summary, ageing with cost/asking price/markdown count, needs-pricing worklist, price-deviation report, financial ledger. Demo: trace one IMEI's entire life — bought, priced, cut twice, sold below asking, with the name of whoever approved that. |
| **M9** | **Month-End Report** | Period close in tenant timezone, per-location inventory value, opening→closing reconciliation, margin, **customer-debt movement + cash collected**, PDF export. Demo: **run last month's report for the warehouse and the store, reconcile closing value against on-hand, and closing debt against customer balances.** |

**M4 is the milestone that proves the product** operationally; **M9 is the milestone that proves it financially.** Note that the financial ledger is *not* deferred to M9 — it is written from M3 onward as each document type lands, because retrofitting money entries onto already-confirmed documents would mean backfilling history. M9 only adds the *reporting* on top of a ledger that has been accruing all along.

---

## 11. Risks & Open Questions

| Risk | Impact | Mitigation / decision needed |
|---|---|---|
| **Migration fan-out** across N tenant DBs | High, ongoing | Resumable, idempotent migration CLI with per-tenant version tracking from M1. This cost is permanent — it is the price of db-per-tenant. |
| **Connection-pool exhaustion** as tenants grow | High, at scale | LRU engine registry with a hard cap. Known ceiling ≈50 concurrently-active tenants on default settings. Beyond that: PgBouncer, or reconsider isolation strategy. **We should agree on the expected tenant count.** |
| **Projection drift** from the ledger | Medium | `verify-projections` in CI and on demand. The ledger is the source of truth; projections are always rebuildable. |
| **Stock & money ledgers disagree** | High | Both are written in the *same* DB transaction on confirm (FR-10.1); a reconciliation check (FR-10.7) recomputes closing inventory value from stock and asserts it against the financial ledger. A mismatch is an error surfaced in the report, never auto-hidden. |
| **Accessory valuation method** | Medium | Weighted-average cost for quantity items, maintained from the purchase ledger (§4.6). Serialized phones sidestep this entirely via specific identification. **Confirm this matches how the owner actually thinks about accessory cost** before M3. |
| **A used unit silently inheriting the new-goods catalog price** | **High** | The signature bug of bolting used stock onto a new-goods catalog, and it is invisible: a plausible number appears on the invoice and the margin report shows profit that never existed. Mitigated structurally — a unit whose `condition ≠ NEW` **never** falls back to `default_sale_price` (§4.5b, FR-2.14), and the test asserts a used unit against a $900 catalog row is *refused*, not quoted. |
| **Unpriced used stock discovered at the counter** | Medium | The cost of FR-2.14's strictness: a customer is standing there and the sale is blocked. Mitigated by pushing pricing to intake, where it belongs — a receipt with unpriced used units cannot be confirmed (FR-3.10) — plus a "needs pricing" worklist (FR-9.6) for the residual path, units surfaced by a stock count (FR-6.4b), which no intake guard can catch. |
| **Markdowns mistaken for inventory write-downs** | Medium | Cutting an asking price moves no money and writes no `FinancialTransaction` (FR-2.17). v1 carries stock **at cost**, with no lower-of-cost-or-market rule: a bad buy is recognised as thin or negative margin when the unit sells, not when the sticker changes. Stated explicitly in §4.5b because the opposite is a reasonable thing to assume. |
| **Trade-ins have no supplier to receive against** | Medium — **decided** | Used handsets arrive from **walk-in customers**, and §4.4 originally defined `GoodsReceipt` as strictly *← supplier*. Resolved with a nullable `supplier_id` plus `acquisition_source ∈ SUPPLIER \| TRADE_IN` (§4.4, FR-3.3b), rather than a `Supplier` row named "Trade-in": the enum costs one column in a schema still being written and makes *"what did we make on trade-ins?"* a real query instead of a filter on a supplier's name. |
| **A trade-in paid for in som against a USD catalog row** | **High** | Phones are booked in USD, but a walk-in is often paid in cash som — and the naive fix, a currency on the unit's cost, makes that unit's margin uncomputable (rule 5), splits its COGS from its revenue across two currency columns, and breaks FR-10.7's per-currency reconciliation. Resolved without touching the seven rules: the owner **states the cost in the product's currency** and the som handed over is recorded in an inert `cash_paid` pair that enters no ledger, total, or report (FR-3.4c, FR-3.4d, §4.5b). The exchange judgement stays in the owner's head, where it is made; no rate enters the system. *The failure mode to watch for is a future report quietly summing `cash_paid` — FR-3.4d's test exists to catch exactly that.* |
| **A catalog price change leaving no trace** | Medium | The asymmetry that would have been: cutting one used handset by $40 is an immutable row naming its author, while changing a model's price — which governs every future sale of every unit of it — would have been a silent `UPDATE`. Resolved by giving the catalog price the same append-only log as the unit price (`product_price_changes`, FR-2.19), landing in **M2** with the products table, because deferred price history cannot be reconstructed. |
| **A draft invoice quoting a price the store has abandoned** | Medium | A draft can sit open while the handset in it is marked down. Freezing the scan-time price would charge the customer a withdrawn price *and* write a deviation nobody made into FR-9.7, poisoning the one report meant to surface human decisions. Resolved by re-resolving every un-overridden line at confirm (FR-4.5b1); explicit overrides survive. |
| **Month boundaries & timezone** | Medium | Period math runs in the tenant's timezone (FR-10.8), so a tenant timezone setting must land in M1. Without it, a late-night sale slips into the wrong month and the report is quietly wrong. |
| **Month-end report performance** at scale | Low (v1) | v1 computes opening/closing live from the full ledger — fine at MVP volumes. If a tenant's ledger grows large, add stored month-end snapshots (opening = prior stored closing) as a v2 optimization; correctness is unaffected either way. |
| **PDF library choice** | Low | **Decided: fpdf2.** WeasyPrint's HTML/CSS templates would have been easier to iterate on, but it needs Cairo and Pango — a build problem on Windows and in a slim container, for pages that are a letterhead, a table and a per-currency footer. fpdf2 is pure Python, so layouts are written in code as ReportLab's would have been, and `DocumentPage` is where that code lives once for all three documents. One catch worth recording: it stamps the wall clock into `/CreationDate`, which FR-8.3 forbids, so the creation date is pinned to the document's `confirmed_at`. |
| **Python 3.14 wheel availability** across the dependency set | Medium | asyncpg 0.31+ ships cp314 wheels. **Verify the full set at M0** — psycopg3 is the drop-in fallback driver, and SQLAlchemy's async layer needs greenlet, which must also have 3.14 wheels. |
| **Currency exponent mismatch (USD=2, UZS=0)** | **High** | The classic 100× corruption bug. Mitigated structurally: exponent lives on the `Money` value object, never in call sites; a bare int is not money. Round-trip tests for both currencies land in M0, before any money is persisted. |
| **UZS integer overflow** | Medium | `BIGINT` everywhere for `amount_minor` — a 32-bit int overflows at ~175 phones' worth of som. Enforced at the schema level. |
| **Accidentally summing across currencies** | **High** | With two currencies and no conversion, a `SUM()` missing its `GROUP BY currency` silently adds cents to som. Mitigated by the `Money` value object (cross-currency arithmetic raises), and by FR-2.11's test that every report returns per-currency totals. |
| **Mixed-currency documents** | Medium | Supported in v1 (§4.5): one invoice, one subtotal per currency. Simplified by the debt model: all customer debt is UZS regardless of line currencies, so only *revenue* is per-currency. Mitigated by `Money` (cross-currency arithmetic raises) and `verify-balances`. |
| **Double-counting revenue as cash** | **High** | The signature bug of naive credit systems. Mitigated structurally: revenue is booked once at sale (`SALE_REVENUE`), payments are a *separate* category (`PAYMENT_RECEIVED`) that never touches revenue (FR-11.7). A test asserts total revenue for a sale equals its price no matter how many payments landed. |
| **Cancelling a sale that already took payments** | Medium | Ambiguous by nature — money changed hands. v1 refuses to silently zero it: the cancel flags the collected payments for explicit refund handling (FR-11.11) rather than deleting them. Full refund workflow is v2. |
| **Attributing a credit company's debt to the customer** | Medium | A financed customer owes the store *nothing* — the company already paid in full. Enforced by FR-11.4's test asserting a financed sale creates no debt anywhere. |
| **Store-credit debt has no due date** | Low, by design | An open balance can sit forever without ever being "late." Accepted — it matches how these debts actually work. The debtor list orders by age of oldest open invoice (FR-11.10), so stale debts surface anyway. If owners ask for due dates, that's a v2 field, not a redesign. |
| **Credit company fails to pay immediately** | Low | The model assumes payment at sale time, per the owner. If a company ever pays late or partially, v1 has no way to represent it — the sale would simply be settled. Accepted; revisit only if it happens in practice (sales are labelled by company, so history is recoverable). |

### Deferred to v2 (schema anticipates them)
Inter-location transfers · customer returns/refunds · reservations · low-stock alerts · domain events · barcode label printing · **a single combined cross-currency bottom line (would require an FX rate — deliberately absent in v1)** · stored month-end snapshots · external accounting export (1C/QuickBooks) · full double-entry chart of accounts · **due dates / overdue tracking on store credit · customer credit limits · installment schedules · credit-company payout & commission tracking** · supplier accounts-payable (store's debts to suppliers).

**Pricing** (§4.5b decides where a price lives; these decide how one is *chosen*, which v1 leaves to the owner): **condition grades driving an automatic used price** (Grade A = 85% of new, …) · **depreciation curves or market price feeds** · **a floor/minimum price per unit** — only meaningful once Sellers can discount, which FR-4.5 does not allow · **scheduled or automatic markdowns** by age · **percentage- or formula-driven bulk markdowns** (FR-2.21 reprices many units in one call, but each unit's new price is stated — a single percentage across handsets in different conditions is the automated valuation §1.3 rejects, merely applied to several at once) · **lower-of-cost-or-market inventory write-downs** (v1 carries stock at cost, FR-2.17) · price lists per customer or channel · **any exchange rate, including one recorded on a som-paid trade-in** (§4.5b keeps the som figure inert precisely so that no rate is implied by dividing it into the booked cost).

**Tenancy & administration** (see §3.5 for the reasoning behind each): a **SuperAdmin-only admin portal** for tenant management — create, edit, change subscription plan · an **`/admin/*` API** · **billing / subscription metadata** on the tenant registry · **per-store custom roles** (DB-driven `TenantRole` rather than the fixed enum) · **API keys, feature flags, impersonation** · **welcome email** delivering the Owner's temporary password · a **server-side hard gate on `must_change_password`**. Note what is *not* deferred — it shipped in M1: public sign-up is **removed**, tenants are **SuperAdmin-provisioned**, identity is **split** between MasterDB (`users`) and each store (`employees`), and authorization runs on a **permission catalog**.
