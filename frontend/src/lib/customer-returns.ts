/**
 * What is not JSX about taking goods back from a customer (§5.4b).
 *
 * The refund arithmetic lives here rather than in the detail screen for the
 * reason `money.ts` exists at all: it is integer minor units throughout, and
 * a component that reached for a float would reintroduce exactly the
 * rounding the money model rules out.
 *
 * None of this is an enforcement point. The server checks every one of these
 * again; what they buy is a disabled button that can say why.
 */

import type {
  CustomerReturn,
  CustomerReturnLine,
  CustomerReturnReason,
  Money,
} from "@/lib/types";

export const CUSTOMER_RETURN_REASON_COLOR: Record<CustomerReturnReason, string> = {
  defective: "red",
  not_as_expected: "blue",
  wrong_item: "orange",
  warranty: "grape",
  other: "gray",
};

export function isSerialLine(line: CustomerReturnLine): boolean {
  return line.trackingType === "serial";
}

/** The one thing the server refuses a return's confirm over: no lines. */
export function canConfirmReturn(document: CustomerReturn): boolean {
  return document.lineCount > 0;
}

/** What the store is keeping on this line, in the line's own currency. */
export function keptOnLine(line: CustomerReturnLine): number {
  return (line.chargedPrice.minor - line.refundPrice.minor) * line.quantity;
}

/** What the store is keeping across the document, per currency. */
export function keptSubtotals(
  document: CustomerReturn,
): Money[] {
  const running = new Map<CustomerReturnLine["currency"], number>();
  for (const line of document.lines) {
    const kept = keptOnLine(line);
    if (kept === 0) continue;
    running.set(line.currency, (running.get(line.currency) ?? 0) + kept);
  }
  return [...running.entries()]
    .map(([currency, minor]) => ({ currency, minor }))
    .sort((a, b) => a.currency.localeCompare(b.currency));
}

/**
 * How many of an accessory line are still returnable on this draft.
 *
 * Only counts *this* document. A return confirmed elsewhere against the same
 * sale is the server's business, and the scan that hits it says so.
 */
export function remainingOnLine(line: CustomerReturnLine): number {
  return line.soldQuantity - line.quantity;
}
