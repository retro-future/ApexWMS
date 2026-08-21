/**
 * What a draft receipt still needs before it can be confirmed.
 *
 * These are the same two checks the server runs at confirm — FR-3.8 (a
 * serialized line with fewer IMEIs than it declares) and FR-3.10 (a unit
 * that is not NEW and carries no asking price). Computing them client-side
 * is **not** an enforcement point: the server refuses regardless, and its
 * message names the offending rows. It exists so the screen can show the
 * gap while the operator is still standing at the shelf, rather than only
 * after they press Confirm.
 *
 * Pure functions over the payload, deliberately free of React, so they are
 * testable without a DOM.
 */

import type {
  Currency,
  GoodsReceipt,
  GoodsReceiptLine,
  PurchaseOrder,
  ReceivedUnit,
} from "@/lib/types";

export function isSerial(line: GoodsReceiptLine): boolean {
  return line.trackingType === "serial";
}

/** `7 of 10` — the running count §6 wants after every beep. */
export function scanProgress(line: GoodsReceiptLine): {
  scanned: number;
  expected: number;
  isComplete: boolean;
} {
  return {
    scanned: line.scannedCount,
    expected: line.quantity,
    isComplete: line.scannedCount >= line.quantity,
  };
}

/** FR-3.8: serialized lines still short of their declared quantity. */
export function shortLines(receipt: GoodsReceipt): GoodsReceiptLine[] {
  return receipt.lines.filter(
    (line) => isSerial(line) && line.scannedCount < line.quantity,
  );
}

/**
 * FR-3.10's worklist: scanned handsets that are not NEW and hold no asking
 * price. A Storekeeper sees this list and cannot act on it — pricing is
 * Owner/Manager (§2.1) — which is the point: they can go and fetch someone
 * who can, instead of discovering the refusal at confirm.
 */
export function unitsNeedingPrice(receipt: GoodsReceipt): ReceivedUnit[] {
  return receipt.lines.flatMap((line) =>
    line.units.filter((unit) => unit.needsAskingPrice),
  );
}

export type ConfirmBlockers = {
  shortLines: GoodsReceiptLine[];
  unpricedUnits: ReceivedUnit[];
  /** True when nothing is standing in the way of a confirm. */
  isReady: boolean;
};

export function confirmBlockers(receipt: GoodsReceipt): ConfirmBlockers {
  const short = shortLines(receipt);
  const unpriced = unitsNeedingPrice(receipt);
  return {
    shortLines: short,
    unpricedUnits: unpriced,
    isReady: short.length === 0 && unpriced.length === 0,
  };
}

export type ReferenceCost = { minor: number; currency: Currency };

/**
 * The PO's per-product price, offered back as a default at receiving. A
 * serialized `GoodsReceiptLine` carries no cost of its own (each handset
 * prices individually, FR-3.4b), so this is read from the linked order
 * rather than the receipt.
 */
export function referenceCosts(
  order: PurchaseOrder | null | undefined,
): Map<string, ReferenceCost> {
  const map = new Map<string, ReferenceCost>();
  for (const line of order?.lines ?? []) {
    if (line.unitCostMinor !== null) {
      map.set(line.productId, { minor: line.unitCostMinor, currency: line.currency });
    }
  }
  return map;
}
