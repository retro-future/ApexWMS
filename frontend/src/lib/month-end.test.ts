import { describe, expect, it } from "vitest";

import {
  SALES_ROWS,
  STOCK_BRIDGE_ROWS,
  STOCK_MOVE_ROWS,
  amountIn,
  currenciesIn,
  formatPeriod,
  fromMonthInput,
  invoicesHref,
  lastCompletedMonth,
  ledgerHref,
  percentIn,
  stockMoveMinor,
  toMonthInput,
} from "@/lib/month-end";
import type { AccrualFigures, CurrencySubtotal, Period } from "@/lib/types";

/**
 * Two things here are worth pinning down. **The period is the store's, not the
 * browser's** (FR-10.8): formatted in the wrong zone, a Tashkent January
 * appears to begin in December and the whole report looks broken. And **the
 * accrual table is a grid**, so a row list and a column list that disagree
 * produce a wrong number that still looks plausible.
 */

const usd = (amountMinor: number): CurrencySubtotal => ({
  currency: "USD",
  amount: String(amountMinor / 100),
  amountMinor,
});

const som = (amountMinor: number): CurrencySubtotal => ({
  currency: "UZS",
  amount: String(amountMinor),
  amountMinor,
});

function figures(overrides: Partial<AccrualFigures> = {}): AccrualFigures {
  return {
    openingInventory: [],
    purchases: [],
    costOfGoods: [],
    revenue: [],
    writeOffs: [],
    supplierReturnCredits: [],
    countAdjustments: [],
    closingInventory: [],
    margin: [],
    marginPercent: [],
    ...overrides,
  };
}

describe("lastCompletedMonth", () => {
  it("is the month before the one we are in", () => {
    expect(lastCompletedMonth(new Date("2026-02-05T10:00:00Z"))).toEqual({
      year: 2026,
      month: 1,
    });
  });

  it("rolls January back into the previous December", () => {
    expect(lastCompletedMonth(new Date("2026-01-03T10:00:00Z"))).toEqual({
      year: 2025,
      month: 12,
    });
  });
});

describe("the month input round trip", () => {
  it("pads a single-digit month, because the input demands two", () => {
    expect(toMonthInput({ year: 2026, month: 1 })).toBe("2026-01");
    expect(toMonthInput({ year: 2026, month: 12 })).toBe("2026-12");
  });

  it("reads a value back", () => {
    expect(fromMonthInput("2026-01")).toEqual({ year: 2026, month: 1 });
  });

  it("refuses an empty, half-typed or impossible value", () => {
    expect(fromMonthInput("")).toBeNull();
    expect(fromMonthInput("2026-")).toBeNull();
    expect(fromMonthInput("2026-13")).toBeNull();
    expect(fromMonthInput("2026-00")).toBeNull();
  });
});

describe("currenciesIn", () => {
  it("returns only what the period touched", () => {
    expect(currenciesIn(figures({ revenue: [usd(60000)] }))).toEqual(["USD"]);
  });

  it("keeps a stable order whichever way the payload arrives", () => {
    const dollarsFirst = figures({ revenue: [usd(60000), som(45000)] });
    const somFirst = figures({ revenue: [som(45000), usd(60000)] });

    expect(currenciesIn(dollarsFirst)).toEqual(["USD", "UZS"]);
    expect(currenciesIn(somFirst)).toEqual(["USD", "UZS"]);
  });

  it("gives a dollars-only store no empty som column", () => {
    const dollars = figures({
      openingInventory: [usd(190000)],
      closingInventory: [usd(176000)],
    });

    expect(currenciesIn(dollars)).not.toContain("UZS");
  });

  it("looks at every row, not just the ones with revenue", () => {
    expect(currenciesIn(figures({ countAdjustments: [som(500)] }))).toEqual([
      "UZS",
    ]);
  });
});

describe("amountIn", () => {
  it("reads one currency's figure", () => {
    expect(amountIn([usd(60000), som(45000)], "USD")).toBe(60000);
    expect(amountIn([usd(60000), som(45000)], "UZS")).toBe(45000);
  });

  it("is zero where the currency is absent, never the other column", () => {
    expect(amountIn([usd(60000)], "UZS")).toBe(0);
  });

  it("keeps §4.6's sign: a purchase is money that left", () => {
    expect(amountIn([usd(-76000)], "USD")).toBe(-76000);
  });
});

describe("percentIn", () => {
  it("reads a currency's margin percentage", () => {
    expect(percentIn([{ currency: "USD", percent: "36.7" }], "USD")).toBe(
      "36.7",
    );
  });

  it("is null where the period sold nothing, not zero", () => {
    expect(percentIn([{ currency: "USD", percent: null }], "USD")).toBeNull();
    expect(percentIn([], "USD")).toBeNull();
  });
});

describe("formatPeriod", () => {
  const january: Period = {
    year: 2026,
    month: 1,
    timezone: "Asia/Tashkent",
    // Midnight on the 1st in Tashkent is 19:00 the evening before in UTC.
    start: "2025-12-31T19:00:00Z",
    end: "2026-01-31T19:00:00Z",
  };

  it("renders the window in the store's timezone, not the browser's", () => {
    const rendered = formatPeriod(january);

    expect(rendered).toContain("2026-01-01 00:00");
    expect(rendered).toContain("2026-02-01 00:00");
    expect(rendered).toContain("Asia/Tashkent");
  });

  it("does not show a January period starting in December", () => {
    expect(formatPeriod(january)).not.toContain("2025-12");
  });
});

describe("the row lists", () => {
  it("opens the stock bridge with opening and ends it with closing", () => {
    expect(STOCK_BRIDGE_ROWS[0]).toBe("openingInventory");
    expect(STOCK_BRIDGE_ROWS[STOCK_BRIDGE_ROWS.length - 1]).toBe(
      "closingInventory",
    );
  });

  it("names each stock-bridge figure once", () => {
    expect(new Set(STOCK_BRIDGE_ROWS).size).toBe(STOCK_BRIDGE_ROWS.length);
  });

  it("counts every move between opening and closing, and nothing else", () => {
    expect(STOCK_MOVE_ROWS).toEqual([
      "purchases",
      "costOfGoods",
      "writeOffs",
      "supplierReturnCredits",
      "countAdjustments",
    ]);
  });

  it("keeps the sales block to revenue, its cost, and the margin", () => {
    expect(SALES_ROWS).toEqual(["revenue", "costOfGoods", "margin"]);
  });
});

describe("the drill-down links", () => {
  const august: Period = {
    year: 2026,
    month: 8,
    timezone: "Asia/Tashkent",
    start: "2026-07-31T19:00:00Z",
    end: "2026-08-31T19:00:00Z",
  };

  it("scopes a ledger link to the report's month and one category", () => {
    expect(ledgerHref("supplier_return_credit", august)).toBe(
      "/reports/financial-ledger?txnType=supplier_return_credit&from=2026-08-01&to=2026-08-31",
    );
  });

  it("scopes an invoices link to store-credit sales confirmed that month", () => {
    expect(
      invoicesHref({ paymentType: "store_credit", status: "confirmed", period: august }),
    ).toBe(
      "/invoices?paymentType=store_credit&status=confirmed" +
        "&confirmedFrom=2026-08-01&confirmedTo=2026-08-31",
    );
  });

  it("pads a single-digit month and ends on the month's last day", () => {
    const february: Period = { ...august, year: 2024, month: 2 };
    expect(ledgerHref("purchase", february)).toBe(
      "/reports/financial-ledger?txnType=purchase&from=2024-02-01&to=2024-02-29",
    );
  });
});

describe("stockMoveMinor", () => {
  it("reads a purchase as stock coming in, not money leaving", () => {
    const f = figures({ purchases: [usd(-1595000)] });
    expect(stockMoveMinor(f, "purchases", "USD")).toBe(1595000);
  });

  it("reads a supplier return credit as stock leaving the shelf", () => {
    const f = figures({ supplierReturnCredits: [usd(90000)] });
    expect(stockMoveMinor(f, "supplierReturnCredits", "USD")).toBe(-90000);
  });

  it("keeps cost of goods and write-offs as reductions", () => {
    const f = figures({ costOfGoods: [usd(-420000)], writeOffs: [usd(-45000)] });
    expect(stockMoveMinor(f, "costOfGoods", "USD")).toBe(-420000);
    expect(stockMoveMinor(f, "writeOffs", "USD")).toBe(-45000);
  });

  it("passes a count surplus straight through as stock coming in", () => {
    const f = figures({ countAdjustments: [usd(125000)] });
    expect(stockMoveMinor(f, "countAdjustments", "USD")).toBe(125000);
  });

  it("the signed moves plus opening land exactly on closing inventory", () => {
    const f = figures({
      openingInventory: [],
      purchases: [usd(-1595000)],
      costOfGoods: [usd(-420000)],
      writeOffs: [usd(-45000)],
      supplierReturnCredits: [usd(90000)],
      countAdjustments: [usd(125000)],
      closingInventory: [usd(1165000)],
    });

    const moved = STOCK_MOVE_ROWS.reduce(
      (running, row) => running + stockMoveMinor(f, row, "USD"),
      amountIn(f.openingInventory, "USD"),
    );

    expect(moved).toBe(amountIn(f.closingInventory, "USD"));
  });
});
