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
  /** Null for a walk-in. */
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

/** One row of FR-9.7's report. `difference` is signed, in both directions. */
export type PriceDeviation = {
  invoiceId: string;
  invoiceNumber: string;
  confirmedAt: string;
  customerId: string | null;
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
  priceNote: string | null;
};
