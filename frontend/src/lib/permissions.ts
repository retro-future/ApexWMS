/**
 * The permission strings this frontend gates on, mirrored from the backend's
 * domain/permissions/. Only the subset the shipped screens gate on is listed.
 *
 * Gate on permissions, never on role names: PRD §2.1's matrix is not
 * hierarchical, so there is no rank to compare. A Storekeeper can receive
 * goods but not sell; a Seller can sell but not receive. Neither outranks
 * the other.
 *
 * And remember the UI is not the enforcement point — the server checks every
 * request regardless. Hiding a button is a courtesy, not a permission.
 */

import type { Me } from "@/lib/types";

export const Permission = {
  Catalog: {
    View: "Permission.Catalog.View",
    Manage: "Permission.Catalog.Manage",
  },
  Location: {
    View: "Permission.Location.View",
    Manage: "Permission.Location.Manage",
  },
  Customer: {
    View: "Permission.Customer.View",
    Manage: "Permission.Customer.Manage",
  },
  Users: {
    View: "Permission.Users.View",
    Manage: "Permission.Users.Manage",
  },
  TenantSettings: {
    View: "Permission.TenantSettings.View",
    Manage: "Permission.TenantSettings.Manage",
  },
  Cost: {
    View: "Permission.Cost.View",
  },
  /** The rate the store quotes: everyone reads it, Owner and Manager set it. */
  ExchangeRate: {
    View: "Permission.ExchangeRate.View",
    Manage: "Permission.ExchangeRate.Manage",
  },
  PurchaseOrder: {
    View: "Permission.PurchaseOrder.View",
    Manage: "Permission.PurchaseOrder.Manage",
  },
  Receiving: {
    View: "Permission.Receiving.View",
    Manage: "Permission.Receiving.Manage",
  },
  Sales: {
    View: "Permission.Sales.View",
    Manage: "Permission.Sales.Manage",
  },
  Pricing: {
    Set: "Permission.Pricing.Set",
    /** Charging something other than what the system resolved (FR-4.5). */
    Override: "Permission.Pricing.Override",
  },
  /** Letting a phone leave before it has been paid for (§4.7). */
  CreditSale: {
    Create: "Permission.CreditSale.Create",
  },
  CreditCompany: {
    View: "Permission.CreditCompany.View",
    Manage: "Permission.CreditCompany.Manage",
  },
  Payment: {
    Record: "Permission.Payment.Record",
    /** Manager and Owner: taking money is the counter's job, unwinding it is not. */
    Reverse: "Permission.Payment.Reverse",
  },
  CustomerAccount: {
    View: "Permission.CustomerAccount.View",
    /** The whole book, not the customer in front of you (§2.1 note 1). */
    ViewAll: "Permission.CustomerAccount.ViewAll",
  },
  SupplierReturn: {
    View: "Permission.SupplierReturn.View",
    Manage: "Permission.SupplierReturn.Manage",
  },
  /**
   * Taking goods back from a customer. Owner/Manager only, like every other
   * operation that gives value back — a Seller sells and takes payments,
   * but does not hand money over (§2.1).
   */
  CustomerReturn: {
    View: "Permission.CustomerReturn.View",
    Manage: "Permission.CustomerReturn.Manage",
  },
  StockCount: {
    /** Open, scan, count and close. A Storekeeper holds this and nothing else in M6. */
    Run: "Permission.StockCount.Run",
    /** Applying the adjustments, which §5.6 keeps away from whoever ran the count. */
    Confirm: "Permission.StockCount.Confirm",
  },
  WriteOff: {
    /** There is no WriteOff.View — reading the list takes this too. */
    Manage: "Permission.WriteOff.Manage",
  },
  Reporting: {
    View: "Permission.Reporting.View",
  },
  /** The raw money ledger. Separate from Reporting.View: 2.1 grades "what did
      we move" and "what did we earn" as different questions. */
  FinancialLedger: {
    View: "Permission.FinancialLedger.View",
  },
  Document: {
    Cancel: "Permission.Document.Cancel",
  },
  Scan: {
    Lookup: "Permission.Scan.Lookup",
  },
} as const;

export function can(me: Me | null | undefined, permission: string): boolean {
  return Boolean(me?.permissions?.includes(permission));
}
