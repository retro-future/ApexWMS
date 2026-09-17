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

Since ADR 0007 there is **one** repository implementation, reached with a
`Specification` and a per-aggregate mapper. Two roots in
`infrastructure/persistence/repositories/base.py`:

- `SqlAppendOnlyRepository` — `add` + `get` + the spec reads, and **no**
  `update`/`delete`. The two ledgers and the two price logs use this
  (through `TenantSqlAppendOnlyRepository`, which only narrows the session
  to `TenantSession`).
- `SqlAlchemyRepository` extends it with `exists`/`update`/`delete` for
  every other aggregate.

The append-only guarantee is **structural**: the methods are absent from
the type, so a handler that tries to edit a ledger row fails `ty check`.
`tests/architecture/test_repository_bases.py` asserts that absence.

A read that returns a projection rather than a whole entity (a total, a
bucket, a row DTO) is a query service, not a repository method — see
[query-services.md](../../.claude/rules/backend/query-services.md).

Row ↔ entity mapping is a per-aggregate mapper class in
`infrastructure/persistence/mappers/`. A flat aggregate whose fields match
its columns gets `AutoMapper`; a ledger row whose `Money` is denominated by
a neighbouring table (the price logs read `model.product.currency`) needs a
hand-written one.

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

## A customer return books COGS positive, and no new inventory category

`CustomerReturnPoster` writes two money rows per line:
`SALES_RETURN_REFUND` for what the customer gets back, and a **positive**
`COGS` for what the goods cost. The second is what makes the accessory pool
work, and it needed no change to `INVENTORY_SIGN` at all: `CostPoolReader`
pairs each positive movement with the money rows on the same `document_id`
whose `INVENTORY_SIGN` contribution is positive, and `COGS` is already `+1`
there. So returned accessories re-enter the pool at the value they left it,
and `verify-financials` and the month-end rollforward fold the same figure
without either learning a new category. `SALES_RETURN_REFUND` is absent from
`INVENTORY_SIGN` for the reason `SALE_REVENUE` is: it is a figure about the
customer.

The value itself comes from the **sale**, not from today's pool — a
serialized unit's own `acquisition_cost`, or `Money.share` of the `COGS`
that invoice actually booked. The current average would let goods re-enter
at a price nobody ever paid for them, and complementary shares of one
amount sum back to it exactly, so two partial returns of a three-unit line
give back the whole cost and no more. `Money.share` is the same integer
half-up rule `CostPool.issue` splits a pool by; they live together in
`money.py` so the two cannot drift.

**Debt relief writes nothing to either ledger.** A store-credit debt is a
column on the invoice rather than a ledger row (§4.7), so what a return
writes off it is a column too, on `customer_returns`. Reading the balance
counts confirmed returns only, which is what lets cancelling a return give
the relief back with no compensating row.
`tests/api/test_verify_cli.py`'s `TestCustomerReturnsReconcile` is what
holds all of this honest against a real store.

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
`persistence/tenant/queries/document_ref.py` is a `CASE` over the six
tables that have one, shared by both ledger query services. `DocumentType.PAYMENT` is absent
from it: a payment has no number to show.

Two reads do not come from the ledgers. FR-9.4's ageing and FR-9.6's
needs-pricing worklist read `device_units` and its price log, because
"how long has this been here and has anyone priced it" is a question about
the projection, not about what moved. FR-9.6's `WHERE` is the one place
FR-2.14 is stated a second time, in SQL, and
`tests/api/test_stock_reports_api.py` asserts it against `PriceResolver`
for the same units so the two cannot drift.

## Valuing the ledgers at a past instant

Every read above answers a question about *now*. The month-end close asks
about a moment that has passed, and a projection cannot answer that: a unit
row says where a handset is today, not whether the store still held it on
31 January. So the close reads the ledgers themselves at a cutoff.

Three pieces carry the cutoff. `MovementsForPair` and `TransactionsForPair`
take an optional `as_of` (exclusive), `CostPoolReader.pool_for` passes it
to both so quantities and costs are replayed to the same instant, and
`SqlStockMovementQueries.serialized_value_at` finds the handsets whose
movements still net above zero at the cutoff and values each at its own
`acquisition_cost`. `InventoryValuer`
(`application/services/inventory_value.py`) folds the two halves into a
per-location, per-currency figure — FR-10.6's breakdown, and the goods side
of FR-10.7's check.

`LedgerReconciler` deliberately keeps its own path over the projections
(`OnHandDeviceUnits`, `moved_pairs` with no cutoff). It is asking a
different question: whether the projections have drifted from the ledger.
The month-end close is asking what the ledger said at a date. Both fold
through the same `CostPoolReader` and the same `inventory_effect`, which is
what keeps them from disagreeing about the arithmetic while disagreeing
about the instant.

`inventory_effect` lives beside `INVENTORY_SIGN` in `cost_pools.py` rather
than in either caller, so the FR-10.5 rollforward and the FR-10.7 audit
cannot fold the same categories two different ways.

## The month-end close (PRD §5.10 — M9)

`MonthEndReporter` (`application/services/month_end.py`) is the whole
report, and every figure in it is a fold over what is already written.

**Opening and closing inventory are both rolled forward from the money
ledger since inception** (`totals_by_type(until=...)` through
`inventory_effect`), which makes "opening = previous closing" exact rather
than approximately true. §5.10 says no stored snapshot is needed for
correctness, and this is why. `InventoryValuer` then computes the goods
side independently, and the difference — per currency, never summed — is a
`Discrepancy` on the report rather than an adjustment to it.

**The wire payload keeps §4.6's cash signs; the screen and PDF re-sign for
presentation.** `MonthEndReportData` carries `purchases` negative and
`supplier_return_credits` positive, unchanged. But the report reads as two
questions, and each is rendered as its own table: a **stock-value bridge**
(`MonthEndStockAndSales.tsx`, `month_end_pdf.py`'s `_stock_rows`) that runs
each move through `INVENTORY_SIGN` so a purchase reads as goods coming in
and a supplier return as goods leaving, ending on the closing figure; and a
**sales** table that keeps the cash signs because revenue-in / cost-out is
the point there. The supplier-return credit gets a one-line note between
the two, so the money that came back is visible without being confused for
the goods that left. `frontend/src/lib/month-end.ts`'s `INVENTORY_SIGN` is
the twin of the backend's and has to agree with it.

**Period boundaries come from `PeriodResolver`**
(`application/services/period.py`), which builds the month in
`ZoneInfo(await settings.get_timezone())` and converts to UTC. The end is
exclusive, matching `totals_by_type`'s `until`.

**The debt block is store-wide even when the report is scoped to one
location.** Debt belongs to a customer and a payment records no location,
so narrowing it would invent a figure. Its four movement lines
(`SqlMonthEndQueries`) include one FR-10.5 does not name: debt *voided* by
a cancellation. Without it `opening + booked - collected` does not reach
`closing` in any month where a credit sale was cancelled, and
`tests/application/test_month_end.py` asserts the identity month by month.

`SqlMonthEndQueries` is separate from `SqlSalesInvoiceQueries` because
every read in it is a period question — what was owed at an instant, what
moved in a window — while the sales queries answer "now" questions about
one customer or one invoice.

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

## `cash_paid_minor` stays out of the accrual figures

`DeviceUnit.cash_paid_minor`/`cash_paid_currency` is a bare pair and
**never a `Money`**, on purpose (PRD §4.5b): it must not be addable to a
per-currency total. `tests/application/test_cash_paid_is_inert.py` pins
that, asserting the accrual side of the close, inventory value and margin
are identical with the som figure recorded and cleared.

It is not unused. `ReceiptPoster._pay_out` books it as `TENDER_PAID`, and
`MonthEndReporter._earned_beyond_the_rate` subtracts it from the converted
`acquisition_cost` to produce `SomFigures.rate_gain` (W9 B2/B3/B7). The
rule it still obeys is the one in `prd-v2-money-and-rate.md`: never stored
as a converted fact, only converted inside a report at the rate stamped on
the receipt.
