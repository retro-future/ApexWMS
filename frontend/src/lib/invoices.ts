/**
 * What a draft invoice would charge, worked out on the client.
 *
 * The server sends `resolvedPrice`, `chargedPrice` and `lineTotal` as null
 * for the whole life of a draft, and an empty `subtotals` — that is FR-4.5b1
 * being honest: a draft reserves no price, and every un-overridden line is
 * resolved again at confirm. But the counter still has to read a figure to
 * the customer, so the page assembles one from what it can see: each
 * handset's own `resolvedPrice` (which the server computed, per FR-2.14) and
 * each accessory's catalog price.
 *
 * It is a **quote, not a reservation**. A markdown made while the draft is
 * open reaches the customer, so the number here can legitimately differ from
 * what the invoice books a moment later.
 *
 * Pure functions over the payload, deliberately free of React, so they are
 * testable without a DOM.
 */

import type { Currency, Money, SalesInvoice, SalesInvoiceLine } from "@/lib/types";

/** What one line resolves to right now, or the fact that it resolves to nothing. */
export type LineQuote = {
  /** What FR-2.14 resolves for this line, or null where it refuses. */
  resolvedMinor: number | null;
  /** What would actually be charged per unit: an override wins (FR-4.5b1). */
  chargedMinor: number | null;
  currency: Currency;
  isOverride: boolean;
};

export type QuoteMap = Map<string, LineQuote>;

export function isSerial(line: SalesInvoiceLine): boolean {
  return line.trackingType === "serial";
}

/**
 * An explicit override survives re-resolution and is what is charged
 * (FR-4.5b1); everything else follows whatever resolves now.
 */
export function chargedMinor(
  line: SalesInvoiceLine,
  resolvedMinor: number | null,
): number | null {
  return line.overridePrice?.minor ?? resolvedMinor;
}

/**
 * FR-4.5b2's blocker, seen early: a line that resolves to nothing cannot be
 * confirmed. Typically a handset flipped to USED while the draft sat open,
 * or one that was never priced.
 */
export function unresolvedLines(
  invoice: SalesInvoice,
  quotes: QuoteMap,
): SalesInvoiceLine[] {
  return invoice.lines.filter((line) => {
    const quote = quotes.get(line.id);
    // A line still loading its unit is not yet a blocker.
    if (!quote) return false;
    return chargedMinor(line, quote.resolvedMinor) === null;
  });
}

export type ConfirmBlockers = {
  isEmpty: boolean;
  unresolvedLines: SalesInvoiceLine[];
  /** True when nothing is standing in the way of a confirm. */
  isReady: boolean;
};

/**
 * The two refusals the screen can see coming. This is **not** an enforcement
 * point — the server re-resolves every price at confirm and refuses on its
 * own terms, naming the offending line. It exists so the gap shows while the
 * customer is still standing there.
 */
export function confirmBlockers(
  invoice: SalesInvoice,
  quotes: QuoteMap,
): ConfirmBlockers {
  const isEmpty = invoice.lines.length === 0;
  const unresolved = unresolvedLines(invoice, quotes);
  return {
    isEmpty,
    unresolvedLines: unresolved,
    isReady: !isEmpty && unresolved.length === 0,
  };
}

/**
 * One figure per currency present, never their sum (§4.5 rule 4). What
 * `<Subtotals>` renders for a confirmed invoice, so one component serves
 * both states.
 */
export function quoteSubtotals(
  invoice: SalesInvoice,
  quotes: QuoteMap,
): Money[] {
  const totals = new Map<Currency, number>();
  for (const line of invoice.lines) {
    const quote = quotes.get(line.id);
    const charged = quote ? chargedMinor(line, quote.resolvedMinor) : null;
    if (charged === null) continue;
    totals.set(line.currency, (totals.get(line.currency) ?? 0) + charged * line.quantity);
  }
  return [...totals.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([currency, minor]) => ({ currency, minor }));
}
