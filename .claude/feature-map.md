# Feature map

Every feature area below is CQRS: one file per operation under
`backend/src/application/commands/` or `queries/`, one response payload per
file under `application/models/` (`.claude/rules/backend/cqrs-response-models.md`),
and a `Handler` DI-registered in `di/providers/handlers.py`. Paths are
relative to `backend/src/application/` unless noted.

## Auth & identity

Login, session refresh, invitations, and the platform side of who a user
is. Deep dive: [multi-tenancy.md](../docs/architecture/multi-tenancy.md).

- Commands: `commands/login.py`, `refresh_tokens.py`, `change_password.py`,
  `invite_user.py`, `accept_invite.py`, `change_user_role.py`
- Queries: `queries/get_me.py`, `list_users.py`
- Models: `models/login.py`, `auth_tokens.py`, `invite_user.py`,
  `accept_invite.py`, `me.py`, `employee.py`
- Services: `services/claims.py` (`ClaimsFactory`), `token_issuer.py`
- Security infra: `infrastructure/security/current_user_accessor.py`,
  `infrastructure/current_tenant_accessor.py` (see
  [tenant-resolution.md](../docs/architecture/tenant-resolution.md))

## Platform & tenancy

SuperAdmin provisioning and per-store settings. Deep dive:
[multi-tenancy.md](../docs/architecture/multi-tenancy.md).

- Commands: `commands/create_tenant.py`, `create_superadmin.py`,
  `update_tenant_settings.py`
- Queries: `queries/get_tenant_settings.py`
- Models: `models/create_tenant.py`, `create_superadmin.py`,
  `tenant_settings.py`
- Services: `services/slugs.py`, `timezones.py`
- CLI entry points: `infrastructure/cli.py` (`apexwms create-tenant`,
  `create-superadmin`)

## Catalog (M2)

Products, locations, suppliers, customers — the `TenantCrudRepository`
aggregates. M5b's `CreditCompany` is a fifth one, listed under credit
sales. Deep dive:
[ledgers.md#repository-bases](../docs/architecture/ledgers.md).

- Commands: `commands/create_product.py`, `update_product.py`,
  `create_location.py`, `update_location.py`, `create_supplier.py`,
  `update_supplier.py`, `create_customer.py`, `update_customer.py`
- Queries: `queries/get_product.py`, `list_products.py`, `get_location.py`,
  `list_locations.py`, `get_supplier.py`, `list_suppliers.py`,
  `get_customer.py`, `list_customers.py`
- Models: `models/product.py`, `location.py`, `supplier.py`, `customer.py`

## Ledgers & device unit pricing (M3)

Stock/financial ledgers and everything that reprices a unit or product.
Deep dive: [ledgers.md](../docs/architecture/ledgers.md),
[value-objects.md](../docs/architecture/value-objects.md).

- Commands: `commands/reprice_device_unit.py`, `reprice_device_units.py`,
  `change_device_unit_condition.py`
- Queries: `queries/get_device_unit.py`,
  `get_device_unit_price_history.py`, `get_product_price_history.py`
- Models: `models/device_unit.py`, `price_history.py`,
  `currency_subtotal.py`
- Services: `services/ledger.py` (`LedgerPoster`),
  `verification/projections.py` + `verification/reconciliation.py`
  (`apexwms verify-projections`/`verify-financials`),
  `device_unit_repricer.py`, `product_repricer.py`, `device_unit_loader.py`,
  `sale_price.py`
- Domain: `domain/services/pricing.py` (`PriceResolver`),
  `projection.py` (`UnitProjector`), `domain/value_objects/cost_pool.py`,
  `currency_totals.py` (`CurrencyTotals` — the one way money is added to a
  per-currency total, used by the reconciler and every M8 report)

## Purchase orders & goods receipts (M4)

Inbound documents: PO to goods receipt to IMEI scan-in to confirm. Deep
dive: [documents.md](../docs/architecture/documents.md).

- Commands: `commands/create_purchase_order.py`,
  `confirm_purchase_order.py`, `cancel_purchase_order.py`,
  `create_goods_receipt.py`, `confirm_goods_receipt.py`,
  `cancel_goods_receipt.py`, `scan_receipt_unit.py`,
  `unscan_receipt_unit.py`, `price_receipt_unit.py`
- Queries: `queries/get_purchase_order.py`, `list_purchase_orders.py`,
  `get_goods_receipt.py`, `list_goods_receipts.py`
- Models: `models/purchase_order.py`, `goods_receipt.py`, `received_unit.py`,
  `scan_result.py`
- Services: `services/document_numbering.py` (`DocumentNumberer`),
  `document_lines.py`, `document_loader.py`, `receipt_posting.py`
  (`ReceiptPoster`)
- Domain: `domain/entities/document.py` (`Document` base lifecycle),
  `purchase_order.py`, `goods_receipt.py`

## Sales invoices (M5)

Outbound documents: open an invoice, scan to sell, override a line, confirm
to `SALE_REVENUE` + `COGS`, cancel to compensate, print. Deep dive:
[documents.md](../docs/architecture/documents.md).

- Commands: `commands/create_sales_invoice.py`, `scan_invoice_line.py`,
  `override_invoice_line_price.py`, `unscan_invoice_line.py`,
  `confirm_sales_invoice.py`, `cancel_sales_invoice.py`
- Queries: `queries/get_sales_invoice.py`, `list_sales_invoices.py`,
  `get_sales_invoice_pdf.py`
- Models: `models/sales_invoice.py`, `invoice_scan_result.py`
- Services: `services/invoice_posting.py` (`InvoicePoster` — where the
  price is resolved the second time), `services/cost_pools.py`
  (`CostPoolReader`, shared with `LedgerReconciler`)
- Persistence: `mappers/sales_invoice.py` (root + line sync),
  `specs/sales_invoice.py` (`SalesInvoiceById` / `ForWrite` / `Browse`),
  `persistence/tenant/queries/sales_invoice.py` (`SqlSalesInvoiceQueries` —
  every projection read)
- Domain: `domain/entities/sales_invoice.py`,
  `domain/services/pricing.py` (`PriceResolver`, FR-2.14)
- Rendering: port `application/ports/documents.py`, implementation
  `infrastructure/documents/invoice_pdf.py`
- Router: `presentation/routers/sales_invoices.py` (`/invoices`)

## Credit sales & customer debt (M5b)

`payment_type` on a sale, the credit-company reference list, som-denominated
store-credit debt and the append-only payments that settle it. Deep dive:
[documents.md](../docs/architecture/documents.md) for the terms on the
invoice, [ledgers.md](../docs/architecture/ledgers.md) for money-only
postings and `DocumentType.PAYMENT`.

- Commands: `commands/create_credit_company.py`, `update_credit_company.py`,
  `record_payment.py`, `reverse_payment.py`; the terms arrive on
  `commands/confirm_sales_invoice.py`'s payload
- Queries: `queries/get_credit_company.py`, `list_credit_companies.py`,
  `get_customer_account.py`, `list_debtors.py`
- Models: `models/credit_company.py`, `payment.py`, `customer_account.py`,
  `debtor.py`
- Carriers: `dtos/customer_debt.py` (`CreditInvoiceDebt`, `DebtorSummary` —
  the joined read rows `SqlSalesInvoiceQueries.credit_history_for` and
  `list_debtors` build)
- Services: `services/payment_posting.py` (`PaymentPoster` — the only
  writer of a payment, and the reason FR-11.7 is structural),
  `services/ledger.py`'s `post_money`, `services/verification/balances.py`'s
  `BalanceVerifier` (`apexwms verify-balances`)
- Domain: `domain/entities/payment.py`, `credit_company.py`,
  `domain/enums/payment_type.py`, `payment_method.py`
- Routers: `presentation/routers/credit_companies.py`, `payments.py`, plus
  `/invoices/{id}/payments`, `/customers/{id}/account` and
  `/reports/debtors` on their existing routers

## Customer returns (M10)

Goods coming back from a customer against one confirmed sale, and the money
going back with them. Deep dive:
[documents.md](../docs/architecture/documents.md)'s "The one that brings
goods back", [ledgers.md](../docs/architecture/ledgers.md) for why the cost
rides on a positive `COGS` and why the debt relief is a column.

- Commands: `commands/create_customer_return.py`,
  `scan_customer_return_line.py`, `unscan_customer_return_line.py`,
  `set_customer_return_refund.py` (FR-4.9c's restocking fee),
  `confirm_customer_return.py` (where the som debt relief arrives),
  `cancel_customer_return.py`
- Queries: `queries/get_customer_return.py`, `list_customer_returns.py`
- Models: `models/customer_return.py`
- Services: `services/customer_return_posting.py` (`CustomerReturnPoster` —
  the only writer of `SALES_RETURN_REFUND`), `customer_return_scanning.py`
  (`CustomerReturnScanner` — "did *this sale* sell it, and is any of it
  still un-returned"), `customer_balance.py` (`remaining_on` — the one
  Python statement of `debt − Σ payments − Σ relief`, whose SQL twin is
  `SqlSalesInvoiceQueries._relieved()`)
- Domain: `domain/entities/customer_return.py`,
  `domain/enums/customer_return_reason.py`; `MovementType.CUSTOMER_RETURN`,
  `TransactionType.SALES_RETURN_REFUND`, `DocumentType.CUSTOMER_RETURN`, and
  the `_STATUS_WHEN_GONE` entry in `domain/services/projection.py` that only
  a *cancelled* return reaches
- Persistence: `mappers/customer_return.py`, `specs/customer_return.py`
  (`CustomerReturnById` / `ForWrite` / `sForInvoice` / `Browse`), migration
  `0011_tenant_customer_returns.py`
- Router: `presentation/routers/customer_returns.py` (`/customer-returns`)
- Screens: `frontend/src/app/(app)/customer-returns/` — list, form, detail,
  plus `CustomerReturnLines.tsx` (the table that carries money, unlike
  `RemovalLinesTable`), `RefundModal.tsx` and `ConfirmReturnModal.tsx` (the
  som relief). `frontend/src/lib/customer-returns.ts` holds what is not JSX.
  `components/scan/ScanConsole.tsx` is shared with both removal documents

## Returns, counts & write-offs (M6)

The three remaining document types from §4.4. Deep dive:
[documents.md](../docs/architecture/documents.md) for the shared
`RemovalLine` and the count's fourth step,
[ledgers.md](../docs/architecture/ledgers.md) for what each adjustment is
valued at.

- Commands: `commands/create_supplier_return.py`,
  `scan_supplier_return_line.py`, `unscan_supplier_return_line.py`,
  `confirm_supplier_return.py`, `cancel_supplier_return.py`;
  `create_write_off.py`, `scan_write_off_line.py`,
  `unscan_write_off_line.py`, `confirm_write_off.py`, `cancel_write_off.py`;
  `open_stock_count.py` (the FR-6.1 snapshot),
  `scan_stock_count_unit.py`, `unscan_stock_count_unit.py`,
  `count_stock_count_line.py`, `close_stock_count.py`,
  `confirm_stock_count.py`, `cancel_stock_count.py`
- Queries: `queries/get_supplier_return.py`, `list_supplier_returns.py`,
  `get_write_off.py`, `list_write_offs.py`, `get_stock_count.py`,
  `list_stock_counts.py`
- Models: `models/supplier_return.py`, `write_off.py`, `stock_count.py`
  (which *is* FR-6.3's discrepancy report), `count_scan_result.py`
- Services: `services/removal_posting.py` (`RemovalPoster` — one service,
  two documents, sign read from `TransactionType.ordinary_sign`),
  `removal_scanning.py` (`RemovalScanner` — the checks both removal scans
  share), `count_posting.py` (`CountPoster` — the only one that creates a
  `DeviceUnit`), `cost_pools.py`'s `issue_value`
- Domain: `domain/entities/removal_line.py` (shared by both removal
  documents), `supplier_return.py`, `write_off.py`, `stock_count.py`,
  `domain/enums/supplier_return_reason.py`, `write_off_reason.py`,
  `count_outcome.py`
- Routers: `presentation/routers/supplier_returns.py`, `write_offs.py`,
  `stock_counts.py`

## Documents on paper (M7)

The three document types §5.8 says a store hands over, and the letterhead
they carry. Deep dive:
[documents.md](../docs/architecture/documents.md)'s "Three of them print".

- Commands: `commands/set_tenant_logo.py` (base64 in, magic bytes sniffed),
  and the text half on `update_tenant_settings.py`
- Queries: `queries/get_sales_invoice_pdf.py`, `get_purchase_order_pdf.py`,
  `get_supplier_return_pdf.py`, `get_tenant_logo.py`
- Models: `models/tenant_settings.py` (`hasLogo`, never the bytes)
- Carriers: `dtos/letterhead.py`, `tenant_logo.py`,
  `dtos/rendered_document.py` (bytes on their way to a raw `Response`)
- Rendering: ports in `application/ports/documents.py`;
  `infrastructure/documents/page.py` (`DocumentPage` — the shared page, and
  the `confirmed_at` creation date FR-8.3 rests on, plus
  `DocumentPageFactory` at APP scope), `invoice_pdf.py`,
  `purchase_order_pdf.py`, `supplier_return_pdf.py`
- Routers: `GET /{id}/pdf` on `sales_invoices.py`, `purchase_orders.py` and
  `supplier_returns.py`; `GET`/`PUT /settings/tenant/logo` on `settings.py`
- Tests: `tests/api/pdf_helpers.py`'s `pdf_text` inflates the content
  streams so a print test can assert the IMEI is really on the page
- Screens: `frontend/src/components/OpenPdfButton.tsx` (a plain anchor —
  same-origin proxy, httpOnly cookie), used by the invoice, purchase order
  and supplier return detail pages; `frontend/src/app/(app)/settings/page.tsx`
  (letterhead and logo); `frontend/src/lib/letterhead.ts` (the client-side
  type and size checks, as a courtesy)

## Reporting (M5, M5b, M8)

> The month-end close (M9) has its own section below.

Reads over what the documents already wrote, all read-only. Most sit
behind `Permission.Reporting.View`; the financial ledger takes
`Permission.FinancialLedger.View` and the debtor list
`Permission.CustomerAccount.ViewAll`, because §2.1 grades "what did we
move", "what did we earn" and "what is the whole book owed" as three
questions. Deep dive: [ledgers.md](../docs/architecture/ledgers.md)'s
"Reading them back".

- Queries: `queries/get_stock_on_hand.py` (FR-9.1),
  `get_device_trace.py` (FR-9.2 — the M8 demo),
  `get_sales_summary.py` (FR-9.3), `list_ageing.py` (FR-9.4),
  `list_movements.py` (FR-9.5), `list_needs_pricing.py` (FR-9.6),
  `list_price_deviations.py` (FR-9.7), `list_below_cost.py` (FR-2.19),
  `list_financial_ledger.py` (FR-10.3), `list_debtors.py` (FR-11.10)
- Models: `models/stock_on_hand.py`, `device_trace.py`, `sales_summary.py`,
  `ageing.py`, `movement_log.py`, `needs_pricing.py`,
  `financial_ledger.py`, `price_deviation.py`, `below_cost.py`, `debtor.py`
- Carriers: `dtos/stock_on_hand.py`, `unit_trace.py`, `sales_summary.py`,
  `ageing.py`, `ledger_log.py` (both raw logs share one row shape),
  `needs_pricing.py`, `price_deviation.py`, `below_cost.py` — the joined
  read rows the repositories build
- Services: `services/stock_on_hand.py` (`StockOnHandReader` — merges the
  two tracking types and values accessories through `CostPoolReader`),
  `services/unit_trace.py` (`UnitTraceAssembler` — three append-only
  sources into one timeline)
- Sorting: `application/sorting.py` — each report's own fixed enum.
  `PagedQuery` deliberately has no generic `order_by`
- Reporting reads: query services per aggregate table, behind Protocol
  ports in `application/ports/tenant/queries.py` —
  `SqlSalesInvoiceQueries` (deviations, debtors, `sales_of_unit`,
  `credit_history_for`, `total_debt`), `SqlStockMovementQueries`
  (`list_page` / `trace_for_unit` / `units_sold` / `net_quantity`),
  `SqlFinancialTransactionQueries` (`totals_by_type` / `sales_totals` /
  `list_page`), `SqlGoodsReceiptQueries` (`origin_of`, `supplier_of`,
  `received_quantities`), `SqlStockOnHandQueries` (`serialized_totals` /
  `accessories_on_hand`), `SqlDeviceUnitQueries` (`list_ageing` /
  `list_needs_pricing`), `SqlBelowCostQueries` (`list_below_cost` — rebuilds
  the weighted-average cost in SQL). `queries/document_ref.py` turns a
  `(document_type, document_id)` pair into its number for both logs
- `services/below_cost.py` (`BelowCostChecker`) — called from
  `commands/confirm_goods_receipt.py` and `commands/confirm_sales_invoice.py`
  to flag an accessory whose average cost has reached the catalog price
  (FR-2.19); non-blocking, returned on the confirm response
- Routers: `presentation/routers/reports.py` (`/reports`), plus
  `GET /device-units/{id}/trace` on `device_units.py`
- Screens: `frontend/src/app/(app)/reports/` — one folder per report
  (`stock-on-hand/`, `trace/`, `movements/`, `sales-summary/`, `ageing/`,
  `needs-pricing/`, `price-deviations/`, `below-cost/`, `financial-ledger/`,
  `debtors/`),
  plus `components/DeviceTraceTimeline.tsx` (the FR-9.2 timeline, also shown
  on the unit page) and `reports/BulkRepriceModal.tsx` (FR-2.21, the write
  the ageing and needs-pricing worklists exist to feed)

## Month-End Report (M9)

The period close (FR-10.4 to FR-10.10), behind
`Permission.FinancialLedger.View` — it is money end to end, so nothing in
it is trimmed by `Cost.View` the way the other reports are. Deep dive:
[ledgers.md](../docs/architecture/ledgers.md)'s "Valuing the ledgers at a
past instant" and "The month-end close".

- Queries: `queries/get_month_end_report.py` (FR-10.4),
  `get_month_end_report_pdf.py` (FR-10.9)
- Models: `models/month_end.py` — the whole payload, one nested
  `CamelModel` per block
- Carriers: `dtos/month_end.py` (`MonthEndReport`, `AccrualFigures`,
  `DebtMovement`), `dtos/period.py`, `dtos/inventory_value.py`,
  `dtos/financing_split.py`
- Services: `services/month_end.py` (`MonthEndReporter` — the whole
  report), `services/period.py` (`PeriodResolver` — FR-10.8's month in the
  tenant's timezone), `services/inventory_value.py` (`InventoryValuer` —
  on-hand value at an instant, by location), and `inventory_effect` in
  `services/cost_pools.py`, shared with `verify-financials`
- Reporting reads: `SqlMonthEndQueries`
  (`infrastructure/persistence/tenant/queries/month_end.py`) — `debt_at`,
  `debt_booked_between`, `debt_voided_between`, `sales_by_financing`; plus
  `SqlStockMovementQueries.serialized_value_at` and the `as_of` cutoff on
  `MovementsForPair` / `TransactionsForPair`
- Renderer: `infrastructure/documents/month_end_pdf.py`, on
  `DocumentPage.start_at` / `title` — the one printed page that is not a
  `Document`
- Routers: `GET /reports/month-end` and `/reports/month-end/pdf` on
  `presentation/routers/reports.py`
- Tests: `tests/application/test_month_end.py` (timezone boundaries and the
  debt-movement identity), `tests/api/test_month_end_api.py` (the §10 demo
  and the two reconciliations against a real database)
- Screens: `frontend/src/app/(app)/reports/month-end/` — `MonthEndReport.tsx`
  (the month picker and the reconciliation banner), `MonthEndStockAndSales.tsx`
  (the stock-value bridge and the sales/margin table — each a grid of figures
  against the currencies the period touched, the bridge re-signed for the
  shelf) plus `MonthEndDebtAndFinancing.tsx` (the som debt movement and the
  financing split). `frontend/src/lib/month-end.ts` holds what is not JSX —
  the default month, the `YYYY-MM` round trip, the currency columns,
  `INVENTORY_SIGN` / `stockMoveMinor` (the frontend twin of the backend's
  sign map), and `formatPeriod`, which renders the window in the **store's**
  timezone rather than the
  browser's (FR-10.8). The PDF reuses `components/OpenPdfButton.tsx`

## Scanning & lookup

One endpoint resolving a scanned string to a handset or a catalog row
(PRD §6, FR-7.1) — the only route into a device unit from a UI, since a
handset is found by its IMEI and never by a UUID anyone could type.

- Queries: `queries/scan_lookup.py`
- Models: `models/scan_lookup.py` (`ScanKind` + the two existing payloads,
  so cost shaping comes from `DeviceUnitData` unchanged)
- Router: `presentation/routers/scan.py`

## Cross-cutting ports (used by every feature area)

`application/ports/`: `clock.py`, `provisioning.py`, `repository.py`
(`AppendOnlyRepository`), `security.py`, `tenancy.py`, `uow.py`, plus
`master/` and `tenant/` for the two database-specific repository port
groups.
