# Documents (PRD §4.4, §5.3, §5.4, §5.5, §5.6)

All six document types exist: `PurchaseOrder`, `GoodsReceipt`,
`SalesInvoice`, `SupplierReturn`, `WriteOff` and `StockCount`. All extend
`Document` (`domain/entities/document.py`), which owns §4.4's one lifecycle
— `DRAFT → CONFIRMED → CANCELLED`, terminal at both ends — and nothing else.
**What makes a particular document confirmable is its own business**: a
subclass overrides `confirm()` to state its invariants and delegates the
state change upward.

- **`GoodsReceipt.confirm()` is the aggregate rule, and it does no I/O at
  all** (PRD §7.4 point 3, FR-3.8, FR-3.10): scan counts against declared
  quantity, no IMEI twice, every unit priced, naming **every** offending
  IMEI in one message. `tests/domain/test_goods_receipt.py` imports no
  repository.
- **`acquisition_source` and `condition` never constrain each other**
  (PRD FR-3.3b) — the source is a fact about the delivery, the condition a
  fact about each handset, and the two are validated independently.
- **A scan row is not a `DeviceUnit`.** `goods_receipt_units` looks like
  `device_units` and is deliberately separate: a scan is a line on a draft
  with no status, no location and no movement behind it, and its
  `acquisition_cost_minor`/`asking_price_minor` are **nullable** until
  confirm (PRD FR-3.4b). `ReceiptPoster`
  (`application/services/receipt_posting.py`) turns each scan into a real
  unit, writes its intake price through `DeviceUnitRepricer` so the
  markdown log starts with `old_price = NULL` (PRD FR-3.11), and hands one
  `Posting` to `LedgerPoster` (see [ledgers.md](ledgers.md)). It never
  commits; `ConfirmGoodsReceiptHandler` owns the transaction, so a
  duplicate IMEI found on the tenth phone rolls back the nine before it.
- **Cancelling a receipt compensates and reprojects.** The units land in
  `DeviceStatus.RECEIPT_CANCELLED`, not `WRITTEN_OFF`. `GoodsReceipt.cancel()`
  refusing a second call is the *only* thing stopping a double reversal;
  `LedgerPoster.reverse` deliberately holds no guard of its own.
- **Cost is response-shaped, the asking price is not** (PRD FR-1.7,
  FR-7.2). `Permission.COST_VIEW` gates `acquisitionCost`, `cashPaid`, and
  every subtotal, since a subtotal of costs is a cost.
- Document numbers (`PO-2026-0001`) come from `DocumentNumberer` over a
  **locked counter row**, not a Postgres sequence: a sequence is
  transaction-independent, so a rolled-back draft would burn its number.
- No new `Permission` members were needed — `PURCHASE_ORDER_*`,
  `RECEIVING_*`, `PRICING_SET`, `COST_VIEW` and `DOCUMENT_CANCEL` were
  already in the catalog with the right grants.

`tests/api/ledger_helpers.py`'s `receive_phone` **stays** rather than
moving to the new endpoints: what it produces is a used handset in stock
with no asking price, which FR-3.10 exists to refuse, and two M3 tests
(FR-2.15's three-row markdown log, FR-2.14's refusal) rest on that state.

## The Sales Invoice, and why its `confirm()` is thin

`GoodsReceipt.confirm()` can state every one of its invariants because all
of them are facts about its own lines. `SalesInvoice.confirm()` cannot:
what a line charges depends on the *live* `DeviceUnit` and the *live*
catalog row, and resolving that needs two repository reads. So the split
runs along the I/O boundary rather than along the document type.

- **`SalesInvoice.confirm()` checks only the aggregate** — still a draft,
  has lines, no handset on it twice. `tests/domain/test_sales_invoice.py`
  imports no repository, exactly as the receipt's suite does.
- **`InvoicePoster` (`application/services/invoice_posting.py`) does the
  rest**: re-check that each handset is still `IN_STOCK` here, re-resolve
  every price through `PriceResolver`, snapshot the line, and hand one
  `Posting` to `LedgerPoster`. It never commits, so
  `ConfirmSalesInvoiceHandler`'s transaction is what makes PRD FR-4.5b2's
  *"nothing is written to either ledger"* true for a tenth line that will
  not resolve.

**A draft line's `resolved_price` and `charged_price` are nullable, and
they stay null for its whole life as a draft.** That is PRD FR-4.5b1
expressed structurally rather than in a comment: there is no scan-time
figure for anything to freeze, and the price the scan response returns is
a display value the invoice never stores. `override_price` is the third
and separate column — what a Manager typed, which survives re-resolution.

That nullability is what the counter screen has to work around, since it
still needs a figure to read to the customer. `frontend/src/lib/invoices.ts`
and `hooks/use-invoice-quote.ts` assemble one from each handset's own
`resolvedPrice` and each accessory's `defaultSalePrice` — both already
published by the API, so the client applies no resolution rule of its own —
and label the result a quote. It is not cached against the invoice and not
sent back; `ConfirmSalesInvoiceHandler` resolves again regardless, and the
two figures are allowed to differ.

`price_approved_by` sits on the line rather than being read off the
document, because the confirmer and the approver are routinely different
people (PRD FR-4.5f); the ledger's `user_id` names the confirmer, so
without the column the deviation report would attribute the discount to
whoever happened to be at the till. That report is
`queries/list_price_deviations.py`, reading the two snapshot columns back
through `SalesInvoiceRepository.list_deviations` — the one place the join
onto `device_units` is outer, because an accessory line deviates without
naming a handset.

**Nothing on the invoice payload is behind `Permission.COST_VIEW`**, in
deliberate contrast to the receipt: every figure on an invoice is a price
the customer is being asked for, and a Seller must see all of them. The
receipt's figures are costs, and `SalesInvoiceData` carries none.

## Payment terms sit on the invoice, and the balance does not

`payment_type`, `credit_company_id`, `contract_ref` and `debt` are columns
on `SalesInvoice`, and `_assert_terms` is the invariant over them — run
from `__post_init__`, from `set_terms`, and again from `confirm`, so a
repository read cannot produce an invalid invoice and a draft saved through
some other path cannot confirm past the rule. All three are pure functions
of the invoice, which is why they live here rather than in `InvoicePoster`
alongside the price re-resolution that needs I/O.

**`debt` is a column and the balance is not.** What the customer still owes
is `debt − Σ payments`, recomputed on every read: by
`SalesInvoiceData.from_entity`, by `SalesInvoiceRepository.credit_history_for`,
and by `list_debtors`'s grouped query. There is no `balance` column on
`customers` or on the invoice, and the entity in
`domain/entities/customer.py` says so in its docstring. Same discipline as
`stock_levels.quantity`, minus even the projection.

`SalesInvoiceData` carries the payment rows, so the counter screen reads
one response rather than two, and a *cancelled* invoice's `paidMinor` is
the refund figure PRD FR-11.11 asks to surface — its debt is void because
every balance read counts confirmed invoices only, while the payments are
booked under their own document identity and survive
`LedgerPoster.reverse` untouched (see [ledgers.md](ledgers.md)).

`CreditCompany` is a `TenantCrudRepository` aggregate, a field-for-field
twin of `Supplier`. It carries no money columns and will not grow any: the
company pays the store in full at sale time (PRD §4.7).

## The two documents that only take goods away

`SupplierReturn` and `WriteOff` share `RemovalLine`
(`domain/entities/removal_line.py`) rather than declaring a line class
each: what a line may say is identical in both, so it is stated once, the
same split `Document` makes for the headers. They also share one poster.
`RemovalPoster` (`application/services/removal_posting.py`) takes each
through `send_back` or `write_off`, differing in three values — the
movement type, where the handset lands, and which financial category
carries the amount. The **sign** is not a fourth: it is read from
`TransactionType.ordinary_sign`, so the service holds no second opinion
about §4.6's convention.

They stay two documents rather than one with a flag because §5.10 reports
them in different columns, and `domain/services/projection.py` sends them
to different terminal statuses. `tests/api/test_verify_cli.py`'s
`TestM6DocumentsReconcile` is what actually holds the signs honest: it
confirms each document against a real store and asserts
`verify-financials` still finds nothing, which it can only do if the value
booked matches the value removed.

Neither payload carries money (`application/models/supplier_return.py`).
What a removal is worth is the goods' book value — a unit's own cost or a
replayed cost pool — and computing it needs repository reads, which a
`from_entity` must not do. Storing it on the line instead would be a
second opinion about a figure the financial ledger already holds.

`RemovalLine.imei` is carried by the repository's join, the way `currency`
and `tracking_type` already are, and the join onto `device_units` is outer
because a quantity line names no handset. It is on the line rather than left
to the caller because `DELETE /{id}/scan/{imei}` is keyed by IMEI, so a
screen holding only `device_unit_id` could neither name what it is showing
nor remove a mis-scanned phone.

## The Stock Count has four steps and three statuses

`StockCount` is opened against a location, scanned, **closed**, and
confirmed. That is one step more than `DocumentStatus` has values, and the
fourth lives on the entity as `closed_at`/`closed_by` rather than as a
shared enum member: only a count has a close, and a fourth `DocumentStatus`
would give every Purchase Order a state it can never enter.
`assert_countable()` is the guard, and a closed count is still a `DRAFT` —
it has found discrepancies and applied none.

**FR-6.3's three lists are derived, not stored.** `StockCountUnit` carries
two booleans (`expected`, `scanned`) and computes `outcome`; a scan sets
the flag on a row the opening snapshot already wrote, so *matched* never
has to be written twice. `StockCountData` is therefore the discrepancy
report itself, and there is no separate report endpoint.

**The snapshot is taken when the count opens** (`open_stock_count.py`), not
computed at close. A count takes hours while sales keep happening, and
recomputing at close would report a phone sold mid-count as missing.

**`CountPoster` (`application/services/count_posting.py`) adjusts only what
the ledger actually gets wrong, and both halves of that are easy to get
backwards.** The snapshot is hours old by the time anyone confirms, so a
row's label and the ledger's current picture can disagree:

- An *unexpected* handset books money **only if the store was not already
  holding it**. One found on another shelf is a location correction — it
  was bought once and its cost booked then — so the goods move and the money
  does not.
- A *missing* handset books nothing **if it has already left through a
  documented path**, sold or returned while the count sat open. It is not
  missing, it is sold, and the ledger has said so already.
- An accessory line adjusts against the **live level**, not against
  `StockCountLine.delta`. That field is the *report* figure — what the
  counter found against what the books said hours ago — and posting it
  would re-book whatever sold in between.

Get any of them wrong and the same goods are counted twice. For the two
serialized cases FR-10.7's reconciliation is what surfaces it, which is why
`tests/api/test_verify_cli.py`'s `TestM6DocumentsReconcile` pins them down
against a real store rather than asserting on rows. The accessory case is
worse: no verifier catches it at all, because `stock_levels` would be a
faithful projection of a movement that should never have been written.

`CountPoster` also has the one case no other poster has: a scanned IMEI the
store has no row for at all, which confirming must *create*. It enters `USED` with no asking price, and the
condition is not an operator choice — `PriceResolver` only refuses to quote
a catalog price for a unit that is not `NEW`, so a settable condition would
let a count produce exactly the silently-mispriced handset §4.5b exists to
prevent. `COUNT_ADJUSTMENT`'s sign is computed from what was found rather
than read from the enum, because `ordinary_sign` is deliberately `0` there
(§4.6): a count finds surplus as readily as shortage.

A surplus with nothing to value it — a surprise nobody costed, or an
accessory at a location whose pool is empty — is refused rather than booked
at zero. `verify-financials` sums on-hand `acquisition_cost` to recompute
inventory value, so a zero would either drift or dilute every later
weighted average.

`GET /invoices/{id}/pdf` renders on demand and stores nothing
(`infrastructure/documents/invoice_pdf.py`). A confirmed document is
immutable and its lines carry their own snapshots, so the file is
byte-stable; a stored blob would be a cache of something that cannot
change. A `DRAFT` is refused with `DocumentNotConfirmedError`, and a
`CANCELLED` invoice still prints, marked as such. The renderer reaches no
repository — the caller passes in what each line reads as — and
`APEXWMS_PDF_FONT_PATH` swaps fpdf2's Latin-1 core font for a Unicode face
where a store needs Cyrillic.
