# The two ledgers and their projections (PRD §4.3, §4.6 — M3)

`stock_movements` (goods) and `financial_transactions` (money) are
append-only and are the source of truth for everything else. Four rules,
none negotiable:

- **Nothing mutates stock except by writing a movement.**
  `stock_levels.quantity`, `device_units.status`/`location_id`,
  `device_units.asking_price` and `products.default_sale_price` are
  *projections* — updated in the same transaction as the row that causes
  them, never assigned on their own.
- **Both ledgers move together or not at all** (PRD FR-10.1). Everything goes
  through `application/services/ledger.py`'s `LedgerPoster`, which takes a
  `Posting` (a stock effect paired with its `MoneyEffect`s) and **never
  commits** — the calling handler owns the transaction. Don't give it a
  `UnitOfWork`; a service that could commit could commit half of something.
- **Cancellation compensates, never deletes.**
  `LedgerPoster.reverse(document_type, document_id)` appends negated
  copies. There is deliberately no `REVERSAL` movement type — a reversal
  keeps its type and flips its sign, so summing deltas is always right and
  no report has to remember to exclude a category.
- **Every aggregate is per currency.** `FinancialTransaction.amount` is a
  signed `Money` (PRD §4.6 defines the sign convention).

## Repository bases

**A repository base is a convenience for the majority, not a
classification of tables.** There are exactly two under
`infrastructure/persistence/tenant/repositories/base.py`, and adding a
third is the mistake this rule exists to prevent:

- `TenantCrudRepository` — an aggregate whose whole persisted state is one
  `TenantActivatableRow`: the identity records and the M2 catalog. It
  supplies `get`/`add`/`update` through the `_to_entity`/`_to_model`/`_apply`
  hooks, plus `_browse_page`, the paging shape every catalog list endpoint
  shares.
- `TenantRepository` — **everything else**, and it is deliberately an open
  bucket with no hooks and no `get`/`add`/`update`: the two ledgers, the
  two price logs, `device_units` (whose amounts are denominated by the
  *product*, so every read joins and the entity is rebuilt from a `Row`),
  the settings row, and the documents M4 brings.

An aggregate that does not fit `TenantCrudRepository` inherits
`TenantRepository` and writes the two or three methods its port declares.
**It does not get a base of its own.** Four bases grew here once, because
each misfit was answered with a new sibling — `TenantJoinedRepository` even
carried a docstring denying the `is-a` its own declaration asserted — and a
hierarchy that must have a box for every table grows with every table.
`tests/architecture/test_repository_bases.py` is that rule as a test. When
something is genuinely missing, widen `SqlRepository`'s mechanics
(`persistence/repository.py` — one session, `_insert`, and reads that are
generic *per method*, which is what lets a joined read need no separate
class) or write the method locally.

The append-only rule lives in **one** place: `AppendOnlyRepository` in
`application/ports/repository.py`, which is what handlers depend on and
therefore what actually prevents editing history. A ledger's SQL class has
no `update` simply because nobody wrote one — not because a base class
withheld it.

Row ↔ entity mapping stays **methods on the repository** (PRD §7.3): no
module-level mapping functions, and no auto-mapper. `Money` needs a
currency that lives on a neighbouring table, `IMEI` must pass Luhn, and
`DeviceUnit.__post_init__` checks fields against each other — none of which
field-name matching can express.

## Domain services and value objects behind the ledgers

`domain/services/` holds the two pure rules the ledgers rest on, each a
stateless class of static methods rather than free functions:
`pricing.py`'s `PriceResolver` (implements PRD §4.5b/FR-2.14's price
resolution) and `projection.py`'s `UnitProjector` (what the ledger implies
for a unit's state — used by both the poster and `verify-projections`, so a
reported mismatch is always real).
`UnitProjector` is DI-injected into `LedgerPoster` and `ProjectionVerifier`
(`di/providers/domain_services.py`, APP scope); `PriceResolver` is not —
its only caller is `DeviceUnitData.from_entity`, a response-model
classmethod, not a constructor-injected collaborator. See
[value-objects.md](value-objects.md) for `CostPool`, the weighted-average
costing value object these services build on.

## Verification

`apexwms verify-projections` and `apexwms verify-financials`
(`application/services/verification.py`) audit all of it, per tenant or
fleet-wide. Both **report and never repair**: a sweep that quietly rewrote
a projection would destroy the evidence of whatever wrote it wrong. Note
`_INVENTORY_SIGN` there: PRD §4.6's signs describe *cash*, so `PURCHASE` and
`SUPPLIER_RETURN_CREDIT` flip when read as inventory value.

## `cash_paid_minor` is inert

`DeviceUnit.cash_paid_minor`/`cash_paid_currency` is a bare pair and
**never a `Money`**, on purpose (PRD §4.5b): it enters no ledger, total, or
report, and `tests/application/test_cash_paid_is_inert.py` exists to catch
the future report that sums it.
