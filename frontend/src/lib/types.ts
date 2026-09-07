/**
 * The slice of the backend's wire contract this frontend actually uses.
 *
 * Hand-written rather than generated so the app typechecks without a running
 * backend. `pnpm gen:api` regenerates the full OpenAPI schema into
 * src/lib/schema.d.ts if you ever want to cross-check these by hand.
 *
 * Everything is camelCase: every backend model inherits CamelModel.
 */

export type TenantRole =
  | "tenant.owner"
  | "tenant.manager"
  | "tenant.storekeeper"
  | "tenant.seller";

export const TENANT_ROLES: TenantRole[] = [
  "tenant.owner",
  "tenant.manager",
  "tenant.storekeeper",
  "tenant.seller",
];

export type AppRole = "app.superadmin" | "app.admin";

export type TrackingType = "serial" | "quantity";

export type Currency = "UZS" | "USD";

/** GET /auth/me */
export type Me = {
  userId: string;
  email: string;
  fullName: string;
  mustChangePassword: boolean;
  tenantId?: string | null;
  role?: TenantRole | null;
  appRoles: AppRole[];
  permissions: string[];
};

/** What POST /api/auth/login hands back to the browser — never the tokens. */
export type LoginResult = {
  mustChangePassword: boolean;
  tenantId: string | null;
  role: TenantRole | null;
  appRoles: AppRole[];
};

export type Product = {
  id: string;
  sku: string;
  name: string;
  brand: string | null;
  model: string | null;
  trackingType: TrackingType;
  currency: Currency;
  barcode: string | null;
  /** Exact major units as a string, e.g. "599.00". Never a float. */
  defaultSalePrice: string | null;
  /** The integer actually stored. Meaningless without `currency`. */
  defaultSalePriceMinor: number | null;
  isActive: boolean;
};

export type Location = {
  id: string;
  name: string;
  isActive: boolean;
};

export type Supplier = {
  id: string;
  name: string;
  contactName: string | null;
  phone: string | null;
  email: string | null;
  isActive: boolean;
};

export type Customer = {
  id: string;
  fullName: string;
  phone: string | null;
  isActive: boolean;
};

/** GET /users — note this one is NOT paged. */
export type Employee = {
  id: string;
  email: string;
  fullName: string;
  role: TenantRole;
  isActive: boolean;
};

/** POST /users/invite */
export type InviteResult = {
  invitationId: string;
  /** Wire format "{invitationId}.{secret}". No email is sent. */
  token: string;
  expiresAt: string;
};

export type TenantSettings = {
  timezone: string;
  /** The letterhead a printed document carries (FR-8.1). */
  businessName: string | null;
  address: string | null;
  /** The image itself is served as bytes from /settings/tenant/logo. */
  hasLogo: boolean;
};

/* ------------------------------------------------------------------ *
 * M4 — inbound documents, handsets, scanning
 * ------------------------------------------------------------------ */

/** Every document shares one lifecycle (PRD §4.4). */
export type DocumentStatus = "draft" | "confirmed" | "cancelled";

/** Where a Goods Receipt's goods came from (FR-3.3b). */
export type AcquisitionSource = "supplier" | "trade_in";

/** Ordered vs. received, derived on read (FR-3.9). */
export type Fulfilment = "pending" | "partial" | "complete";

/** Decides whether a unit may inherit the catalog price (FR-2.14). */
export type DeviceCondition = "new" | "refurbished" | "used";

export type DeviceStatus =
  | "in_stock"
  | "reserved"
  | "sold"
  | "returned_to_supplier"
  | "written_off"
  | "receipt_cancelled";

/**
 * One document total, in one currency. A document carries a list of these —
 * never a combined figure, because §4.5 rule 4 leaves no field for a caller
 * to add 500 cents to 30 000 so'm in.
 */
export type CurrencySubtotal = {
  currency: Currency;
  /** Exact major units as a string, e.g. "599.00". Never a float. */
  amount: string;
  amountMinor: number;
};

/**
 * Cost fields are typed optional because the server *omits* them without
 * `Permission.Cost.View` (FR-1.7) — it does not send them as null.
 */
export type PurchaseOrderLine = {
  id: string;
  productId: string;
  quantity: number;
  trackingType: TrackingType;
  currency: Currency;
  /** Null until someone prices the line; the order cannot be confirmed so. */
  unitCost: string | null;
  unitCostMinor: number | null;
  totalCost: string | null;
  totalCostMinor: number | null;
  receivedQuantity: number;
};

export type PurchaseOrder = {
  id: string;
  number: string;
  status: DocumentStatus;
  supplierId: string;
  note: string | null;
  createdBy: string;
  createdAt: string;
  confirmedAt: string | null;
  cancelledAt: string | null;
  lines: PurchaseOrderLine[];
  subtotals: CurrencySubtotal[];
  fulfilment: Fulfilment;
};

/** One handset scanned onto an open receipt. */
export type ReceivedUnit = {
  id: string;
  imei: string;
  imei2: string | null;
  serialNumber: string | null;
  condition: DeviceCondition;
  currency: Currency;
  askingPrice: string | null;
  askingPriceMinor: number | null;
  /** Not NEW and unpriced — exactly what FR-3.10 refuses the confirm over. */
  needsAskingPrice: boolean;
  /** --- Permission.Cost.View only --- */
  acquisitionCost?: string | null;
  acquisitionCostMinor?: number | null;
  /** A formatted string, never a number: it enters no total (FR-3.4d). */
  cashPaid?: string | null;
};

/**
 * One accessory whose weighted-average cost has caught up with its catalog
 * price. Returned only on the confirm response, empty on every other read.
 */
export type BelowCostAlert = {
  productId: string;
  sku: string;
  catalogPrice: string;
  catalogPriceMinor: number;
  averageUnitCost: string;
  averageUnitCostMinor: number;
};

export type GoodsReceiptLine = {
  id: string;
  productId: string;
  quantity: number;
  trackingType: TrackingType;
  currency: Currency;
  scannedCount: number;
  units: ReceivedUnit[];
  /** --- Permission.Cost.View only --- */
  unitCost?: string | null;
  unitCostMinor?: number | null;
};

export type GoodsReceipt = {
  id: string;
  number: string;
  status: DocumentStatus;
  acquisitionSource: AcquisitionSource;
  supplierId: string | null;
  customerId: string | null;
  purchaseOrderId: string | null;
  locationId: string;
  note: string | null;
  createdBy: string;
  createdAt: string;
  confirmedAt: string | null;
  cancelledAt: string | null;
  lines: GoodsReceiptLine[];
  /** --- Permission.Cost.View only; empty otherwise --- */
  subtotals: CurrencySubtotal[];
  /** Populated only on the confirm response; empty on every GET. */
  belowCostAlerts: BelowCostAlert[];
};

/** What one beep of the scanner returns (PRD §6). */
export type ScanResult = {
  lineId: string;
  scannedCount: number;
  expectedCount: number;
  unit: ReceivedUnit;
};

export type DeviceUnit = {
  id: string;
  imei: string;
  imei2: string | null;
  serialNumber: string | null;
  productId: string;
  sku: string;
  productName: string;
  status: DeviceStatus;
  condition: DeviceCondition;
  locationId: string | null;
  currency: Currency;
  askingPrice: string | null;
  /**
   * The price it would sell at, or null where the resolution rule refuses
   * (FR-2.14). Null is the counter's cue that someone must price it — it is
   * never zero and never the catalog price of a used handset.
   */
  resolvedPrice: string | null;
  resolvedPriceMinor: number | null;
  createdAt: string;
  /** --- Permission.Cost.View only --- */
  acquisitionCost?: string | null;
  acquisitionCostMinor?: number | null;
  cashPaid?: string | null;
};

/** One row of either price log (§4.5b). */
export type PriceChange = {
  id: string;
  occurredAt: string;
  /** Null on the first row: where pricing started, not a gap. */
  oldPrice: string | null;
  newPrice: string;
  oldPriceMinor: number | null;
  newPriceMinor: number;
  currency: Currency;
  reason: string | null;
  userId: string;
};

/**
 * GET /scan/lookup — the scanner does not know what it just read, so the
 * server states which kind it found (FR-7.1).
 */
export type ScanLookup = {
  kind: "device" | "product";
  device: DeviceUnit | null;
  product: Product | null;
};

/* ------------------------------------------------------------------ *
 * M5 — outbound sales
 * ------------------------------------------------------------------ */

/**
 * Nothing on an invoice is behind `Permission.Cost.View`: every figure is a
 * price the customer is being asked for, and a Seller must see all of them
 * (FR-1.7). So unlike a receipt's cost fields, none of these are optional —
 * the server always sends them.
 *
 * `resolvedPrice`, `chargedPrice` and `lineTotal` are null for the whole
 * life of a draft. That is the API telling the truth about FR-4.5b1: a
 * draft reserves no price, and resolution runs again at confirm. Only
 * `overridePrice` is set on a draft, because an override is a decision
 * somebody made rather than a figure the confirm produced.
 */
export type SalesInvoiceLine = {
  id: string;
  productId: string;
  /** Null on a quantity line — an accessory has no handset (§4.1). */
  deviceUnitId: string | null;
  quantity: number;
  trackingType: TrackingType;
  currency: Currency;
  resolvedPrice: string | null;
  resolvedPriceMinor: number | null;
  chargedPrice: string | null;
  chargedPriceMinor: number | null;
  lineTotal: string | null;
  lineTotalMinor: number | null;
  overridePrice: string | null;
  overridePriceMinor: number | null;
  /** Whoever last overrode the price, stamped then and not at confirm. */
  priceApprovedBy: string | null;
  priceNote: string | null;
  isDeviation: boolean;
};

export type SalesInvoice = {
  id: string;
  number: string;
  status: DocumentStatus;
  locationId: string;
  /** Null for a walk-in, and required once the sale is on store credit. */
  customerId: string | null;
  note: string | null;
  createdBy: string;
  createdAt: string;
  confirmedBy: string | null;
  confirmedAt: string | null;
  cancelledBy: string | null;
  cancelledAt: string | null;
  cancellationReason: string | null;
  lines: SalesInvoiceLine[];
  /** Empty on a draft, because a draft holds no prices. */
  subtotals: CurrencySubtotal[];
  /** --- M5b: how this sale is paid for. Every debt figure is som. --- */
  paymentType: PaymentType;
  creditCompanyId: string | null;
  contractRef: string | null;
  /** The som total the seller wrote. Null unless this is store credit. */
  debt: string | null;
  debtMinor: number | null;
  paidMinor: number;
  /** Som written off by confirmed customer returns against this sale (FR-4.9d). */
  relievedMinor: number;
  /**
   * `debt − Σ payments − Σ return relief`, recomputed on every read and never
   * stored. Zero on a cancelled sale, whose debt is void while its payments
   * stand (FR-11.11) — which makes `paidMinor` the refund figure at that point.
   */
  remainingMinor: number;
  payments: Payment[];
  /** Populated only on the confirm response; empty on every GET. */
  belowCostAlerts: BelowCostAlert[];
};

/**
 * One beep at the till. `resolvedPrice` is a quote for the counter to read
 * aloud — it is not written to the line and not reserved.
 */
export type InvoiceScanResult = {
  line: SalesInvoiceLine;
  lineCount: number;
  resolvedPrice: string;
  resolvedPriceMinor: number;
  productId: string;
  deviceUnitId: string | null;
};

/* ------------------------------------------------------------------ *
 * M5b — credit sales and customer debt
 * ------------------------------------------------------------------ */

/**
 * How a sale is paid for (§4.7). The goods and the revenue are identical in
 * all three cases; what differs is who still owes the store money afterwards
 * — nobody, nobody, the customer.
 */
export type PaymentType = "paid_in_full" | "credit_company" | "store_credit";

/** A label on how the money arrived, not a processed transaction (§1.4). */
export type PaymentMethod = "cash" | "transfer" | "card";

export const PAYMENT_METHODS: PaymentMethod[] = ["cash", "transfer", "card"];

export type CreditCompany = {
  id: string;
  name: string;
  contactName: string | null;
  phone: string | null;
  email: string | null;
  isActive: boolean;
};

/**
 * Money received against a store-credit sale. Always som, so `amount` and
 * `amountMinor` carry the same number — UZS has exponent 0.
 *
 * `amountMinor` is **signed**: a negative row is the compensating entry that
 * reverses an earlier payment (FR-11.8), and the original stays beside it.
 */
export type Payment = {
  id: string;
  salesInvoiceId: string;
  occurredAt: string;
  amount: string;
  amountMinor: number;
  method: PaymentMethod;
  userId: string;
  note: string | null;
  reversesPaymentId: string | null;
  isReversal: boolean;
};

/** One non-cash sale on a customer's account (FR-11.9). */
export type CreditInvoiceDebt = {
  invoiceId: string;
  invoiceNumber: string;
  status: DocumentStatus;
  paymentType: PaymentType;
  confirmedAt: string | null;
  /** Null on a financed sale: it opened no debt at all. */
  debt: string | null;
  debtMinor: number | null;
  paid: string;
  paidMinor: number;
  remaining: string;
  remainingMinor: number;
  creditCompanyId: string | null;
  contractRef: string | null;
  daysSinceSale: number | null;
};

/**
 * GET /customers/{id}/account. Two lists, deliberately separate: `openDebts`
 * is money the store is waiting for, `financedSales` is money a credit
 * company already paid. The balance counts only the first (§4.7).
 */
export type CustomerAccount = {
  customerId: string;
  fullName: string;
  phone: string | null;
  balance: string;
  balanceMinor: number;
  openDebts: CreditInvoiceDebt[];
  financedSales: CreditInvoiceDebt[];
};

/** One row of FR-11.10's debtor list, oldest open debt first. */
export type Debtor = {
  customerId: string;
  fullName: string;
  phone: string | null;
  balance: string;
  balanceMinor: number;
  oldestOpenAt: string;
  daysSinceOldest: number;
  openInvoiceCount: number;
};

/* ------------------------------------------------------------------ *
 * M6 — the three documents that correct what the shelf actually holds
 * ------------------------------------------------------------------ */

/** Why goods came back from a customer (FR-4.9). */
export type CustomerReturnReason =
  | "defective"
  | "not_as_expected"
  | "wrong_item"
  | "warranty"
  | "other";

export const CUSTOMER_RETURN_REASONS: CustomerReturnReason[] = [
  "defective",
  "not_as_expected",
  "wrong_item",
  "warranty",
  "other",
];

/** Why goods are going back to the supplier (FR-5.1). */
export type SupplierReturnReason = "defective" | "unsold" | "wrong_item" | "other";

export const SUPPLIER_RETURN_REASONS: SupplierReturnReason[] = [
  "defective",
  "unsold",
  "wrong_item",
  "other",
];

/** Why stock is being destroyed or given up on (FR-6.5). */
export type WriteOffReason = "damage" | "loss" | "theft" | "other";

export const WRITE_OFF_REASONS: WriteOffReason[] = ["damage", "loss", "theft", "other"];

/**
 * What a count found for one handset (FR-6.3). Derived by the server from
 * two booleans, never stored: expected and scanned is matched, expected and
 * not scanned is missing, scanned and not expected is unexpected.
 */
export type CountOutcome = "matched" | "missing" | "unexpected";

/**
 * A line on either removal document. The two share one shape because what a
 * line may say is identical in both — only the header differs.
 *
 * Neither payload carries money. What a removal is worth is the goods' book
 * value, which the financial ledger holds and a `from_entity` must not read.
 */
export type RemovalLine = {
  id: string;
  productId: string;
  /** Null on a quantity line — an accessory names no handset. */
  deviceUnitId: string | null;
  /**
   * Null on a quantity line. Present rather than only the unit id because
   * unscanning names the IMEI: the operator is holding the phone, not its
   * primary key.
   */
  imei: string | null;
  quantity: number;
  currency: Currency;
  trackingType: TrackingType;
};

export type SupplierReturn = {
  id: string;
  number: string;
  status: DocumentStatus;
  supplierId: string;
  locationId: string;
  reason: SupplierReturnReason;
  note: string | null;
  createdBy: string;
  createdAt: string;
  confirmedAt: string | null;
  cancelledAt: string | null;
  cancellationReason: string | null;
  lines: RemovalLine[];
  lineCount: number;
};

/**
 * One line of a customer return: the goods, and what is being paid back.
 *
 * Carries money where a `RemovalLine` does not, and that is the difference
 * between the documents: goods go back to a supplier at their book value,
 * but a customer is paid back a price somebody agreed to.
 */
export type CustomerReturnLine = {
  id: string;
  salesInvoiceLineId: string;
  productId: string;
  /** Null on a quantity line — an accessory names no handset. */
  deviceUnitId: string | null;
  /** Null on a quantity line. Unscanning names the IMEI, not the unit id. */
  imei: string | null;
  quantity: number;
  /** What the sale sold, so the screen can offer "return all". */
  soldQuantity: number;
  currency: Currency;
  trackingType: TrackingType;
  /** The ceiling: a refund never goes above what the sale charged. */
  chargedPriceMinor: number;
  refundPriceMinor: number;
  refundPrice: string;
  lineTotalMinor: number;
  isReduced: boolean;
  refundApprovedBy: string | null;
  refundNote: string | null;
};

/** Goods coming back from a customer against one confirmed sale (§5.4b). */
export type CustomerReturn = {
  id: string;
  number: string;
  status: DocumentStatus;
  salesInvoiceId: string;
  customerId: string | null;
  locationId: string;
  reason: CustomerReturnReason;
  /**
   * Som, and never a conversion of the subtotals: a store-credit debt is
   * written directly in som, so the relief against it is too (§4.7).
   */
  debtReliefMinor: number | null;
  note: string | null;
  createdBy: string;
  createdAt: string;
  confirmedAt: string | null;
  cancelledAt: string | null;
  cancellationReason: string | null;
  lines: CustomerReturnLine[];
  subtotals: CurrencySubtotal[];
  lineCount: number;
};

/** A write-off is a supplier return that names no counterparty. */
export type WriteOff = {
  id: string;
  number: string;
  status: DocumentStatus;
  locationId: string;
  reason: WriteOffReason;
  note: string | null;
  createdBy: string;
  createdAt: string;
  confirmedAt: string | null;
  cancelledAt: string | null;
  cancellationReason: string | null;
  lines: RemovalLine[];
  lineCount: number;
};

/**
 * One handset on a count: a row the opening snapshot wrote, or one a scan
 * added because nobody expected it.
 *
 * The cost fields are typed optional because the server *omits* them without
 * `Permission.Cost.View` (FR-1.7) — it does not send them as null. So an
 * absent cost means "not permitted to know", not "not priced".
 */
export type StockCountUnit = {
  id: string;
  imei: string;
  /** Null for a handset the store has no row for at all. */
  deviceUnitId: string | null;
  productId: string | null;
  expected: boolean;
  scanned: boolean;
  outcome: CountOutcome;
  /** Unknown to the store entirely — confirming has to create it (FR-6.4b). */
  isSurprise: boolean;
  /** --- Permission.Cost.View only --- */
  acquisitionCost?: string | null;
  acquisitionCostMinor?: number | null;
};

/**
 * One accessory level on a count.
 *
 * `countedQuantity` is null until somebody states a figure, and null is not
 * zero: a shelf nobody looked at and a shelf found empty are different
 * findings, and only the second books a loss.
 */
export type StockCountLine = {
  id: string;
  productId: string;
  expectedQuantity: number;
  countedQuantity: number | null;
  /** Zero while `countedQuantity` is null. The report figure, not the posting. */
  delta: number;
};

/**
 * A count is opened, scanned, **closed**, then confirmed — one step more than
 * `DocumentStatus` has values. The fourth lives here as `closedAt`, because
 * only a count has a close, and a closed count is still a `draft` that has
 * found discrepancies and applied none.
 *
 * This payload *is* FR-6.3's discrepancy report; there is no separate report
 * endpoint, because every row carries the outcome it computed.
 */
export type StockCount = {
  id: string;
  number: string;
  status: DocumentStatus;
  locationId: string;
  note: string | null;
  createdBy: string;
  createdAt: string;
  closedAt: string | null;
  confirmedAt: string | null;
  cancelledAt: string | null;
  cancellationReason: string | null;
  units: StockCountUnit[];
  lines: StockCountLine[];
  matchedCount: number;
  missingCount: number;
  unexpectedCount: number;
};

/**
 * One beep on a count. Deliberately narrow: a count holds the whole shelf,
 * and re-serializing hundreds of rows per trigger-pull would spend §6's
 * latency budget on rows nothing changed about.
 *
 * Exactly one of `unit` / `line` is set — an IMEI or a barcode, never both.
 */
export type CountScanResult = {
  unit: StockCountUnit | null;
  line: StockCountLine | null;
  matchedCount: number;
  missingCount: number;
  unexpectedCount: number;
};

/** One row of FR-9.7's report. `difference` is signed, in both directions. */
export type PriceDeviation = {
  invoiceId: string;
  invoiceNumber: string;
  confirmedAt: string;
  customerId: string | null;
  customerName: string | null;
  productId: string;
  productName: string;
  imei: string | null;
  currency: Currency;
  resolvedPrice: string;
  resolvedPriceMinor: number;
  chargedPrice: string;
  chargedPriceMinor: number;
  difference: string;
  differenceMinor: number;
  priceApprovedBy: string | null;
  priceApprovedByName: string | null;
  priceNote: string | null;
};

/* ------------------------------------------------------------------ *
 * M8 - reading the two ledgers back (PRD 5.9, 5.10)
 * ------------------------------------------------------------------ */

export type DocumentType =
  | "purchase_order"
  | "goods_receipt"
  | "sales_invoice"
  | "supplier_return"
  | "stock_count"
  | "write_off"
  | "payment";

export type MovementType =
  | "receipt"
  | "sale"
  | "supplier_return"
  | "count_adjustment"
  | "write_off";

export type TransactionType =
  | "purchase"
  | "sale_revenue"
  | "cogs"
  | "write_off_loss"
  | "supplier_return_credit"
  | "sales_return_refund"
  | "count_adjustment"
  | "payment_received";

export type StockGroupBy = "location" | "product" | "brand";

/**
 * One group of FR-9.1. `key` is a plain string whatever the grouping is,
 * because `groupBy` on the same row already says how to read it, and
 * `costValue` is absent without `Permission.Cost.View`.
 */
export type StockOnHandRow = {
  groupBy: StockGroupBy;
  key: string | null;
  label: string;
  /** Only present when grouping by product. */
  sku?: string | null;
  quantity: number;
  /** --- Permission.Cost.View only --- */
  costValue?: CurrencySubtotal[] | null;
};

export type AgeingSort = "age" | "markdowns";

/** One row of FR-9.4. Cost and implied margin are absent without `Cost.View`. */
export type AgeingRow = {
  deviceUnitId: string;
  imei: string;
  productId: string;
  sku: string;
  productName: string;
  brand: string | null;
  condition: DeviceCondition;
  locationId: string | null;
  locationName: string | null;
  since: string;
  daysInStock: number;
  currency: Currency;
  askingPrice: string | null;
  askingPriceMinor: number | null;
  markdownCount: number;
  /** --- Permission.Cost.View only --- */
  acquisitionCost?: string | null;
  acquisitionCostMinor?: number | null;
  impliedMargin?: string | null;
  impliedMarginMinor?: number | null;
};

/** Why FR-2.14 refuses to price the unit: its own price is missing, or the model's. */
export type NeedsPricingReason = "used_no_price" | "no_catalog_price";

/** One row of FR-9.6. No cost anywhere on it - pricing does not need one. */
export type NeedsPricingRow = {
  deviceUnitId: string;
  imei: string;
  productId: string;
  sku: string;
  productName: string;
  brand: string | null;
  condition: DeviceCondition;
  locationId: string | null;
  locationName: string | null;
  since: string;
  daysUnpriced: number;
  reason: NeedsPricingReason;
};

export type DeviceInventorySort = "received" | "imei" | "status";

/**
 * The status a caller filters the device-inventory list by. Mostly
 * `DeviceStatus`, plus `customer_returned` — a derived case, since a
 * customer-returned handset is `in_stock` again and no status records it.
 */
export type DeviceInventoryStatusFilter =
  | "in_stock"
  | "sold"
  | "customer_returned"
  | "returned_to_supplier"
  | "written_off"
  | "receipt_cancelled";

/** One row of the device-inventory list. Cost and margin are absent without `Cost.View`. */
export type DeviceInventoryRow = {
  deviceUnitId: string;
  imei: string;
  imei2: string | null;
  serialNumber: string | null;
  productId: string;
  sku: string;
  productName: string;
  brand: string | null;
  condition: DeviceCondition;
  status: DeviceStatus;
  wasCustomerReturned: boolean;
  locationId: string | null;
  locationName: string | null;
  since: string;
  daysInStock: number;
  currency: Currency;
  askingPrice: string | null;
  askingPriceMinor: number | null;
  resolvedPrice: string | null;
  resolvedPriceMinor: number | null;
  sourceDocumentType: DocumentType | null;
  sourceDocumentId: string | null;
  /** --- Permission.Cost.View only --- */
  acquisitionCost?: string | null;
  acquisitionCostMinor?: number | null;
  impliedMargin?: string | null;
  impliedMarginMinor?: number | null;
};

/**
 * One row of the below-cost report: an accessory whose average unit cost has
 * caught up with its catalog price. The decimal fields arrive pre-formatted
 * as strings; `*Minor` fields plus `currency` drive `formatMoney`.
 */
export type BelowCostRow = {
  productId: string;
  sku: string;
  productName: string;
  locationId: string;
  locationName: string;
  quantity: number;
  currency: Currency;
  catalogPrice: string;
  catalogPriceMinor: number;
  averageUnitCost: string;
  averageUnitCostMinor: number;
  shortfall: string;
  shortfallMinor: number;
};

/** One row of FR-9.5's stock ledger. `quantityDelta` is signed. */
export type MovementRow = {
  id: string;
  occurredAt: string;
  movementType: MovementType;
  quantityDelta: number;
  productId: string;
  sku: string;
  productName: string;
  deviceUnitId: string | null;
  imei: string | null;
  locationId: string;
  locationName: string;
  documentType: DocumentType;
  documentId: string;
  documentNumber: string | null;
  userId: string;
  userName: string | null;
  note: string | null;
};

/**
 * One row of FR-10.3's money ledger. Each row carries its own currency and
 * the report carries no total: a figure over these rows would be adding
 * so'm to dollars.
 */
export type FinancialLedgerRow = {
  id: string;
  occurredAt: string;
  txnType: TransactionType;
  currency: Currency;
  /** Signed per 4.6: negative is money out. */
  amount: string;
  amountMinor: number;
  productId: string | null;
  productName: string | null;
  deviceUnitId: string | null;
  imei: string | null;
  locationId: string | null;
  locationName: string | null;
  documentType: DocumentType;
  documentId: string;
  documentNumber: string | null;
  userId: string;
  userName: string | null;
  note: string | null;
};

/**
 * FR-9.3. `costOfGoods` and `returns` keep 4.6's sign and are negative;
 * `margin` is revenue plus returns plus cost, with nothing flipped.
 */
export type SalesFigures = {
  unitsSold: number;
  revenue: CurrencySubtotal[];
  costOfGoods: CurrencySubtotal[];
  /** Negative: money handed back to customers on returns (FR-4.9). */
  returns: CurrencySubtotal[];
  margin: CurrencySubtotal[];
};

export type LocationSales = {
  locationId: string | null;
  locationName: string | null;
  figures: SalesFigures;
};

export type SalesSummary = {
  fromDate: string | null;
  toDate: string | null;
  locations: LocationSales[];
  total: SalesFigures;
};

/** --- M9 month-end close (FR-10.4 to FR-10.10) --- */

/** The reporting month, resolved to two instants in the tenant's timezone. */
export type Period = {
  year: number;
  /** 1-12. */
  month: number;
  /** IANA name, e.g. "Asia/Tashkent". The window below only reads right in it. */
  timezone: string;
  start: string;
  /** Exclusive: a month runs `[start, end)` (FR-10.8). */
  end: string;
};

/** Null where the period sold nothing — 0.0 would read as breaking even. */
export type MarginPercent = {
  currency: Currency;
  percent: string | null;
};

/**
 * FR-10.5's accrual view. Every figure keeps 4.6's sign, which describes cash:
 * `purchases`, `costOfGoods`, `writeOffs` and `salesReturns` are negative
 * because money left. `margin` is net revenue (revenue plus the already
 * negative `salesReturns`) plus cost, with nothing flipped.
 */
export type AccrualFigures = {
  openingInventory: CurrencySubtotal[];
  purchases: CurrencySubtotal[];
  costOfGoods: CurrencySubtotal[];
  revenue: CurrencySubtotal[];
  /** Negative: money refunded to customers for goods brought back (FR-4.9). */
  salesReturns: CurrencySubtotal[];
  writeOffs: CurrencySubtotal[];
  supplierReturnCredits: CurrencySubtotal[];
  countAdjustments: CurrencySubtotal[];
  closingInventory: CurrencySubtotal[];
  margin: CurrencySubtotal[];
  marginPercent: MarginPercent[];
};

/** FR-10.6: where the closing value physically sits. */
export type LocationInventoryValue = {
  locationId: string;
  locationName: string | null;
  quantity: number;
  value: CurrencySubtotal[];
};

/**
 * Always som and always store-wide, even when the report is scoped to one
 * location: debt belongs to a customer, not a shelf (4.7). `voided` is what a
 * cancellation took off the books (FR-11.11) — without it the other four lines
 * do not add up.
 */
export type DebtMovement = {
  openingMinor: number;
  bookedMinor: number;
  collectedMinor: number;
  voidedMinor: number;
  /** Debt written off by confirmed customer returns against the sale (FR-4.9d). */
  relievedMinor: number;
  closingMinor: number;
  currency: Currency;
};

/** FR-10.5's last line: how the store actually sells. */
export type FinancingSplit = {
  paymentType: PaymentType;
  creditCompanyId: string | null;
  creditCompanyName: string | null;
  invoiceCount: number;
  revenue: CurrencySubtotal[];
};

/** One thing that does not add up (FR-10.7, FR-10.7b). */
export type Discrepancy = {
  subject: string;
  expected: string;
  found: string;
};

export type MonthEndReport = {
  period: Period;
  locationId: string | null;
  figures: AccrualFigures;
  closingByLocation: LocationInventoryValue[];
  debt: DebtMovement;
  financing: FinancingSplit[];
  /** False means the figures still render — the mismatch is surfaced beside
      them, never folded into them. */
  reconciles: boolean;
  discrepancies: Discrepancy[];
};

export type TraceEventKind =
  | "received"
  | "priced"
  | "sold"
  | "returned_to_supplier"
  | "written_off"
  | "count_adjustment";

/** Where the handset came from - a supplier, or a walk-in (FR-3.3b). */
export type TraceOrigin = {
  acquisitionSource: AcquisitionSource;
  supplierId: string | null;
  supplierName: string | null;
  customerId: string | null;
  customerName: string | null;
};

/** The line that sold it, with both prices and who approved the gap (FR-4.5f). */
export type TraceSale = {
  invoiceId: string;
  invoiceNumber: string;
  customerId: string | null;
  customerName: string | null;
  resolvedPrice: string | null;
  resolvedPriceMinor: number | null;
  chargedPrice: string | null;
  chargedPriceMinor: number | null;
  priceApprovedBy: string | null;
  priceApprovedByName: string | null;
  priceNote: string | null;
};

/**
 * One line of FR-9.2's timeline. Flat with a `kind` rather than a type per
 * event: the optional halves are what each kind carries.
 */
export type TraceEvent = {
  kind: TraceEventKind;
  occurredAt: string;
  userId: string;
  userName: string | null;
  note: string | null;
  documentType: DocumentType | null;
  documentId: string | null;
  documentNumber: string | null;
  locationId: string | null;
  locationName: string | null;
  /** PRICED only. A null `oldPrice` is the first pricing, not a cut. */
  oldPrice: string | null;
  oldPriceMinor: number | null;
  newPrice: string | null;
  newPriceMinor: number | null;
  origin: TraceOrigin | null;
  sale: TraceSale | null;
};

export type DeviceTrace = {
  unit: DeviceUnit;
  events: TraceEvent[];
};
