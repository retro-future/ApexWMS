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
- **Money is fuzzy.** Devices are frequently bought in USD and sold in local currency. If the exchange rate isn't captured at the moment of the transaction, margin becomes unknowable after the fact.

### 1.2 Goals (MVP v1)

1. **Know every device.** Each physical handset is a first-class record, identified by IMEI, with a complete, immutable history from receipt to sale.
2. **Make stock changes auditable.** Every increase or decrease in stock is an entry in an append-only ledger. No exceptions, no silent edits.
3. **Work at scanner speed.** A storekeeper receiving 50 phones scans 50 barcodes without waiting for the UI. A seller scans one IMEI and sells it.
4. **Produce the paperwork.** Purchase Orders to suppliers, Sales Invoices to customers, Return-to-Supplier notes — as PDFs, with the tenant's own details on them.
5. **Isolate tenants completely.** One store's data is physically unreachable from another's.
6. **Record the money, not just the goods.** Every stock event that has a financial consequence — a purchase, a sale, a write-off, a supplier credit — writes a matching entry to a financial ledger. At month's end the owner gets a report on the state of the warehouse and store: what was bought, what was sold, what it cost, what's left on the shelves and what it's worth, and the margin earned.
7. **Sell on credit and installments, and know who owes what.** A phone can leave the store before it is paid for — on an open credit balance or a fixed installment schedule. The system tracks each customer's outstanding balance, what has been paid and when, what is still due and by when, and who is overdue.

### 1.3 Non-Goals (explicitly NOT in v1)

Naming these is the point of this section. If a request falls in this list, it is a v2 conversation, not a scope adjustment.

| Not in v1 | Why / when |
|---|---|
| **Inter-location transfers** | The schema will model `Location` and record it on every movement, so transfers are additive in v2. Deliberately deferred to keep v1 shippable. |
| **Payment *processing*** | The system **records** payments received (cash handed over, a transfer that landed) against an invoice or installment — that's core to credit tracking (§4.7). It does **not** *process* payments: no card rails, no payment gateway, no cash drawer, no till reconciliation. "Customer paid 2,000,000 today" is a recorded fact, not a transaction the system executes. |
| **Lending mechanics beyond a schedule** | v1 tracks balances, schedules, and lateness. It does **not** compute interest/APR (installments are interest-free, §4.7), charge automatic late fees, run credit scoring, or handle repossession/default workflows. Those are v2. |
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
| **Owner** | Runs the business, may own several stores. | Everything, plus reporting, plus user management and settings. |
| **Manager** | Runs one or more locations day to day. | All stock operations, documents, reporting. Cannot manage billing or delete the tenant. |
| **Storekeeper** | Physically handles goods. | Receiving, stock counts, write-offs. Should not see margins or set prices. |
| **Seller** | Sells to customers on the floor. | Look up stock, sell, generate invoice. Should not see acquisition cost. |

### 2.1 Permission matrix

| Operation | Owner | Manager | Storekeeper | Seller |
|---|:--:|:--:|:--:|:--:|
| Manage users & roles | ✅ | ❌ | ❌ | ❌ |
| Manage tenant settings (currency, letterhead) | ✅ | ❌ | ❌ | ❌ |
| Manage locations | ✅ | ✅ | ❌ | ❌ |
| Manage catalog (products, suppliers) | ✅ | ✅ | ❌ | ❌ |
| Create / send Purchase Order | ✅ | ✅ | ❌ | ❌ |
| Receive goods (scan-in) | ✅ | ✅ | ✅ | ❌ |
| **See acquisition cost / margin** | ✅ | ✅ | ❌ | ❌ |
| Sell / issue stock | ✅ | ✅ | ❌ | ✅ |
| Set / override sale price | ✅ | ✅ | ❌ | ❌ |
| Sell on credit / installment | ✅ | ✅ | ❌ | ✅ |
| Record a customer payment | ✅ | ✅ | ❌ | ✅ |
| Reverse a payment | ✅ | ✅ | ❌ | ❌ |
| Set customer credit limit / override it | ✅ | ✅¹ | ❌ | ❌ |
| View customer balances & AR aging | ✅ | ✅ | ❌ | ✅² |
| Return to supplier | ✅ | ✅ | ❌ | ❌ |
| Run stock count | ✅ | ✅ | ✅ | ❌ |
| Confirm count adjustments | ✅ | ✅ | ❌ | ❌ |
| Write off stock | ✅ | ✅ | ❌ | ❌ |
| Cancel a confirmed document | ✅ | ✅ | ❌ | ❌ |
| Look up stock / IMEI | ✅ | ✅ | ✅ | ✅ |
| Operational reporting | ✅ | ✅ | ❌ | ❌ |
| **Financial ledger & month-end report** | ✅ | ✅ | ❌ | ❌ |
| Set / update tenant exchange rate | ✅ | ❌ | ❌ | ❌ |

> **Note on cost visibility:** hiding acquisition cost from Storekeeper and Seller is a *response-shaping* requirement, not just a UI concern. The API must omit cost fields for those roles — not send them and rely on the frontend to hide them.
>
> ¹ A Manager can override a customer's credit limit at sale time; **setting** the limit is Owner-only.
> ² A Seller sees the balance and status of the customer they are serving (needed to take a payment), but AR aging *totals across all customers* — a business-health figure — are Owner/Manager only.

---

## 3. Multi-Tenancy Architecture — Database-per-Tenant

This is the single most consequential decision in this document, and the most expensive one to reverse. It is written down here with its costs, not only its benefits.

### 3.1 The model

- **One master database (MasterDB).** Holds `tenants`, `tenant_databases`, global `users`, and `memberships` (which user belongs to which tenant, with which role). This is the *only* database reachable without a tenant context. Login happens here.
- **One database per tenant.** Created at provisioning. Holds *all* business data: products, device units, movements, documents, locations, suppliers, customers. **There is no `tenant_id` column anywhere inside a tenant database** — isolation is physical, not a `WHERE` clause. A missing filter cannot leak another tenant's data because that data is not in the database you are connected to.

### 3.2 What this costs us

| Cost | Mitigation |
|---|---|
| **Migrations fan out.** Every schema change must run against the master DB *and* every tenant DB. With 200 tenants, that's 201 migration runs, and a failure halfway leaves the fleet on mixed schema versions. | A migration CLI (`apexwms migrate --all-tenants`) that runs tenant migrations idempotently, records per-tenant schema version, is resumable, and reports the fleet's version spread. Treat a partial migration as an expected state, not an emergency. |
| **Connection pools multiply.** Each tenant needs its own `AsyncEngine` and pool. 200 tenants × 5 connections = 1000 connections; Postgres will refuse. | A bounded **LRU engine registry**: at most *N* live engines (default 50), each with a small pool (default 5). Idle engines are disposed on eviction. Scale beyond that requires PgBouncer or a shift to shared-schema — a known ceiling, documented here so it isn't a surprise. |
| **Cross-tenant queries are hard.** "Total devices sold across all tenants" requires querying N databases. | Accepted. v1 has no cross-tenant reporting requirement. If one appears, it needs an analytics pipeline, not a JOIN. |
| **Provisioning is a real operation** that can fail halfway (DB created, migrations failed). | Provisioning is a state machine on the `tenants` row: `pending → provisioning → active | failed`. A tenant is not usable until `active`. Failed provisioning is retryable and idempotent. |

**Why we accept these costs:** physical isolation of retail inventory and customer data, per-tenant backup/restore, and the ability to hand a tenant their own database if they leave. For a system whose entire value is "the record is trustworthy," a bug class that can cross-contaminate tenants is worth engineering away structurally.

### 3.3 Request lifecycle

```
Request → JWT validated → tenant_id claim extracted
        → EngineRegistry.get(tenant_id)   [LRU cache; opens engine on miss]
        → AsyncSession bound to that engine   [Dishka REQUEST scope]
        → Use case executes; it never knows a tenant exists
        → Session committed/rolled back and closed by the DI container
```

The tenant is resolved **once**, at the edge. Nothing in the `domain` or `application` layer takes a tenant parameter. This is what makes the isolation structural rather than disciplinary.

### 3.4 Provisioning flow

1. Insert `tenants` row (`status = pending`).
2. `CREATE DATABASE apexwms_tenant_<uuid>` (autocommit, outside a transaction — Postgres requires this).
3. Record connection info in `tenant_databases`.
4. Run Alembic to head against the new DB.
5. Seed: a default `Location` ("Main Store"), the tenant's base currency, and the Owner membership for the signing-up user.
6. Mark `status = active`.

Steps 2–5 are idempotent and retryable.

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

**`Product`** — a catalog entry, not a physical thing. *"iPhone 15 Pro 256GB Titanium"*. Fields: `sku`, `name`, `brand`, `model`, `tracking_type`, `barcode` (EAN/UPC, for quantity items), `default_sale_price` (Money), `is_active`.

**`DeviceUnit`** — one physical handset. The heart of the system.
- `imei` — unique within the tenant, **validated with the Luhn check digit** at the boundary. A typo'd IMEI is worse than no IMEI.
- `imei2`, `serial_number` — optional (dual-SIM devices, non-phone serialized goods).
- `product_id` — what model it is.
- `status` ∈ `IN_STOCK | RESERVED | SOLD | RETURNED_TO_SUPPLIER | WRITTEN_OFF`.
- `location_id` — where it physically is (null once sold).
- `acquisition_cost` (Money) — what *this specific unit* cost. Two identical iPhones bought a month apart have different costs; average costing would destroy that.
- `condition` ∈ `NEW | REFURBISHED | USED`.
- Provenance: the receipt document that brought it in.

**`StockLevel`** — `(product_id, location_id) → quantity`, for `QUANTITY` products only. **A projection, never a source of truth** (see §4.3).

**`Location`** — a store, a stockroom, a warehouse. Present from day one even though transfers are v2, because retrofitting a location column onto a populated movements table is a migration nobody wants.

**`Supplier`** — name, contact, default currency.

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
| **`GoodsReceipt`** | ← supplier | Creates `DeviceUnit`s (serial) / increments levels (qty). `+` movements. |
| **`SalesInvoice`** | → customer | Marks units `SOLD` / decrements levels. `−` movements. |
| **`SupplierReturn`** | → supplier | Marks units `RETURNED_TO_SUPPLIER` / decrements levels. `−` movements. |
| **`StockCount`** | internal | Writes adjustment movements for every discrepancy found. `±` movements. |
| **`WriteOff`** | internal | Marks units `WRITTEN_OFF` / decrements levels. `−` movements. |

**Stock only moves on confirm.** A draft document is a shopping list; it touches nothing. This means a half-finished receipt sitting open on someone's screen has zero effect on the books.

**Cancel writes compensating movements**, never deletes. A cancelled sale is *two* sets of movements (the sale, and its reversal), not zero.

Documents carry a human-readable, per-tenant sequential number (`PO-2026-0001`, `INV-2026-0042`).

### 4.5 Money — UZS and USD

The system supports exactly **two currencies in v1: `UZS` (Uzbek som) and `USD`**. This is not a placeholder for "any currency" — it is the real, and typical, shape of an Uzbek phone business: **devices are bought from suppliers in USD and sold to customers in UZS.**

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

#### Base currency and frozen rates

Each **tenant has a `base_currency`** (default `UZS` — it is the currency the business reports, banks, and pays taxes in). Each **document captures, at confirm time**:
- the transaction currency (`UZS` or `USD`),
- the `USD→UZS` rate used,
- the resulting base-currency amount, stored alongside the original.

Because *both* the transaction amount and the base-currency amount are persisted, reports can be run in either currency without re-converting anything.

**Why the rate is frozen onto the document:** a phone is bought for $500 when the rate is 12,600, and sold for 7,000,000 so'm when the rate is 12,900. If we recompute historical documents against today's rate, **last quarter's margin changes every morning** — the books become unreproducible. Freezing the rate at confirm time means a confirmed document's numbers never move again, ever.

**Where the rate comes from (v1):** entered manually on the document, defaulting to a tenant-level "current rate" setting that an Owner updates. No automatic FX feed — that's v2. The rate is a required field at confirm time when the document's currency differs from the tenant's base currency.

**Margin is only meaningful in one currency.** A device costing $500 and selling for 7,000,000 UZS has no margin until both sides are expressed in the same currency at their respective frozen rates. All margin reporting is computed in the tenant's base currency, from the frozen base-currency amounts — never by converting on the fly.

**What this costs us:** every money field is two columns, every comparison must check currency, and cross-currency sums require an explicit conversion decision. Accepted — the alternative is a system that cannot state its own margin.

### 4.6 `FinancialTransaction` — the money ledger

The stock ledger (§4.3) answers *"what happened to the goods?"*. It cannot answer *"what happened to the money?"* — a receipt of 10 phones and a receipt of 10 phones at double the cost look different financially but similar in units. So the money gets its own append-only ledger, built on exactly the same principles as the stock ledger.

**Every confirmed document with a financial consequence writes one or more `FinancialTransaction` rows, in the same transaction as its stock movements.** The two ledgers move together or not at all.

```
id, occurred_at, txn_type, direction (+/-),
amount_minor, currency,                 -- as transacted (USD or UZS)
base_amount_minor, base_currency, rate, -- frozen at confirm time (§4.5)
category, document_type, document_id,
location_id, product_id (nullable), device_unit_id (nullable),
user_id, note
```

**Transaction categories** (the vocabulary the month-end report groups by):

| `txn_type` | Sign | Written when | Meaning |
|---|:--:|---|---|
| `PURCHASE` | − | Goods Receipt confirmed | Money owed to / spent on suppliers (inventory acquired). |
| `SALE_REVENUE` | + | Sales Invoice confirmed | Revenue earned from the customer. |
| `COGS` | − | Sales Invoice confirmed | Cost of the specific goods sold (see valuation below). |
| `WRITE_OFF_LOSS` | − | Write-Off confirmed | Book value of stock destroyed/lost. |
| `SUPPLIER_RETURN_CREDIT` | + | Supplier Return confirmed | Value credited back for goods sent to the supplier. |
| `COUNT_ADJUSTMENT` | ± | Stock Count confirmed | Value of surplus (+) or shortage (−) found in a physical count. |
| `PAYMENT_RECEIVED` | + | A customer payment is recorded (§4.7) | **Cash collected**, not revenue. Settles a receivable; does **not** re-book revenue. |

The same rules as the stock ledger apply, and for the same reasons:

1. **Nothing records money except by writing a transaction.** No code sets a running total directly.
2. **Transactions are immutable.** Cancelling a document writes **reversing transactions**, never deletes.
3. **Every transaction names its cause and author** and carries its frozen base-currency amount, so the report never re-converts history.

> **Revenue is not cash — and this is the trap credit introduces.** `SALE_REVENUE` (and its `COGS`) is booked in full **the moment a sale is confirmed**, whether or not a single som has been paid. That is *accrual* accounting, and it is what makes margin correct: the profit on a phone is earned when it is sold, not dribbled in as the customer pays. `PAYMENT_RECEIVED` is a separate, *cash* dimension — it settles the receivable the sale created. **A payment must never write `SALE_REVENUE`**, or every installment would inflate revenue and the books would double-count. The month-end report (§5.10) therefore presents two distinct views: an **accrual view** (revenue, COGS, margin — unchanged by credit) and a **receivables/cash view** (who owes what, what was collected).

#### Inventory valuation — how COGS and on-hand value are costed

This is the one genuinely new decision the financial ledger forces, and it differs by tracking type:

- **Serialized phones → specific identification.** Every `DeviceUnit` carries *its own* `acquisition_cost`. When that exact unit sells, its COGS is its own cost — exact, no estimation. This is the payoff of serializing: valuation is not a model, it's a fact.
- **Quantity accessories → weighted-average cost.** A box of cases has no per-unit identity, so on-hand value is `average_unit_cost × quantity`, where the average is maintained from the purchase ledger. When accessory prices move, the average moves; COGS uses the average at time of sale. Simple, standard, and computable from the ledger.

**On-hand inventory value** at any instant = (Σ `acquisition_cost` of every `IN_STOCK` device unit) + (Σ `avg_cost × qty` for every accessory stock level), all in the tenant's base currency at each item's frozen acquisition rate.

**What this buys us:** the month-end report (§5.10) is a *grouping query over one ledger*, and closing inventory value can be independently recomputed from stock and cross-checked. Money and goods reconcile by construction.

**What this costs us:** a second ledger write on every confirm, a valuation rule to maintain for accessories, and a reconciliation check to run. Accepted — without it, "how did the store do this month?" has no answer.

### 4.7 Credit, Installments & Receivables

A sale can leave the store before it is paid for. This section models *who owes what and how it gets paid down*, and it rests on one hard rule already stated in §4.6: **the goods and the revenue leave at the sale; the money is a separate, later stream.**

#### The customer stops being anemic

In §4.2, `Customer` was "name + phone, deliberately anemic." Credit changes that: a customer is now a **party the store holds a balance against**. It gains an **outstanding balance** (a projection, never edited directly) and, optionally, a **credit limit** the Owner can set. It is still not a CRM — no marketing, no history of interactions — but it is now a debtor.

#### Payment terms on a sale

Every `SalesInvoice` gains a `payment_type`:

| `payment_type` | Meaning | Receivable created on confirm |
|---|---|---|
| `PAID_IN_FULL` | Paid on the spot. The existing v1 flow, unchanged. | None. |
| `CREDIT` | Open balance, no fixed schedule. Pay it down whenever. | `total − down_payment` |
| `INSTALLMENT` | Fixed schedule of dated instalments. | `total − down_payment`, split across the schedule |

- **Interest-free (decided).** The installment total **equals** the cash price. There is no markup, no APR, no amortization math. The financed amount is simply `price − down_payment`, divided across N installments. *(If a shop wants to charge more for installments, it sets a higher line price at sale time — the system does not compute interest.)*
- **Optional down payment (decided).** At confirm, the seller may record an initial payment of zero or more. The remainder is what's financed.
- **The phone still leaves at confirm.** A `CREDIT` or `INSTALLMENT` sale marks its `DeviceUnit`s `SOLD` and writes the `−` stock movement and full `SALE_REVENUE`/`COGS` exactly like a paid sale. The customer walks out with the device; the store carries the debt. **This is the entire point of credit and the reason revenue must be accrual, not cash.**

#### Entities

**`InstallmentPlan`** — belongs to one `INSTALLMENT` invoice. Holds `financed_amount`, `down_payment`, `installment_count`, `start_date`, `interval` (monthly), and its `schedule`.

**`Installment`** — one scheduled row of a plan: `sequence`, `due_date`, `amount_due`, `amount_paid`, and a derived `status` ∈ `PENDING | PARTIAL | PAID | OVERDUE`. Status is computed, not stored as truth — `OVERDUE` is simply `due_date < today AND amount_paid < amount_due`, evaluated in the tenant's timezone.

**`Payment`** — an **append-only** record of money received. `occurred_at`, `amount` (Money), `method` (cash / transfer / card — a *label*, not a processed transaction), `customer_id`, `invoice_id`, `user_id`, `note`. A payment is **allocated** against the invoice's balance — for an installment plan, oldest-due-first by default, with the option to target a specific installment. Confirming a payment writes a `PAYMENT_RECEIVED` financial transaction (§4.6) and reduces the outstanding balance. **Payments are never edited; a mistaken payment is reversed by a compensating negative payment**, same as every other ledger in this system.

#### Balances are projections, not stored counters

The single source of truth is the append-only pair *(receivable opened by the sale) + (payments applied)*. Every "how much is owed" number is derived:

```
customer_outstanding = Σ(financed amounts of their credit/installment sales)
                     − Σ(their payments)
invoice_outstanding  = invoice_financed − Σ(payments allocated to it)
installment_status   = f(due_date, amount_due, amount_paid, today@tenant_tz)
```

No code ever assigns `customer.balance = X`. This is the same discipline as the stock and money ledgers, for the same reason: a balance you can recompute from an immutable history is a balance you can trust and audit. A `verify-balances` check (sibling of `verify-projections`) recomputes every outstanding figure from the ledgers and asserts it against any cached projection.

**What this costs us:** a third thing to reconcile, an allocation rule for partial payments, and the accrual-vs-cash discipline that makes revenue and collections two different questions. **What it buys us:** an exact, auditable answer to "who owes us money, how much, and since when" — which is the feature that was asked for.

---

## 5. Functional Requirements

Each requirement is phrased as *actor → action → observable outcome*, so it converts directly into a test case.

### 5.1 Authentication & Tenancy

- **FR-1.1** An anonymous visitor can sign up, creating a tenant and becoming its Owner. The tenant is unusable until provisioning reaches `active`.
- **FR-1.2** A user authenticates with email + password and receives an access token (short-lived) and a refresh token (long-lived). Passwords are hashed with argon2id.
- **FR-1.3** A user belonging to multiple tenants selects one at login; the resulting token carries exactly one `tenant_id`.
- **FR-1.4** A request with a token for tenant A can never read or write data in tenant B. *(Test: issue a token for A, attempt every endpoint, assert no row from B is reachable.)*
- **FR-1.5** An Owner can invite a user by email and assign a role; the invitee sets their password via a signed, single-use, expiring link.
- **FR-1.6** A request whose role lacks permission for an operation receives `403`, and the operation has no side effect.
- **FR-1.7** Responses omit `acquisition_cost` and margin fields entirely for Storekeeper and Seller roles.

### 5.2 Catalog & Reference Data

- **FR-2.1** A Manager can create a product with a `tracking_type`; the type is **immutable** once any stock movement references the product.
- **FR-2.2** A Manager can create locations, suppliers, and customers.
- **FR-2.3** A product with `tracking_type = QUANTITY` may carry a barcode (EAN/UPC), unique within the tenant.
- **FR-2.4** Deactivating a product prevents new movements against it but preserves all history.

### 5.2b Currency (UZS / USD)

- **FR-2.5** A tenant has a `base_currency`, set at signup, defaulting to `UZS`. Only `UZS` and `USD` are accepted.
- **FR-2.6** An Owner maintains a tenant-level current `USD→UZS` rate, used as the default on new documents.
- **FR-2.7** Any document whose transaction currency differs from the tenant's base currency **cannot be confirmed without an exchange rate**. Confirmation is rejected, not defaulted to 1.
- **FR-2.8** On confirm, a document persists its transaction amount, the rate used, **and** the resulting base-currency amount. *(Test: confirm a USD purchase, change the tenant's current rate, re-read the document — every figure on it is unchanged.)*
- **FR-2.9** Amounts are stored in minor units with **per-currency exponents: USD = 2, UZS = 0**. *(Test: `Money(1000, "UZS")` renders as `1 000 so'm`; `Money(1000, "USD")` renders as `$10.00`.)*
- **FR-2.10** Adding or comparing two `Money` values of different currencies raises a domain error. There is no implicit conversion anywhere in the domain.
- **FR-2.11** Margin in any report is computed **from the frozen base-currency amounts**, never by converting historical amounts at the current rate.

### 5.3 Inbound — Purchase Orders & Receiving

- **FR-3.1** A Manager creates a Purchase Order: supplier, currency, and lines of `(product, quantity, unit_cost)`. It is a `DRAFT`.
- **FR-3.2** Confirming a PO fixes its numbers and generates a PDF. **It does not change stock.**
- **FR-3.3** A Storekeeper creates a Goods Receipt, optionally from a PO (which pre-fills its lines).
- **FR-3.4** For a `SERIAL` line, the Storekeeper scans one IMEI per unit. The system validates the Luhn check digit and rejects malformed IMEIs **at scan time**, not on submit.
- **FR-3.5** Scanning an IMEI that already exists in this tenant is rejected immediately with a message naming the existing unit's status and location. *(A duplicate IMEI is either a scanning error or a stolen-goods red flag. Never silently accept it.)*
- **FR-3.6** For a `QUANTITY` line, the Storekeeper enters a count.
- **FR-3.7** Confirming a Goods Receipt creates the `DeviceUnit`s with their per-unit acquisition cost, increments quantity levels, and writes one `+` movement per line. Units enter as `IN_STOCK` at the receipt's location.
- **FR-3.8** A receipt whose serial line has fewer scanned IMEIs than its declared quantity cannot be confirmed.
- **FR-3.9** Receiving against a PO records the linkage, and the PO reports its received-vs-ordered state (`pending`, `partial`, `complete`).

### 5.4 Outbound — Sales & Issue

- **FR-4.1** A Seller creates a Sales Invoice: customer (optional), location, currency.
- **FR-4.2** The Seller scans an IMEI; the system resolves it to a `DeviceUnit` and adds it as a line at the product's default sale price.
- **FR-4.3** Scanning an IMEI that is not `IN_STOCK` is rejected, stating the actual status. *(You cannot sell a phone that is already sold.)*
- **FR-4.4** Scanning an IMEI held at a different location than the invoice's is rejected.
- **FR-4.5** Only Owner/Manager may override a line's price. A Seller's invoice uses the catalog price.
- **FR-4.6** Confirming the invoice marks each unit `SOLD`, decrements quantity lines, writes one `−` movement per line, freezes the exchange rate, and generates the invoice PDF.
- **FR-4.7** Confirming an invoice whose line quantity exceeds available stock is rejected atomically — no partial fulfilment.
- **FR-4.8** Cancelling a confirmed invoice returns the units to `IN_STOCK` **by writing compensating `+` movements**. The original movements remain.

### 5.5 Returns to Supplier

- **FR-5.1** A Manager creates a Supplier Return, scans the IMEIs of units being sent back, and states a reason (defective, unsold, wrong item).
- **FR-5.2** Only units currently `IN_STOCK` may be added.
- **FR-5.3** Confirming marks units `RETURNED_TO_SUPPLIER`, writes `−` movements, and generates the Return-to-Supplier PDF.

### 5.6 Stock Counts & Write-Offs

- **FR-6.1** A Storekeeper opens a Stock Count for a location; the system snapshots expected stock at that moment.
- **FR-6.2** The Storekeeper scans every IMEI physically present and enters counts for quantity products.
- **FR-6.3** On close, the system reports three lists: **matched**, **missing** (expected, not scanned), and **unexpected** (scanned, not expected — including IMEIs unknown to the system entirely).
- **FR-6.4** Only Owner/Manager may confirm the count's adjustments. Confirming writes `±` adjustment movements bringing the system in line with reality.
- **FR-6.5** A Manager can write off units (damage, loss, theft) with a mandatory reason, producing `−` movements. Units become `WRITTEN_OFF`.

### 5.7 Scanning & Lookup

- **FR-7.1** `GET /scan/lookup?code=<x>` resolves a scanned string to *either* a `DeviceUnit` (by IMEI) *or* a `Product` (by barcode/SKU), and **states which kind it found**. One call — the operator's scanner does not know what it just scanned.
- **FR-7.2** The lookup returns, for a device: model, status, location, and (role permitting) cost. This is the "customer walks in with a phone" screen.
- **FR-7.3** Lookup responds within **200ms at p95**. A storekeeper scanning 50 units must never wait on the system.
- **FR-7.4** An unrecognized code returns a clear "not found" — not a 500, not an empty 200.

### 5.8 Documents (PDF)

- **FR-8.1** Confirming a PO, Sales Invoice, or Supplier Return generates a PDF carrying the tenant's name, address, and logo.
- **FR-8.2** Invoice lines show the IMEI for serialized items. *(This is the customer's proof of which handset they bought.)*
- **FR-8.3** A document's PDF is **immutable once confirmed**; regenerating it produces byte-identical content. Cancellation overlays a "CANCELLED" mark rather than deleting the file.
- **FR-8.4** Documents show amounts in the transaction currency, with the base-currency equivalent and the frozen rate in the footer where they differ.

### 5.9 Reporting

- **FR-9.1** **Stock on hand** — by location, by product, by brand. Includes total cost value (Owner/Manager only).
- **FR-9.2** **IMEI trace** — given an IMEI, the complete chronological movement history: received on which document, from which supplier, at what cost, sold on which invoice, to whom, for how much, by which user.
- **FR-9.3** **Sales summary** — over a date range, by location: units sold, revenue, cost of goods, margin.
- **FR-9.4** **Ageing** — units `IN_STOCK` for longer than N days. *(Dead stock is the phone retailer's core financial risk.)*
- **FR-9.5** **Movement log** — the raw ledger, filterable by product, location, user, date, movement type.

### 5.10 Financial Ledger & Month-End Report

- **FR-10.1** Every confirmed document that has a financial consequence writes its `FinancialTransaction` row(s) **in the same database transaction** as its stock movements. A confirm either records both goods and money, or neither.
- **FR-10.2** Cancelling a confirmed document writes **reversing** financial transactions; the originals remain. *(Test: confirm a sale, cancel it, and assert the net financial effect for that document is zero while both transactions are visible in the ledger.)*
- **FR-10.3** An Owner/Manager can pull a **financial transaction log** over any date range, filterable by category, location, and document — the raw money ledger, mirroring the movement log.
- **FR-10.4** An Owner/Manager can run a **Month-End Report** for a given month and location (or consolidated across all locations), reported in the tenant's base currency.
- **FR-10.5** The Month-End Report presents, for the period:
  - **Opening inventory value** (= previous period's closing).
  - **Purchases** — value of goods received.
  - **COGS** — cost of goods sold (specific-identification for phones, weighted-average for accessories, per §4.6).
  - **Sales revenue** and **gross margin** (revenue − COGS), with margin % — **accrual, i.e. all sales confirmed in the period, paid or not.**
  - **Write-offs** and **count adjustments** — value lost or corrected.
  - **Supplier-return credits**.
  - **Closing inventory value** (= opening + purchases − COGS − write-offs − returns ± adjustments).
  - **Receivables movement** (cash view): opening receivables, + credit/installment sales booked, − payments collected, = **closing receivables outstanding**.
  - **Cash collected** in the period (Σ `PAYMENT_RECEIVED`) — distinct from revenue, so the owner sees the gap between what was earned and what actually came in.
- **FR-10.6** The report breaks the closing inventory figure down **by location** — the warehouse's stock value and each store's stock value shown separately, then totalled — so the owner sees where the value physically sits.
- **FR-10.7** The report's **closing inventory value must equal the independently-computed on-hand value** (Σ cost of `IN_STOCK` units + Σ accessory average-cost value) at period end. A mismatch is surfaced as a reconciliation error, not silently reconciled. *(This is the money-side analogue of `verify-projections`.)*
- **FR-10.7b** The report's **closing receivables must equal the sum of every customer's outstanding balance** (§4.7) at period end — the `verify-balances` check, run as part of the report.
- **FR-10.8** All period boundaries are computed in the **tenant's timezone**: a month runs `[00:00 on the 1st, 00:00 on the 1st of next month)` in that timezone, so a sale at 23:30 on the 31st lands in the correct month.
- **FR-10.9** The Month-End Report is exportable as a PDF carrying the tenant's letterhead and the period.
- **FR-10.10** Because every figure derives from the frozen base-currency amounts on the ledger (§4.5), **re-running a past month's report always yields identical numbers**, regardless of today's exchange rate. *(Test: generate March's report, change the current USD→UZS rate, regenerate March — byte-identical figures.)*

> **On "opening = previous closing":** in v1 both are computed live from the ledger since inception — the ledger is complete and immutable, so no stored month-end snapshot is required for correctness. Snapshotting closing balances is a v2 performance optimization (see risks), not a correctness need.

### 5.11 Credit, Installments & Payments

- **FR-11.1** When creating a Sales Invoice, a Seller chooses a `payment_type` of `PAID_IN_FULL`, `CREDIT`, or `INSTALLMENT`. `PAID_IN_FULL` behaves exactly as the existing outbound flow.
- **FR-11.2** For `CREDIT` or `INSTALLMENT`, the Seller may record an optional **down payment** (≥ 0, ≤ total). The financed amount is `total − down_payment`.
- **FR-11.3** For `INSTALLMENT`, the Seller specifies the number of installments and a start date; the system generates an equal-split schedule of dated installments whose amounts sum **exactly** to the financed amount (the rounding remainder lands on the final installment, never lost). *(Test: a 10,000,003-som balance over 3 installments produces rows summing to exactly 10,000,003.)*
- **FR-11.4** The installment total equals the cash price — **no interest or markup is added by the system** (FR references §4.7).
- **FR-11.5** Confirming a credit/installment sale marks the device(s) `SOLD`, writes the `−` stock movement and full `SALE_REVENUE`/`COGS`, records any down payment as a `Payment`, and opens a receivable for the financed amount — **all in one transaction.**
- **FR-11.6** A user with the right role can **record a payment** against an outstanding invoice: an amount, a date, and a method label (cash/transfer/card). The payment reduces the invoice balance and, for installment plans, is allocated oldest-due-first unless a specific installment is targeted.
- **FR-11.7** A payment cannot exceed the invoice's outstanding balance. Overpayment is rejected. *(No customer credit balances in v1.)*
- **FR-11.8** Recording a payment writes a `PAYMENT_RECEIVED` financial transaction and **never** a `SALE_REVENUE` one. *(Test: sell on installment, pay all installments, assert total `SALE_REVENUE` equals the sale price exactly once — not once per payment.)*
- **FR-11.9** A mistaken payment is reversed by recording a compensating negative payment; the original stays in the ledger.
- **FR-11.10** Any user (cost-visibility aside) can view a **customer's account**: total sold on credit, total paid, current outstanding balance, and the list of open invoices/installments with due dates and statuses.
- **FR-11.11** An installment is `OVERDUE` when `due_date < today` (tenant timezone) and it is not fully paid. This is **computed at read time**, so an installment becomes overdue by the passage of time with no batch job required.
- **FR-11.12** An Owner/Manager can run an **Accounts-Receivable / aging report**: every customer with an outstanding balance, bucketed by how overdue (current, 1–30, 31–60, 60+ days), with totals. *(This is the "who owes what" answer.)*
- **FR-11.13** Cancelling a credit/installment invoice reverses the stock, revenue, and COGS as in FR-4.8, **and** voids the receivable and its remaining schedule. Payments already received against it are surfaced for refund handling but not silently deleted. *(A sale with money already collected cannot be cancelled without an explicit resolution — the system flags it rather than losing the payment record.)*
- **FR-11.14** An Owner can set an optional **credit limit** per customer; a new credit/installment sale that would push the customer's outstanding balance over the limit requires Owner/Manager override.

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
│   │   │   ├── application/     # use cases, ports (protocols), DTOs
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
- **`application/`** — use cases (one class, one `execute()` method, one business operation: `ReceiveGoods`, `SellDevices`, `ConfirmStockCount`). It defines **ports** — `Protocol` classes describing what it needs (`DeviceUnitRepository`, `UnitOfWork`, `PdfRenderer`, `Clock`). It depends on `domain` only.
- **`infrastructure/`** — the implementations. SQLAlchemy models and repositories, the tenant engine registry, the JWT service, the PDF renderer. It *implements* the ports that `application` declared. The arrow points inward: `application` never imports from `infrastructure`.
- **`presentation/`** — FastAPI routers, request/response schemas, exception handlers, Dishka wiring. Thin: parse, authorize, call a use case, serialize.

**Why the ports live in `application`, not `infrastructure`:** this is the inversion in "dependency inversion," and it's the bit people get backwards. The use case *declares its needs*; infrastructure *satisfies them*. Consequence: `application` can be tested with in-memory fakes and no database at all.

### 7.4 A use case end to end: `ReceiveGoods`

Tracing one operation through every layer, because this is the pattern every other operation copies:

1. **`presentation/routers/receipts.py`** — `POST /receipts/{id}/confirm`. Validates the request schema, checks the role, and asks Dishka for a `ReceiveGoods` instance.
2. **`application/use_cases/receive_goods.py`** — `ReceiveGoods.execute(receipt_id, user_id)`. Depends only on ports: `GoodsReceiptRepository`, `DeviceUnitRepository`, `StockMovementRepository`, `UnitOfWork`, `Clock`. It loads the receipt, asks the domain to validate it, creates the `DeviceUnit`s, writes the movements, and commits.
3. **`domain/entities/goods_receipt.py`** — `GoodsReceipt.confirm()` enforces the invariants: not already confirmed; every serial line has exactly as many scanned IMEIs as its declared quantity; no IMEI appears twice. **These rules live in the domain and are testable with no I/O whatsoever.**
4. **`infrastructure/persistence/`** — the SQLAlchemy repositories that actually satisfy those ports, and the `UnitOfWork` that wraps it all in one transaction against *this tenant's* database.

The use case does not know a tenant exists. It does not know Postgres exists. That is the entire point.

### 7.5 Dishka scopes

| Scope | Provides |
|---|---|
| `APP` | Settings, the MasterDB engine, the tenant `EngineRegistry`, the JWT service, the PDF renderer. |
| `REQUEST` | The authenticated user, the resolved tenant, that tenant's `AsyncSession`, the `UnitOfWork`, repositories, and every use case. |

The tenant-scoped `AsyncSession` is the linchpin: it's provided at `REQUEST` scope by pulling the tenant from the validated JWT and asking the registry for that tenant's engine. Everything downstream — every repository, every use case — is automatically bound to the right database without a single line of code below `presentation` mentioning tenancy.

### 7.6 On DDD (a note on how this will be taught)

This document uses Clean Architecture, which is a *structural* discipline: where code lives and which way imports point. DDD is a *modelling* discipline: how you find the right objects in the first place. They're complementary, not the same thing, and you do not need to understand DDD to build v1.

DDD concepts will be introduced **against real code, at the moment the code needs them**, not up front:

- **Value objects** — arrive immediately, in `IMEI` and `Money`. The simplest DDD idea and the one with the fastest payoff: an `IMEI` that cannot exist in an invalid state deletes an entire class of bugs.
- **Entities & identity** — `DeviceUnit` is the obvious teaching case: two handsets of the same model are *not* equal, even with identical attributes, because identity is not attributes.
- **Aggregates & invariants** — when we build `GoodsReceipt.confirm()`. A receipt and its lines are one consistency boundary: you cannot confirm a receipt whose lines don't add up, so they must be loaded, validated, and saved as a unit. This is where "aggregate" stops being jargon and starts being obvious. `InstallmentPlan` (a plan and its installments, whose amounts must always sum to the financed total) is the second worked example, at M5b.
- **Domain events** — deferred. Not needed in v1. When a stock movement needs to trigger a low-stock alert, that's the moment to introduce them, and not before.

The rule: no DDD concept enters this codebase before there's a concrete problem in *this* system that it solves.

---

## 8. API Surface

All routes are prefixed `/api/v1`. All except auth require a bearer token carrying a `tenant_id`.

### Auth & Tenancy
| Method | Path | Role |
|---|---|---|
| `POST` | `/auth/signup` | anon (creates tenant + owner) |
| `POST` | `/auth/login` | anon |
| `POST` | `/auth/refresh` | anon (valid refresh token) |
| `GET` | `/auth/me` | any |
| `GET` / `POST` | `/users`, `/users/invite` | Owner |
| `PATCH` | `/users/{id}/role` | Owner |

### Catalog
| Method | Path | Role |
|---|---|---|
| `GET` / `POST` | `/products` | read: any · write: Manager |
| `GET` / `PATCH` | `/products/{id}` | read: any · write: Manager |
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
| `POST` | `/receipts/{id}/scan` | Storekeeper+ (append one IMEI) |
| `DELETE` | `/receipts/{id}/scan/{imei}` | Storekeeper+ (undo a scan) |
| `POST` | `/receipts/{id}/confirm` | Storekeeper+ |

### Outbound
| Method | Path | Role |
|---|---|---|
| `GET` / `POST` | `/invoices` | Seller+ |
| `POST` | `/invoices/{id}/scan` | Seller+ |
| `PATCH` | `/invoices/{id}/lines/{line_id}` | Manager (price override) |
| `POST` | `/invoices/{id}/confirm` | Seller+ (body carries `payment_type`, down payment, installment terms) |
| `POST` | `/invoices/{id}/cancel` | Manager |
| `GET` | `/invoices/{id}/pdf` | Seller+ |

### Credit, Installments & Payments
| Method | Path | Role |
|---|---|---|
| `GET` | `/invoices/{id}/schedule` | Seller+ (installment schedule + status) |
| `POST` | `/invoices/{id}/payments` | Seller+ (record a payment) |
| `POST` | `/payments/{id}/reverse` | Manager |
| `GET` | `/customers/{id}/account` | Seller+ (balance, invoices, schedule) |
| `PUT` | `/customers/{id}/credit-limit` | Owner (Manager may override at sale) |
| `GET` | `/reports/receivables?as_of=&bucket=` | Manager (AR aging) |

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
| `GET` | `/devices/{imei}/history` | any (cost hidden by role) |
| `GET` | `/reports/stock-on-hand` | Manager |
| `GET` | `/reports/sales-summary` | Manager |
| `GET` | `/reports/ageing` | Manager |
| `GET` | `/reports/movements` | Manager |
| `GET` | `/reports/financial-ledger?from=&to=&category=&location=` | Manager |
| `GET` | `/reports/month-end?year=&month=&location=` | Manager |
| `GET` | `/reports/month-end/pdf?year=&month=&location=` | Manager |
| `GET` / `PUT` | `/settings/exchange-rate` | read: Manager · write: Owner |

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
- Revenue is booked once per sale, never per payment — total `SALE_REVENUE` for a sale equals its price regardless of how many installments were paid.
- A fully-paid credit sale nets `customer_outstanding = 0`; a cancelled-with-payment sale is flagged, never silently zeroed.
- Installment schedule amounts sum exactly to the financed amount (no rounding leak).

---

## 10. Delivery Plan

Each milestone is independently demoable.

| # | Milestone | Delivers |
|---|---|---|
| **M0** | **Bootstrap** | uv workspace, FastAPI + Dishka skeleton, the four-layer structure, docker-compose (Postgres), CI. Demo: `/health` responds. |
| **M1** | **Tenancy & Auth** | MasterDB, tenant provisioning, engine registry, migration fan-out CLI, JWT, roles. Demo: sign up two tenants; prove tenant A cannot see tenant B. |
| **M2** | **Catalog** | Products (both tracking types), locations, suppliers, customers. Demo: build a catalog. |
| **M3** | **The ledgers** | `StockMovement` **and** `FinancialTransaction`, projections, valuation rules, `verify-projections` + financial reconciliation. Demo: a confirm writes both a stock movement and its money entry, and both reconcile. |
| **M4** | **Inbound** | PO → Goods Receipt, IMEI scan-in, Luhn + duplicate rejection, `PURCHASE` financial entries. Demo: **scan 10 phones into stock with a real scanner.** |
| **M5** | **Outbound** | Sales Invoice, scan-to-sell, confirm, cancel-with-compensation, `SALE_REVENUE` + `COGS` entries. Demo: scan a phone, sell it, cancel, watch both goods and money reverse. |
| **M5b** | **Credit, installments & receivables** | `payment_type` on sales, down payment, installment schedules, `Payment` ledger, per-customer balance, `verify-balances`, AR aging report. Demo: **sell a phone on a 3-month plan, record two payments, show the balance and the one installment now overdue.** |
| **M6** | **Counts, write-offs, supplier returns** | Full discrepancy → adjustment flow with `WRITE_OFF_LOSS` / `COUNT_ADJUSTMENT` / `SUPPLIER_RETURN_CREDIT` entries. Demo: hide a phone, run a count, watch the system find it missing and book the loss. |
| **M7** | **Documents** | PDF generation for PO, Invoice, Supplier Return. Demo: print a real invoice with an IMEI on it. |
| **M8** | **Reporting** | Stock on hand, IMEI trace, sales summary, ageing, financial ledger. Demo: trace one IMEI's entire life. |
| **M9** | **Month-End Report** | Period close in tenant timezone, per-location inventory value, opening→closing reconciliation, margin, **receivables movement + cash collected**, PDF export. Demo: **run last month's report for the warehouse and the store, reconcile closing value against on-hand, and closing receivables against customer balances.** |

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
| **Month boundaries & timezone** | Medium | Period math runs in the tenant's timezone (FR-10.8), so a tenant timezone setting must land in M1. Without it, a late-night sale slips into the wrong month and the report is quietly wrong. |
| **Month-end report performance** at scale | Low (v1) | v1 computes opening/closing live from the full ledger — fine at MVP volumes. If a tenant's ledger grows large, add stored month-end snapshots (opening = prior stored closing) as a v2 optimization; correctness is unaffected either way. |
| **PDF library choice** | Low | **Open question.** WeasyPrint (HTML/CSS templates — far easier to iterate on, but a heavier system dependency: cairo/pango) vs ReportLab (pure Python, no system deps, but layouts are written in code). Leaning WeasyPrint; decide at M7. |
| **Python 3.14 wheel availability** across the dependency set | Medium | asyncpg 0.31+ ships cp314 wheels. **Verify the full set at M0** — psycopg3 is the drop-in fallback driver, and SQLAlchemy's async layer needs greenlet, which must also have 3.14 wheels. |
| **Currency exponent mismatch (USD=2, UZS=0)** | **High** | The classic 100× corruption bug. Mitigated structurally: exponent lives on the `Money` value object, never in call sites; a bare int is not money. Round-trip tests for both currencies land in M0, before any money is persisted. |
| **UZS integer overflow** | Medium | `BIGINT` everywhere for `amount_minor` — a 32-bit int overflows at ~175 phones' worth of som. Enforced at the schema level. |
| **Exchange-rate source** | Low | v1: entered manually per document, defaulting to a tenant-level current rate an Owner maintains. Automatic FX feed is v2. |
| **Double-counting revenue as cash** | **High** | The signature bug of naive credit systems. Mitigated structurally: revenue is booked once at sale (`SALE_REVENUE`), payments are a *separate* category (`PAYMENT_RECEIVED`) that never touches revenue (FR-11.8). A test asserts total revenue for a sale equals its price no matter how many payments landed. |
| **Cancelling a sale that already took payments** | Medium | Ambiguous by nature — money changed hands. v1 refuses to silently zero it: the cancel flags the collected payments for explicit refund handling (FR-11.13) rather than deleting them. Full refund/repossession workflow is v2. |
| **Payment-in-a-currency-≠-sale-currency** | Medium | **Open question for M5b.** A USD sale paid in UZS (or vice-versa) needs an allocation rule and a rate at payment time. Simplest v1 stance: a payment must be in the invoice's currency; cross-currency settlement is v2. Confirm before M5b. |
| **Installment rounding leak** | Low | Equal-split schedules must sum to the financed amount to the minor unit; the remainder lands on the final installment (FR-11.3), asserted by test. |

### Deferred to v2 (schema anticipates them)
Inter-location transfers · customer returns/refunds · reservations · low-stock alerts · domain events · barcode label printing · automatic FX rates · stored month-end snapshots · external accounting export (1C/QuickBooks) · full double-entry chart of accounts · **automatic late fees / penalties · credit scoring · repossession & default workflow · cross-currency payment settlement · supplier accounts-payable (store's debts to suppliers)**.
