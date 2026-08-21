/**
 * What every document shares, regardless of which one it is.
 *
 * The `DRAFT → CONFIRMED → CANCELLED` lifecycle (PRD §4.4) is one rule
 * across purchase orders, goods receipts and sales invoices alike, so it
 * lives here rather than in any one of their modules.
 */

import type { DocumentStatus } from "@/lib/types";

/** A document is freely editable while DRAFT, and immutable after (§4.4). */
export function isEditable(status: DocumentStatus): boolean {
  return status === "draft";
}
