# ApexWMS — V2 Scope & Roadmap

**Version:** 2.0 (roadmap)
**Status:** Agreed scope, PRDs pending
**Last updated:** 2026-09-08

---

## 0. What this file is

[docs/prd.md](prd.md) specifies the system as it exists. V1 (M0–M9) is delivered:
tenancy, catalog, both ledgers, inbound, outbound, credit sales, counts and removals,
PDFs, reporting and the month-end report all ship, and the first stores are on it.

This file is **a roadmap, not a specification**. It names the V2 workstreams, their
boundaries and their order, and it collects everything `prd.md` deferred so that the
deferral list lives in one place instead of three. Each workstream gets its own PRD at
`docs/prd-v2-<slug>.md` before any of it is built; that PRD carries the FR-level
requirements, this file does not.

### Fixed ground

These V1 decisions are **closed**. V2 builds on top of them and does not revisit them:

- **The seven money rules** (§4.6) and the per-currency model: no base currency, no
  exchange rate, two totals rather than one combined bottom line (§4.5).
- **The two append-only ledgers** as the source of truth, with every other figure a
  projection written in the same transaction.
- **Database-per-tenant** with split identity — `User` in MasterDB, `Employee` in each
  store, same id.
- **The flat permission catalog** with two role namespaces kept apart by prefix (§3.5).

A V2 feature that needs one of these to change reopens it **explicitly, in its own PRD,
with the reasoning written down**. The failure mode this section exists to prevent is a
new feature dragging an exchange rate or a `tenant_id` column into the system sideways.
Two live examples: the public catalog (W4) wants one price per handset for a shopper,
which is where an FX rate would sneak in; billing (W2) is platform data and belongs in
MasterDB, never in a store's database.

---

## 1. Workstreams

| # | Workstream | Depends on | PRD |
|---|---|---|---|
| **W1** | Platform: `/admin/*` API and the SuperAdmin portal | — | `prd-v2-admin-portal.md` |
| **W2** | Billing and subscriptions | W1 | `prd-v2-billing.md` |
| **W3** | File storage and product photos | — | `prd-v2-media.md` |
| **W4** | Public catalog and Telegram bot | W2, W3 | `prd-v2-public-catalog.md` |
| **W5** | Supplier debt, cash drawer and shifts | — | `prd-v2-payables-cash.md` |
| **W6** | Inter-location transfers | — | `prd-v2-transfers.md` |
| **W7** | Seller performance and audit log | — | `prd-v2-people.md` |
| **W8** | Warranty, Excel, operations | — | `prd-v2-operations.md` |

W1 → W2 → W3 → W4 is a chain. W5–W8 are independent of it and of each other, and slot
in wherever there is capacity.

### W1 — Platform: `/admin/*` API and the SuperAdmin portal

**Goal:** every operation that today needs shell access to the server becomes a screen.

Platform operators already exist as real accounts holding `app.superadmin` / `app.admin`,
and their token simply carries no tenant claim, so no new auth realm is needed — only
routes and a UI.

In scope:

- `/admin/*` HTTP API, authorized by `APP_ROLE_PERMISSIONS`.
- The portal itself. Whether it is a route group in the existing Next.js app or a second
  app is the first question its PRD answers.
- **Every `apexwms` CLI command gets a GUI equivalent**: `create-tenant`, `list-tenants`,
  `suspend-tenant`, `activate-tenant`, `retry-provisioning`, `migrate` / `migrate-master`
  (with per-tenant version state visible), `seed-tenant`, `seed-phones`, and the three
  audits `verify-projections`, `verify-financials`, `verify-balances`.
- Server-side hard gate on `must_change_password`.
- Welcome email carrying the Owner's temporary password. This is the project's first
  transactional email, so it brings an email provider with it.
- Impersonation, feature flags, API keys.

Out of scope: per-store custom roles (DB-driven `TenantRole`). `register_tenant_role()`
is the seam and the schema change is additive; nothing asks for it yet.

**The CLI does not go away.** It stays the recovery path for a portal that is down or a
tenant that cannot be resolved, and it stays what CI runs. The portal becomes the
everyday surface.

The audits are the interesting part of this workstream: `verify-*` today prints to a
terminal for one tenant at a time. In the portal they become a fleet view — which tenants
reconcile, which drifted, when each was last checked.

### W2 — Billing and subscriptions

**Goal:** a store's access is tied to whether it pays, and that link is enforced by the
system rather than by somebody remembering.

In scope:

- `Subscription`, `SubscriptionPlan`, `PlanFeature` in **MasterDB**, on the tenant
  registry. This is platform data; it never touches a store's database.
- **Two months of demo** on every new tenant, granted at provisioning.
- **Payment is recorded, not processed.** A store pays by transfer or in cash, outside
  the system; an operator marks the payment in the portal against the subscription. The
  payment log is append-only, for the same reason every other ledger here is.
- A subscription check that runs **immediately after tenant resolution**, so an expired
  tenant is stopped before any of its data is touched.
- Automatic suspension on expiry. The `suspended` status and `activate-tenant` already
  exist and are unchanged — expiry becomes a second thing that can set the flag.
- Plan features drive W4: whether a store appears in the public catalog is a
  `PlanFeature`, not a separate setting.

Out of scope for now, designed for: a payment gateway (Payme, Click, Uzum). The billing
domain is shaped so a gateway becomes a second source of payment records, not a rewrite.
Also out: invoices to stores, VAT, dunning emails.

### W3 — File storage and product photos

**Goal:** the system can hold pictures.

It cannot today. The tenant logo is a `LargeBinary` column on `tenant_settings`, and
migration `0009_tenant_logo` says why in as many words: one image of a few dozen
kilobytes did not justify a deployment dependency, and *"if a tenant ever needs many
files, that is the point to reconsider."* Photos of handsets are that point.

In scope: object storage (S3-compatible, MinIO in development), photo upload on a product
and on an individual `DeviceUnit`, thumbnails, and the tenant logo moving out of its
column into the same store.

Per-unit photos matter more than per-product ones here, because a used handset's actual
scratches are what a buyer wants to see, while a catalog photo of a new iPhone is
interchangeable.

### W4 — Public catalog and Telegram bot

**Goal:** a shopper asks "who has an iPhone 13 128GB" and gets an answer, and the stores
get walk-ins.

The model is [ArzonApteka](https://arzonapteka.uz/en/bot) and Oson Apteka: an aggregator
over many independent shops, with a Telegram bot as the interface for the end customer
and the shops paying for the traffic.

For each match a shopper sees: model, sale price, condition (new or used), photo, the
store's name, its address and contact, and a map.

In scope:

- **A separate service with its own database.** It is not a tenant, it holds no ledger,
  and it is the only part of ApexWMS with unauthenticated public read traffic. Keeping it
  physically apart from the WMS is the point.
- A denormalized availability view fed from the tenants that opted in.
- The Telegram bot: search, results, store card, map.
- Participation is a `PlanFeature` from W2, plus a per-tenant switch — a store must be
  able to leave.

Its PRD decides:

- **How data reaches the view.** Two candidates: a scheduled read of each tenant database
  into the public store, or an outbox table in the WMS with a publisher. The first puts
  zero code in the WMS write path; the second is fresher. Phone stock moves slowly enough
  that minutes of staleness are probably fine, which argues for the first.
- What "in stock" means to a shopper, and how a unit sold two minutes ago disappears.
- Whether a unit with no `asking_price` is listed at all. FR-2.14 already refuses to sell
  a used handset with no price; listing one publicly with no price is the same problem.

What it must not do: invent an exchange rate to show one price, or expose acquisition
cost, margin, customer data or IMEIs.

### W5 — Supplier debt, cash drawer and shifts

**Goal:** close the half of the money picture V1 left open.

V1 knows who owes the store money (customer debt, §4.7). It does not know **what the
store owes its suppliers**, which for a trade that takes phones on consignment is a real
hole. Supplier accounts payable is the mirror of the customer debt model already built,
and should reuse its shape: an open balance, recorded payments, no schedules.

The cash drawer is the second piece: how much cash is in the till, cash taken out,
per-shift reconciliation per seller. This is the natural home for the thing §1.3
sidestepped — the system records payments received but runs no till.

The **som-paid USD sale** question (§4) is closed by the *tender*, gated on
`tenant_settings.runs_till` and off until a store says it balances a drawer. With it on,
both directions are recorded: what the customer handed over on a sale, and what was
handed to a walk-in for a used handset. Off, neither is, and FR-3.4c's inert `cash_paid`
stands. Nothing converts and no existing report moves either way. What remains here is
the till and shift screens that read those rows and prove the drawer at end of shift.

### W6 — Inter-location transfers

**Goal:** move stock between a store and a warehouse and have the ledger say so.

Deferred since §1.3, and deliberately cheap: `Location` is modeled and recorded on every
movement already, so this is additive — a document type with the same
`DRAFT → CONFIRMED → CANCELLED` lifecycle as the six that exist, writing paired stock
movements and no financial transaction, since a transfer moves goods and not money.

### W7 — Seller performance and audit log

**Goal:** answer "who sold what, at what margin" and "who changed this".

Sales, margin and discounts per employee, as the basis for commission. The data is
already in the ledger and on the invoices; this is reporting, not new recording.

The audit log is the gap next to it. Stock movements and both price logs are append-only
and name their author, but editing a customer, a supplier or a tenant setting leaves no
trace.

### W8 — Warranty, Excel, operations

**Goal:** the unglamorous things a store and an operator both ask for in month two.

- **Warranty on a unit.** §1.1 names the warranty clock as part of the problem, and V1
  does not track it. A warranty period on a sold unit, visible on the IMEI trace and on
  the invoice.
- **Excel import and export** for the catalog and stock on hand.
- **Full tenant data export.** Billing makes this mandatory rather than nice: a store
  that stops paying must be able to leave with its data.
- **Per-tenant backups, metrics and error tracking**, surfaced in the W1 portal.
- Low-stock alerts. This is the first real trigger for domain events, which §7 deferred
  until something needed them.
- Onboarding wizard for a new store.

---

## 2. Register: everything prd.md deferred

Collected from `prd.md` §1.3 (Non-Goals), §3.5 (the deferred-tenancy table) and §11
(Deferred to v2). Items map to the workstream that picks them up; items with no
workstream are in §3, not planned.

**Tenancy and administration** (§3.5) — W1, W2:
SuperAdmin admin portal · `/admin/*` API · billing and subscription metadata ·
API keys, feature flags, impersonation · welcome email · server-side hard gate on
`must_change_password`. Deferred further: per-store custom roles (DB-driven `TenantRole`).

**Warehouse and logistics** (§11) — W6, W8:
inter-location transfers (W6) · low-stock alerts and the domain events they justify (W8) ·
reservations (§3). Barcode label printing shipped in V1 rather than being deferred.

**Money** (§11) — W5, and §3:
supplier accounts payable (W5) · stored month-end snapshots, a performance optimization
only, correctness unaffected either way (W8, and only once a tenant's ledger is actually
large) · external accounting export to 1C or QuickBooks, a full double-entry chart of
accounts, and a single combined cross-currency bottom line (all §3).

**Credit and debt** (§11) — §3, except:
due dates and overdue tracking on store credit, and customer credit limits, which are
cheap additive fields if owners ask (§4). Installment schedules and credit-company payout
and commission tracking stay out (§3).

**Pricing** (§11) — all §3:
condition grades driving an automatic used price · depreciation curves and market feeds ·
a floor price per unit · scheduled or automatic markdowns by age · percentage-driven bulk
markdowns · lower-of-cost-or-market write-downs · price lists per customer or channel ·
any exchange rate.

**Whole domains** (§1.3):
repairs and service tickets (§3, though W8's warranty tracking is adjacent) ·
e-commerce and marketplace sync (§3 — W4 is the deliberate, narrower version) ·
a full CRM beyond name and phone (partly W4, partly §3) · a native mobile app (§3) ·
purchase-order approval workflows (§3) · payment processing (§3; W5 adds a till, which is
recording cash, not processing it).

---

## 3. Not in V2

Named so a request for one of these is a V3 conversation rather than V2 scope creep.

- **Repairs and service tickets.** A separate domain with its own workflow.
- **E-commerce and marketplace sync.** W4 publishes availability; it does not sell.
- **Full double-entry bookkeeping and a chart of accounts**, and export to 1C or
  QuickBooks. The internal ledger is an inventory-and-margin ledger by design.
- **A single combined cross-currency total.** Requires an FX rate, which §4.5 removed on
  purpose.
- **Automated used-price valuation** in any form.
- **Installment schedules, interest, late fees, credit scoring, repossession.**
- **Credit-company payout and commission tracking.** Revisit only if a company actually
  starts paying late or short; sales are labelled by company, so history survives.
- **A native mobile app.** Web, with a keyboard-wedge scanner.
- **Purchase-order approval chains.**
- **Payment processing**: card rails and gateways for *store* sales. W2's gateway is for
  subscription payments to us, which is a different thing.
- **Reservations.**

---

## 4. Open questions

| Question | Whose | Why it is open |
|---|---|---|
| **Expected tenant count.** | W1, W2 | `prd.md` §11 has asked since M1 and never got an answer. The LRU engine registry tops out around 50 concurrently-active tenants on default settings; past that it is PgBouncer or a different isolation strategy. Billing is what finally makes the number knowable, so it is answered here. |
| ~~A som-paid USD sale records no som.~~ **Closed 2026-09-10.** | W5 | Closed by the *tender*, behind `tenant_settings.runs_till` and off by default. A store that keeps a drawer records what physically changed hands in both directions: `TENDER_RECEIVED` on a sale, `TENDER_PAID` for the som handed to a walk-in. Off, nothing is recorded and the system is exactly what V1 shipped, FR-3.4c included. No rate either way, and no existing figure moves: month-end names its seven categories, `inventory_effect` skips what it does not know, and the debt movement is still pinned to `PAYMENT_RECEIVED`. What W5 still owes is the till and shift screens that read these rows. |
| **Two totals, confirmed with a real owner?** | W5 | `prd.md:319` claims the no-combined-bottom-line decision was confirmed with target users; it has never been re-confirmed with a store owner now actually running the system. Cheap to ask, expensive to retrofit. Any future statutory or tax reporting will need som figures regardless. |
| **Weighted-average cost for accessories, confirmed with a real owner?** | W5 | `prd.md` §11 asked for this to be confirmed before M3 and it never was. M3 shipped with weighted-average cost for quantity items, maintained from the purchase ledger; serialized phones sidestep it entirely. The method is in production and the figures reconcile, so this is a question about whether it matches how the owner *thinks* about accessory cost, not about correctness. |
| **Store-credit due dates and credit limits.** | W5 | Both are additive fields, not redesigns. Build them if owners ask; do not build them speculatively. §11's reasoning stands: the debtor list orders by age of the oldest open invoice, so stale debts surface without a due date. |
| **Credit company pays late or short.** | — | V1 cannot represent it, and the model assumes payment at sale time. Still accepted. Revisit only if it happens. |
| **How availability reaches the public catalog.** | W4 | Scheduled read of each tenant database versus an outbox in the WMS. Settled in W4's PRD, not before. |
| **Where the admin portal lives.** | W1 | A route group in the existing Next.js app, or a second application. Settled in W1's PRD. |
