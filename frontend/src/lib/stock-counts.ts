/**
 * A stock count's four steps, and the three lists a closed one reports.
 *
 * The count is the only document with a step `DocumentStatus` has no value
 * for: it is opened, scanned, **closed**, then confirmed. The close lives on
 * `closedAt`, and a closed count is still a `draft` — it has found
 * discrepancies and applied none. So `isEditable()` from `lib/documents.ts`
 * is not enough on its own here: scanning is refused after the close too.
 *
 * FR-6.3's three lists are derived rather than stored, so they are derived
 * here as well, off the same payload the server sends.
 *
 * Pure functions over the payload, deliberately free of React, so they are
 * testable without a DOM.
 */

import type { StockCount, StockCountLine, StockCountUnit } from "@/lib/types";

/** Where a count is in its life. Not a wire value — assembled from two fields. */
export type CountStep = "counting" | "closed" | "confirmed" | "cancelled";

export function countStep(count: StockCount): CountStep {
  if (count.status === "cancelled") return "cancelled";
  if (count.status === "confirmed") return "confirmed";
  return count.closedAt === null ? "counting" : "closed";
}

/** Scanning and line entry are open only before the close (FR-6.3). */
export function isCounting(count: StockCount): boolean {
  return countStep(count) === "counting";
}

/** Closed and reported, with nothing applied yet. This is where confirm lives. */
export function isClosed(count: StockCount): boolean {
  return countStep(count) === "closed";
}

export type CountLists = {
  matched: StockCountUnit[];
  missing: StockCountUnit[];
  unexpected: StockCountUnit[];
};

/** FR-6.3's three lists, split off the outcome each row already computed. */
export function unitsByOutcome(count: StockCount): CountLists {
  return {
    matched: count.units.filter((unit) => unit.outcome === "matched"),
    missing: count.units.filter((unit) => unit.outcome === "missing"),
    unexpected: count.units.filter((unit) => unit.outcome === "unexpected"),
  };
}

/**
 * Accessory levels nobody stated a figure for. Null is not zero: an
 * uncounted shelf and a shelf found empty are different findings, and only
 * the second books a loss. Worth warning about before the close, because
 * after it nothing can be counted.
 */
export function uncountedLines(count: StockCount): StockCountLine[] {
  return count.lines.filter((line) => line.countedQuantity === null);
}

/**
 * Surprise handsets that confirming cannot value yet (FR-6.4b).
 *
 * A surplus with nothing to value it is refused rather than booked at zero,
 * because `verify-financials` recomputes inventory value by summing on-hand
 * cost and a zero would drift or dilute every later weighted average. Each
 * row needs both a product (a cost is denominated by the model it belongs
 * to, §4.5 rule 3) and a cost.
 *
 * Only meaningful for a caller holding `Permission.Cost.View`: without it the
 * server omits the cost field entirely, so every surprise row looks unvalued.
 * The caller checks the permission; this function only reads the payload.
 */
export function surplusNeedingValue(count: StockCount): StockCountUnit[] {
  return count.units.filter(
    (unit) =>
      unit.isSurprise &&
      (unit.productId === null ||
        unit.acquisitionCostMinor === null ||
        unit.acquisitionCostMinor === undefined),
  );
}

/**
 * The net figure for an accessory line, for display beside the two counts.
 * The server sends `delta` already; this exists so an uncounted line renders
 * as nothing rather than as a confident zero.
 */
export function lineDelta(line: StockCountLine): number | null {
  return line.countedQuantity === null ? null : line.delta;
}
