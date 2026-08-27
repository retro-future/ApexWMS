import type { DocumentType } from "@/lib/types";

/**
 * Where a ledger row's document lives on this frontend.
 *
 * A payment has no page of its own — it is a row on the customer's account —
 * so it resolves to null and the log renders its number as plain text rather
 * than a link that would 404.
 */
const PATHS: Record<DocumentType, string | null> = {
  purchase_order: "/purchase-orders",
  goods_receipt: "/receipts",
  sales_invoice: "/invoices",
  supplier_return: "/supplier-returns",
  stock_count: "/stock-counts",
  write_off: "/write-offs",
  payment: null,
};

export function documentHref(type: DocumentType, id: string): string | null {
  const path = PATHS[type];
  return path ? `${path}/${id}` : null;
}
