# Below-cost accessory alert

## Problem

An accessory's catalog price (`Product.default_sale_price`) is a field a
person sets once and only changes by hand through `ProductRepricer`
(FR-2.19). Its weighted-average cost is not stored at all: `CostPoolReader`
replays it from `stock_movements` and `financial_transactions` every time it
is needed.

When a new goods receipt arrives at a higher unit cost than earlier
batches, the average cost rises but the catalog price does not. If nobody
reprices the product, every following sale of that accessory resolves to
the old catalog price, books COGS at the new higher average, and posts a
negative margin. There is no error and no warning. `PriceResolver.resolve`
returns `default_sale_price` with no cost check; `InvoicePoster` books
`SALE_REVENUE` and `COGS` from two independent figures.

Nothing in the system compares sale price to cost:

- FR-9.6 needs-pricing worklist: only products with no price at all.
- FR-9.7 price-deviations: charged price vs resolved price, not resolved
  price vs cost.

So one forgotten reprice is a slow loss across every sale of that product
until someone notices in the month-end report.

Serialized phones are not in scope. Each carries its own
`acquisition_cost`, and a used unit carries its own `asking_price`. Only a
`NEW` phone with no unit price falls through to the catalog price, and that
is a smaller, separate case.

## What we are building

Selling below cost is sometimes deliberate (clearance, damaged stock, a
loss leader). The feature makes the situation visible; it never blocks.

### 1. Warning on goods receipt confirm

After `ReceiptPoster.receive` has posted the receipt, check each quantity
(accessory) line's product: rebuild its cost pool at the receipt's location
and compare `pool.average_unit_cost` to the product's
`default_sale_price`.

If the average cost is greater than or equal to the catalog price (and the
product has a catalog price), attach a warning to the confirm response. One
warning per offending product, carrying: product id, SKU, catalog price,
new average unit cost. The receipt still confirms.

The warning rides on `GoodsReceiptData` as a new field, for example
`belowCostAlerts: list[BelowCostAlertData]`. The `Result` envelope only has
a single `message` string, so a typed list on the payload is the place for
structured, translatable data. The field is empty on every other read of
`GoodsReceiptData` (get, list, create, cancel) and only populated by the
confirm handler.

Frontend: the goods receipt detail page shows the alerts after a
successful confirm, each with a link to the product so an Owner or Manager
can reprice. No blocking dialog.

### 2. "Selling below cost" report

A new read-only report: every active quantity product whose current average
cost at a location is greater than or equal to its catalog price.

Columns: SKU, product name, location, catalog price, average unit cost,
difference, quantity on hand at that location.

- Query: `queries/list_below_cost.py` (`ListBelowCostQuery`,
  `ListBelowCostHandler`), a `PagedQuery`.
- Model: `models/below_cost.py` (`BelowCostRowData` with `from_entity`).
- Read: a method on a query service, computed in SQL, not a Python loop
  over `CostPoolReader.pool_for`. A store can have hundreds of accessories
  across several locations, and replaying every pool per request is too
  much work for a report. The average cost per `(product, location)` is
  `sum(PURCHASE and surplus COUNT_ADJUSTMENT value) / sum(inbound quantity)`
  read straight from the two ledger tables, filtered to
  `device_unit_id IS NULL`. This must fold the same categories the same way
  as `INVENTORY_SIGN` in `services/cost_pools.py`, or the report and a real
  sale would disagree about the same goods.
- Router: `GET /reports/below-cost` on `presentation/routers/reports.py`,
  behind `Permission.Reporting.View`.
- Sorting: its own enum in `application/sorting.py`, default by largest
  difference.
- Frontend: `frontend/src/app/(app)/reports/below-cost/`, following the
  existing one-folder-per-report pattern; add it to the reports index.

### Not in this iteration

- No change to invoice confirm. It stays thin.
- No block, no override flow, no acknowledgement/dismiss state on the
  report. If the report keeps listing a product the owner sells below cost
  on purpose, that is acceptable.
- Serialized / `NEW` phone below-cost detection.
- No stored average-cost column. The pool stays a replay.

## Decision when the alert fires

The alert is a prompt to decide, not a task with one required outcome. The
person answers one question: did I mean to sell this below cost?

- Oversight: raise `default_sale_price` to "new average cost + target
  margin" through the normal catalog reprice (Owner or Manager). Repricing
  is not retroactive; sales already posted at a loss stay as booked in the
  append-only ledger. The point of the alert is to catch it before many
  such sales pile up.
- Deliberate: acknowledge and move on. The report will keep showing the
  product, which is fine.

The receipt confirm is never held for a repricing decision: receiving goods
and pricing the catalog are separate actions with separate permissions
(a Storekeeper confirms receipts but cannot reprice).

## Testing

- `CostPool` already has unit tests; no domain change.
- Application test for the confirm handler: a receipt that pushes average
  cost above catalog price returns the alert and still confirms; a receipt
  that stays below returns none; a product with no catalog price returns
  none.
- Query-service test for the SQL average against a real database, checked
  against `CostPoolReader.pool_for` for the same product so the two agree.
- API test for `GET /reports/below-cost`: the §9 demo shape, permission
  gate, pagination.
- Frontend: vitest for the report page rendering and the confirm-page alert
  block.

## Files

New:

- `backend/src/application/queries/list_below_cost.py`
- `backend/src/application/models/below_cost.py`
- `backend/src/application/models/below_cost_alert.py` (the confirm-response
  row; or nest it in `goods_receipt.py`'s model file if that reads better)
- `frontend/src/app/(app)/reports/below-cost/` (page + components)

Changed:

- `backend/src/application/services/receipt_posting.py` or
  `commands/confirm_goods_receipt.py`: run the per-product check after
  posting. Decide during planning which layer owns it. `ReceiptPoster`
  already has the receipt and a products repository; the handler owns the
  response shaping. Leaning toward a small collaborator the handler calls
  after `receive`, so `ReceiptPoster.receive` keeps its single job.
- `backend/src/application/models/goods_receipt.py`: add `belowCostAlerts`.
- `backend/src/infrastructure/persistence/tenant/queries/`: the average-cost
  query service method (extend an existing stock/ledger query service
  rather than adding a new class if one fits).
- `backend/src/application/ports/tenant/queries.py`: the Protocol method.
- `backend/src/presentation/routers/reports.py`: the new route.
- `backend/src/application/sorting.py`: the new sort enum.
- `backend/src/di/providers/handlers.py`: register the new handler (and any
  new collaborator).
- `frontend/src/app/(app)/reports/page.tsx` (or the reports index): add the
  link.
- `frontend` API client regeneration for the new endpoint and the new
  `GoodsReceiptData` field.
- `.claude/feature-map.md` and `docs/prd.md` reporting section: add the
  report.
