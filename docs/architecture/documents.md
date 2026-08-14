# Documents (PRD §4.4, §5.3 — M4)

The first two of the six document types exist: `PurchaseOrder` and
`GoodsReceipt`. Both extend `Document` (`domain/entities/document.py`),
which owns §4.4's one lifecycle — `DRAFT → CONFIRMED → CANCELLED`, terminal
at both ends — and nothing else. **What makes a particular document
confirmable is its own business**: a subclass overrides `confirm()` to
state its invariants and delegates the state change upward. The four still
to come (M5's invoice, M6's return/count/write-off) inherit the same base.

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
