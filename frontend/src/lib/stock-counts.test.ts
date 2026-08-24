import { describe, expect, it } from "vitest";

import {
  countStep,
  isClosed,
  isCounting,
  lineDelta,
  surplusNeedingValue,
  uncountedLines,
  unitsByOutcome,
} from "@/lib/stock-counts";
import type { StockCount, StockCountLine, StockCountUnit } from "@/lib/types";

function unit(overrides: Partial<StockCountUnit> = {}): StockCountUnit {
  return {
    id: crypto.randomUUID(),
    imei: "490154203237518",
    deviceUnitId: "device-1",
    productId: "product-1",
    expected: true,
    scanned: true,
    outcome: "matched",
    isSurprise: false,
    ...overrides,
  };
}

function line(overrides: Partial<StockCountLine> = {}): StockCountLine {
  return {
    id: crypto.randomUUID(),
    productId: "product-1",
    expectedQuantity: 10,
    countedQuantity: null,
    delta: 0,
    ...overrides,
  };
}

function count(overrides: Partial<StockCount> = {}): StockCount {
  return {
    id: "count-1",
    number: "SC-2026-0001",
    status: "draft",
    locationId: "location-1",
    note: null,
    createdBy: "user-1",
    createdAt: "2026-08-14T09:00:00Z",
    closedAt: null,
    confirmedAt: null,
    cancelledAt: null,
    cancellationReason: null,
    units: [],
    lines: [],
    matchedCount: 0,
    missingCount: 0,
    unexpectedCount: 0,
    ...overrides,
  };
}

describe("countStep", () => {
  it("reads a count that is still being scanned as counting", () => {
    expect(countStep(count())).toBe("counting");
    expect(isCounting(count())).toBe(true);
  });

  it("separates closed from counting even though both are drafts", () => {
    // The fourth step has no DocumentStatus of its own: a closed count has
    // found its discrepancies and applied none, so it is still a draft.
    const closed = count({ status: "draft", closedAt: "2026-08-14T17:00:00Z" });

    expect(closed.status).toBe("draft");
    expect(countStep(closed)).toBe("closed");
    expect(isClosed(closed)).toBe(true);
    expect(isCounting(closed)).toBe(false);
  });

  it("reads confirmed and cancelled off the status", () => {
    expect(countStep(count({ status: "confirmed" }))).toBe("confirmed");
    expect(countStep(count({ status: "cancelled" }))).toBe("cancelled");
  });

  it("calls a cancelled count cancelled even though it was closed first", () => {
    const cancelled = count({
      status: "cancelled",
      closedAt: "2026-08-14T17:00:00Z",
    });

    expect(countStep(cancelled)).toBe("cancelled");
  });
});

describe("unitsByOutcome", () => {
  it("splits FR-6.3's three lists off the outcome each row carries", () => {
    const matched = unit({ outcome: "matched" });
    const missing = unit({ outcome: "missing", scanned: false });
    const surprise = unit({
      outcome: "unexpected",
      expected: false,
      isSurprise: true,
      deviceUnitId: null,
      productId: null,
    });

    const lists = unitsByOutcome(count({ units: [matched, missing, surprise] }));

    expect(lists.matched).toEqual([matched]);
    expect(lists.missing).toEqual([missing]);
    expect(lists.unexpected).toEqual([surprise]);
  });
});

describe("uncountedLines", () => {
  it("treats a null count as uncounted and a zero as a real finding", () => {
    // A shelf nobody looked at and a shelf found empty are different
    // findings, and only the second books a loss.
    const untouched = line({ countedQuantity: null });
    const foundEmpty = line({ countedQuantity: 0, delta: -10 });

    expect(uncountedLines(count({ lines: [untouched, foundEmpty] }))).toEqual([
      untouched,
    ]);
  });
});

describe("lineDelta", () => {
  it("reports nothing for an uncounted line rather than a confident zero", () => {
    expect(lineDelta(line({ countedQuantity: null }))).toBeNull();
  });

  it("reports the server's delta once a figure has been stated", () => {
    expect(lineDelta(line({ countedQuantity: 8, delta: -2 }))).toBe(-2);
  });
});

describe("surplusNeedingValue", () => {
  it("lists a surprise that names no product", () => {
    const nameless = unit({
      outcome: "unexpected",
      expected: false,
      isSurprise: true,
      deviceUnitId: null,
      productId: null,
    });

    expect(surplusNeedingValue(count({ units: [nameless] }))).toEqual([nameless]);
  });

  it("lists a surprise whose product is known but whose cost is not", () => {
    const unpriced = unit({
      outcome: "unexpected",
      expected: false,
      isSurprise: true,
      acquisitionCostMinor: null,
    });

    expect(surplusNeedingValue(count({ units: [unpriced] }))).toEqual([unpriced]);
  });

  it("clears a surprise once a cost has been stated", () => {
    const valued = unit({
      outcome: "unexpected",
      expected: false,
      isSurprise: true,
      acquisitionCost: "300.00",
      acquisitionCostMinor: 30000,
    });

    expect(surplusNeedingValue(count({ units: [valued] }))).toEqual([]);
  });

  it("ignores an unexpected handset the store already holds elsewhere", () => {
    // Found on another shelf: it was bought once and its cost booked then,
    // so the goods move and the money does not. Nothing to value.
    const elsewhere = unit({
      outcome: "unexpected",
      expected: false,
      isSurprise: false,
    });

    expect(surplusNeedingValue(count({ units: [elsewhere] }))).toEqual([]);
  });

  it("ignores matched and missing rows entirely", () => {
    const matched = unit({ outcome: "matched" });
    const missing = unit({ outcome: "missing", scanned: false });

    expect(surplusNeedingValue(count({ units: [matched, missing] }))).toEqual([]);
  });
});
