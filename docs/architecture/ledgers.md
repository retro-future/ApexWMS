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

## Money with no goods behind it

`LedgerPoster.post_money` is the one way to write the money ledger without
writing the stock one. A `PostingEntry` exists so a caller cannot describe
a stock effect without saying what it did to the money; a customer payment
(PRD §4.7) is the genuine inverse, and it has no movement to hang itself
on. Naming that case as a method keeps every ledger write inside
`LedgerPoster` rather than letting `PaymentPoster`
(`application/services/payment_posting.py`) reach
`FinancialTransactionRepository` directly. It does not commit, like
everything else there.

**A payment's ledger row names `(DocumentType.PAYMENT, payment.id)`, not
the invoice it settles.** `DocumentType`'s seventh member is the only one
that is not a `Document` — no lifecycle, no lines — and it earns its place
because the enum is the vocabulary of *what caused a row*. Booking
payments under the invoice would put them inside
`LedgerPoster.reverse`'s blast radius, so cancelling a store-credit sale
would silently reverse the money the customer handed over (PRD FR-11.11
forbids exactly this). The alternative was a `PAYMENT_RECEIVED` carve-out
inside `reverse`, in the one service the rule above says must not have
one.

FR-11.8's reversal is therefore not a `reverse()` call at all: it is a
compensating negative `Payment` row naming the original through
`reverses_payment_id`, which is `UNIQUE` so a payment cannot be reversed
twice.

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

## The accessory cost pool is replayed, not stored

A serialized phone carries its own `acquisition_cost`, so its COGS is a
fact. A quantity accessory has no per-unit identity, so its cost is a
weighted average — and there is **no column holding it**.
`application/services/cost_pools.py`'s `CostPoolReader` rebuilds one
product-and-location pool from the stock ledger's quantities and the money
ledger's purchase values, in total per document rather than per unit
(dividing a line's cost out and multiplying it back would introduce a
rounding error that was never in the data).

One replay, several callers, and that is the point: `issue_value` is what
`InvoicePoster` books COGS from, what `RemovalPoster` values a return
credit and a write-off loss from, and what `CountPoster` values a shortage
from, while `LedgerReconciler` recomputes on-hand value from the same pool
for PRD FR-10.7. Two implementations would let a sale be booked at one
average and reconciled against another, showing up as a discrepancy in the
check that exists to catch real ones. `INVENTORY_SIGN` lives there too,
since both sides read it.

A count *surplus* is the one figure that cannot come from `issue_value`:
nothing is being taken out. It uses `CostPool.average_unit_cost`, and where
the pool is empty there is no average and no stand-in for one, so
`CountPoster` refuses the confirm rather than booking zero.

## Reading them back (PRD §5.9, §5.10 — M8)

The reports are reads over these two tables and nothing else, which is why
none of them needed a new column. Three things about how they are shaped:

**Signs are never flipped for presentation.** A `PURCHASE` and a `COGS` are
stored negative because §4.6's convention describes *cash*, and the sales
summary reports them that way, so its margin is `revenue + cost` with no
sign adjusted anywhere. `INVENTORY_SIGN` above is the one place a sign is
reinterpreted, and it exists because inventory value genuinely asks a
different question from cash.

**Nothing is excluded.** A reversal keeps its type and flips its sign, so
the movement log, the financial ledger and every aggregate over them net a
cancelled document to zero without a category to filter out. This is the
payoff of having no `REVERSAL` type.

**A `(document_type, document_id)` pair resolves to a number in one place.**
`persistence/tenant/repositories/document_ref.py` is a `CASE` over the six
tables that have one, shared by both logs. `DocumentType.PAYMENT` is absent
from it: a payment has no number to show.

Two reads do not come from the ledgers. FR-9.4's ageing and FR-9.6's
needs-pricing worklist read `device_units` and its price log, because
"how long has this been here and has anyone priced it" is a question about
the projection, not about what moved. FR-9.6's `WHERE` is the one place
FR-2.14 is stated a second time, in SQL, and
`tests/api/test_stock_reports_api.py` asserts it against `PriceResolver`
for the same units so the two cannot drift.

## Verification

`apexwms verify-projections`, `verify-financials` and `verify-balances`
(`application/services/verification/`, one module per audit) audit all of
it, per tenant or fleet-wide. All three **report and never repair**: a sweep
that quietly rewrote a projection would destroy the evidence of whatever
wrote it wrong. Note `INVENTORY_SIGN` in `services/cost_pools.py`, which
`reconciliation.py` reads: PRD §4.6's signs describe *cash*, so `PURCHASE`
and `SUPPLIER_RETURN_CREDIT` flip when read as inventory value.

`BalanceVerifier` is the odd one out, because customer balances have no
cached projection to check against — nothing stores a balance, on the
customer or the invoice (PRD §4.7). What it audits instead is that the two
independent records of the same fact agree: the `payments` table against
the money ledger's `PAYMENT_RECEIVED` rows, which `PaymentPoster` writes in
one transaction and so can only diverge if something bypassed it. It also
sweeps for a debt smaller than what has been collected against it, and for
a settled sale (`PAID_IN_FULL`/`CREDIT_COMPANY`) carrying a payment at all.

## `cash_paid_minor` is inert

`DeviceUnit.cash_paid_minor`/`cash_paid_currency` is a bare pair and
**never a `Money`**, on purpose (PRD §4.5b): it enters no ledger, total, or
report, and `tests/application/test_cash_paid_is_inert.py` exists to catch
the future report that sums it.
