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
| Manage tenant settings (timezone, letterhead) | ✅ | ❌ | ❌ | ❌ |
| Manage locations | ✅ | ✅ | ❌ | ❌ |
| Manage catalog (products, suppliers) | ✅ | ✅ | ❌ | ❌ |
| Create / send Purchase Order | ✅ | ✅ | ❌ | ❌ |
| Receive goods (scan-in) | ✅ | ✅ | ✅ | ❌ |
| **See acquisition cost / margin** | ✅ | ✅ | ❌ | ❌ |
| Sell / issue stock | ✅ | ✅ | ❌ | ✅ |
| Set / override sale price | ✅ | ✅ | ❌ | ❌ |
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
5. Seed: a default `Location` ("Main Store"), the tenant's timezone, and the Owner membership for the signing-up user.
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

**`Supplier`** — name, contact. *(No currency field — currency belongs to products, §4.5, not to suppliers or documents.)*

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
| **`GoodsReceipt`** | ← supplier | Creates `DeviceUnit`s (serial) / increments levels (qty). `+` movements. |
| **`SalesInvoice`** | → customer | Marks units `SOLD` / decrements levels. `−` movements. |
| **`SupplierReturn`** | → supplier | Marks units `RETURNED_TO_SUPPLIER` / decrements levels. `−` movements. |
| **`StockCount`** | internal | Writes adjustment movements for every discrepancy found. `±` movements. |
| **`WriteOff`** | internal | Marks units `WRITTEN_OFF` / decrements levels. `−` movements. |

**Stock only moves on confirm.** A draft document is a shopping list; it touches nothing. This means a half-finished receipt sitting open on someone's screen has zero effect on the books.

**Cancel writes compensating movements**, never deletes. A cancelled sale is *two* sets of movements (the sale, and its reversal), not zero.

Documents carry a human-readable, per-tenant sequential number (`PO-2026-0001`, `INV-2026-0042`).

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

- **Phones are bought *and* sold in USD.**
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

- **FR-1.1** An anonymous visitor can sign up, creating a tenant and becoming its Owner. The tenant is unusable until provisioning reaches `active`.
- **FR-1.2** A user authenticates with email + password and receives an access token (short-lived) and a refresh token (long-lived). Passwords are hashed with argon2id.
- **FR-1.3** A user belonging to multiple tenants selects one at login; the resulting token carries exactly one `tenant_id`.
- **FR-1.4** A request with a token for tenant A can never read or write data in tenant B. *(Test: issue a token for A, attempt every endpoint, assert no row from B is reachable.)*
- **FR-1.5** An Owner can invite a user by email and assign a role; the invitee sets their password via a signed, single-use, expiring link.
- **FR-1.6** A request whose role lacks permission for an operation receives `403`, and the operation has no side effect.
- **FR-1.7** Responses omit `acquisition_cost` and margin fields entirely for Storekeeper and Seller roles.

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

### 5.3 Inbound — Purchase Orders & Receiving

- **FR-3.1** A Manager creates a Purchase Order: supplier and lines of `(product, quantity, unit_cost)` — each line's currency comes from its product (FR-2.7); the document has no currency of its own. It is a `DRAFT`.
- **FR-3.2** Confirming a PO fixes its numbers and generates a PDF. **It does not change stock.**
- **FR-3.3** A Storekeeper creates a Goods Receipt, optionally from a PO (which pre-fills its lines).
- **FR-3.4** For a `SERIAL` line, the Storekeeper scans one IMEI per unit. The system validates the Luhn check digit and rejects malformed IMEIs **at scan time**, not on submit.
- **FR-3.5** Scanning an IMEI that already exists in this tenant is rejected immediately with a message naming the existing unit's status and location. *(A duplicate IMEI is either a scanning error or a stolen-goods red flag. Never silently accept it.)*
- **FR-3.6** For a `QUANTITY` line, the Storekeeper enters a count.
- **FR-3.7** Confirming a Goods Receipt creates the `DeviceUnit`s with their per-unit acquisition cost, increments quantity levels, and writes one `+` movement per line. Units enter as `IN_STOCK` at the receipt's location.
- **FR-3.8** A receipt whose serial line has fewer scanned IMEIs than its declared quantity cannot be confirmed.
- **FR-3.9** Receiving against a PO records the linkage, and the PO reports its received-vs-ordered state (`pending`, `partial`, `complete`).

### 5.4 Outbound — Sales & Issue

- **FR-4.1** A Seller creates a Sales Invoice: customer (optional) and location. Line currencies come from their products (FR-2.7); the invoice has no currency of its own.
- **FR-4.2** The Seller scans an IMEI; the system resolves it to a `DeviceUnit` and adds it as a line at the product's default sale price.
- **FR-4.3** Scanning an IMEI that is not `IN_STOCK` is rejected, stating the actual status. *(You cannot sell a phone that is already sold.)*
- **FR-4.4** Scanning an IMEI held at a different location than the invoice's is rejected.
- **FR-4.5** Only Owner/Manager may override a line's price. A Seller's invoice uses the catalog price.
- **FR-4.6** Confirming the invoice marks each unit `SOLD`, decrements quantity lines, writes one `−` movement per line, and generates the invoice PDF.
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
- **FR-8.4** Each document line shows its amount in its own currency, correctly formatted (`$1,000.00` vs `1 000 so'm`), and the document footer shows **one subtotal per currency present** — never a combined total, and never a converted one.

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
| Validation & serialization | **Pydantic v2** — request/response schemas in `presentation`, `pydantic-settings` for `Settings` in `infrastructure`. **Never imported by `domain` or `application`** (§7.3). |
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

#### Data shapes across the layers — where Pydantic v2 lives, and what a DTO is

Three kinds of data-carrying classes exist, one per layer. They look similar and are **not interchangeable** — each exists to keep its layer's dependencies clean:

| Layer | Class kind | Example | Job |
|---|---|---|---|
| `presentation` | **Pydantic v2 `BaseModel` schemas** | `ConfirmInvoiceRequest`, `InvoiceResponse` | Parse and validate raw HTTP input; serialize responses. This is also where **role-based field omission** happens (FR-1.7): a Staff-facing response model simply has no cost fields. |
| `application` | **DTOs: frozen `@dataclass`es** | `ReceiveGoodsCommand`, `ScanResult` | Carry structured data across the use-case boundary. No behavior, no validation logic, no framework imports. |
| `domain` | **Entities & value objects** | `Money`, `IMEI`, `GoodsReceipt` | Not DTOs at all — they hold *behavior and invariants*. An `IMEI` validates itself; a DTO never does. |
| `infrastructure` | **SQLAlchemy models** | `DeviceUnitModel` (mapped to `device_units`) | The *persistence* shape of an entity. **Never escapes the repository**: each repository maps row ↔ domain entity internally, so `application` never sees the ORM. |

**Who maps what:** row ↔ entity mapping lives **inside repositories** (`infrastructure`) — the repository's public signatures speak domain types only. Schema → DTO/args and entity → response-model mapping lives in **`presentation`** (a `from_entity()` classmethod on the response schema is the idiomatic form). No mapping code exists in `domain` or `application` — those layers are mapped *to*, never mapping themselves.

**Why application DTOs are dataclasses and not Pydantic models:** `application` depends on `domain` only — that rule is what makes use cases testable with in-memory fakes. Pulling Pydantic into `application` would work mechanically, but it drags a validation framework into the one layer whose tests are supposed to run with zero framework, and it creates a second place where validation *could* live. The split is deliberate: **structural validation** (types, required fields, ranges) happens once, at the edge, in the Pydantic schema; **semantic validation** (a well-formed IMEI, a non-negative Money, a confirmable receipt) happens in the domain. A DTO in between carries data and validates nothing, so there is never a question about which layer owns a rule.

The flow for one request:

```
HTTP JSON ──▶ Pydantic schema (presentation: shape, types)
          ──▶ DTO / plain args (application boundary)
          ──▶ entities & value objects (domain: invariants)
          ──▶ result DTO ──▶ Pydantic response model ──▶ JSON
```

**When to actually write a DTO — and when not to.** A use case taking two scalars needs no ceremony: `ReceiveGoods.execute(receipt_id, user_id)` (§7.4) takes plain arguments, and that is the correct form. A DTO earns its place when the input is *compound* — `CreateInvoiceCommand` with customer, location, payment type, and a list of lines — or when a use case returns a structured result the router must serialize. The rule mirrors §7.6: no mapping class exists before there's a concrete shape that needs carrying. Mapping code (schema → DTO, entity → response model) lives in `presentation`, because it is presentation that knows both sides.

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
- **Aggregates & invariants** — when we build `GoodsReceipt.confirm()`. A receipt and its lines are one consistency boundary: you cannot confirm a receipt whose lines don't add up, so they must be loaded, validated, and saved as a unit. This is where "aggregate" stops being jargon and starts being obvious. The store-credit invoice (whose remaining balance must always equal entered debt minus its payments, never negative) is the second worked example, at M5b.
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
| `GET` | `/devices/{imei}/history` | any (cost hidden by role) |
| `GET` | `/reports/stock-on-hand` | Manager |
| `GET` | `/reports/sales-summary` | Manager |
| `GET` | `/reports/ageing` | Manager |
| `GET` | `/reports/movements` | Manager |
| `GET` | `/reports/financial-ledger?from=&to=&category=&location=` | Manager |
| `GET` | `/reports/month-end?year=&month=&location=` | Manager |
| `GET` | `/reports/month-end/pdf?year=&month=&location=` | Manager |
| `GET` / `PUT` | `/settings/tenant` | read: any · write: Owner (timezone, letterhead) |

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
| **M1** | **Tenancy & Auth** | MasterDB, tenant provisioning, engine registry, migration fan-out CLI, JWT, roles. Demo: sign up two tenants; prove tenant A cannot see tenant B. |
| **M2** | **Catalog** | Products (both tracking types, **per-product currency** with USD/UZS defaults), locations, suppliers, customers. Demo: build a catalog. |
| **M3** | **The ledgers** | `StockMovement` **and** `FinancialTransaction`, projections, valuation rules, `verify-projections` + financial reconciliation. Demo: a confirm writes both a stock movement and its money entry, and both reconcile. |
| **M4** | **Inbound** | PO → Goods Receipt, IMEI scan-in, Luhn + duplicate rejection, `PURCHASE` financial entries. Demo: **scan 10 phones into stock with a real scanner.** |
| **M5** | **Outbound** | Sales Invoice, scan-to-sell, confirm, cancel-with-compensation, `SALE_REVENUE` + `COGS` entries. Demo: scan a phone, sell it, cancel, watch both goods and money reverse. |
| **M5b** | **Credit sales & customer debt** | `payment_type` on sales, `CreditCompany` reference list, som-denominated store-credit debt, `Payment` ledger, customer accounts, debtor list, `verify-balances`. Demo: **sell a $600 phone on store credit for 7.8M som with an 800k down payment, record two payments, show the remaining balance — then sell another via a credit company and show it settled with zero debt.** |
| **M6** | **Counts, write-offs, supplier returns** | Full discrepancy → adjustment flow with `WRITE_OFF_LOSS` / `COUNT_ADJUSTMENT` / `SUPPLIER_RETURN_CREDIT` entries. Demo: hide a phone, run a count, watch the system find it missing and book the loss. |
| **M7** | **Documents** | PDF generation for PO, Invoice, Supplier Return. Demo: print a real invoice with an IMEI on it. |
| **M8** | **Reporting** | Stock on hand, IMEI trace, sales summary, ageing, financial ledger. Demo: trace one IMEI's entire life. |
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
| **Month boundaries & timezone** | Medium | Period math runs in the tenant's timezone (FR-10.8), so a tenant timezone setting must land in M1. Without it, a late-night sale slips into the wrong month and the report is quietly wrong. |
| **Month-end report performance** at scale | Low (v1) | v1 computes opening/closing live from the full ledger — fine at MVP volumes. If a tenant's ledger grows large, add stored month-end snapshots (opening = prior stored closing) as a v2 optimization; correctness is unaffected either way. |
| **PDF library choice** | Low | **Open question.** WeasyPrint (HTML/CSS templates — far easier to iterate on, but a heavier system dependency: cairo/pango) vs ReportLab (pure Python, no system deps, but layouts are written in code). Leaning WeasyPrint; decide at M7. |
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
