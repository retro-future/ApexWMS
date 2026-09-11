import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MonthEndReportScreen } from "@/app/(app)/reports/month-end/MonthEndReport";
import { Permission } from "@/lib/permissions";
import { makeMe, renderWithProviders } from "@/test/render";
import type { Money, MonthEndReport, SomFigures } from "@/lib/types";

/**
 * The accrual block is a grid of figures against currencies, and a grid is
 * where a plausible-looking wrong number comes from: a dollar amount under a
 * som heading reads as fine. So this pins the columns to what the period
 * actually touched, and pins the reconciliation banner to the flag rather
 * than to whether the list happens to be empty.
 */

const { apiGet } = vi.hoisted(() => ({ apiGet: vi.fn() }));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiGet,
}));

const usd = (minor: number): Money => ({ currency: "USD", minor });

const som = (minor: number): Money => ({ currency: "UZS", minor });

function report(overrides: Partial<MonthEndReport> = {}): MonthEndReport {
  return {
    period: {
      year: 2026,
      month: 1,
      timezone: "Asia/Tashkent",
      start: "2025-12-31T19:00:00Z",
      end: "2026-01-31T19:00:00Z",
    },
    locationId: null,
    figures: {
      openingInventory: [usd(190000)],
      purchases: [usd(-76000)],
      costOfGoods: [usd(-38000)],
      revenue: [usd(60000)],
      salesReturns: [],
      writeOffs: [],
      supplierReturnCredits: [],
      countAdjustments: [],
      closingInventory: [usd(176000)],
      margin: [usd(22000)],
      marginPercent: [{ currency: "USD", percent: "36.7" }],
    },
    som: null,
    closingByLocation: [
      {
        locationId: "location-1",
        locationName: "Chilonzor shop",
        quantity: 4,
        value: [usd(176000)],
      },
    ],
    debt: {
      opening: { minor: 0, currency: "UZS" },
      booked: { minor: 7800000, currency: "UZS" },
      collected: { minor: 800000, currency: "UZS" },
      voided: { minor: 0, currency: "UZS" },
      relieved: { minor: 0, currency: "UZS" },
      closing: { minor: 7000000, currency: "UZS" },
    },
    financing: [
      {
        paymentType: "store_credit",
        creditCompanyId: null,
        creditCompanyName: null,
        invoiceCount: 1,
        revenue: [usd(60000)],
      },
    ],
    reconciles: true,
    discrepancies: [],
    ...overrides,
  };
}

function renderScreen(data: MonthEndReport) {
  apiGet.mockReset();
  apiGet.mockResolvedValue(data);
  return renderWithProviders(<MonthEndReportScreen />, {
    me: makeMe([Permission.FinancialLedger.View]),
  });
}

describe("the stock and sales blocks", () => {
  it("gives a dollars-only month no som column", async () => {
    renderScreen(report());

    // Closing inventory is printed twice: closing the bridge, and per location.
    expect(await screen.findAllByText("$1,760.00")).toHaveLength(2);
    expect(
      screen.getAllByRole("columnheader", { name: "USD" }).length,
    ).toBeGreaterThan(0);
    expect(
      screen.queryByRole("columnheader", { name: "UZS" }),
    ).not.toBeInTheDocument();
  });

  it("adds a som column once the period touches so'm", async () => {
    const mixed = report();
    renderScreen({
      ...mixed,
      figures: { ...mixed.figures, revenue: [usd(60000), som(45000)] },
    });

    expect(
      (await screen.findAllByRole("columnheader", { name: "UZS" })).length,
    ).toBeGreaterThan(0);
  });

  it("reads a purchase as stock coming in, not money leaving", async () => {
    renderScreen(report()); // purchases: usd(-76000)

    expect(await screen.findByText("$760.00")).toBeInTheDocument();
    expect(screen.queryByText("-$760.00")).not.toBeInTheDocument();
  });

  it("reads a supplier return as stock leaving the shelf", async () => {
    const r = report();
    renderScreen({
      ...r,
      figures: { ...r.figures, supplierReturnCredits: [usd(90000)] },
    });

    expect(await screen.findByText("-$900.00")).toBeInTheDocument();
  });

  it("shows the supplier-return credit as money back, once the goods are out", async () => {
    const r = report();
    renderScreen({
      ...r,
      figures: { ...r.figures, supplierReturnCredits: [usd(90000)] },
    });

    // -$900 in the bridge where the goods left, +$900 as the credit.
    expect(await screen.findByText("-$900.00")).toBeInTheDocument();
    expect(screen.getByText("$900.00")).toBeInTheDocument();
  });

  it("keeps cost of goods negative in the sales block and shows the margin", async () => {
    renderScreen(report());

    // Cost of goods reads negative in both the bridge and the sales block.
    expect((await screen.findAllByText("-$380.00")).length).toBe(2);
    expect(screen.getByText("$220.00")).toBeInTheDocument();
  });

  it("links a stock move to the ledger category it was folded from", async () => {
    const r = report();
    renderScreen({
      ...r,
      figures: { ...r.figures, supplierReturnCredits: [usd(90000)] },
    });

    const link = await screen.findByRole("link", {
      name: "Returned to suppliers",
    });
    expect(link).toHaveAttribute(
      "href",
      "/reports/financial-ledger?txnType=supplier_return_credit&from=2026-01-01&to=2026-01-31",
    );
  });

  it("shows no margin percentage where the month sold nothing", async () => {
    const quiet = report();
    renderScreen({
      ...quiet,
      figures: {
        ...quiet.figures,
        revenue: [],
        margin: [],
        marginPercent: [{ currency: "USD", percent: null }],
      },
    });

    expect(await screen.findByText("—")).toBeInTheDocument();
    expect(screen.queryByText("0%")).not.toBeInTheDocument();
  });
});

describe("a month with nothing in it", () => {
  it("says so rather than printing labels against empty columns", async () => {
    const quiet = report();
    renderScreen({
      ...quiet,
      figures: {
        openingInventory: [],
        purchases: [],
        costOfGoods: [],
        revenue: [],
        salesReturns: [],
        writeOffs: [],
        supplierReturnCredits: [],
        countAdjustments: [],
        closingInventory: [],
        margin: [],
        marginPercent: [],
      },
      closingByLocation: [],
    });

    expect(await screen.findByText("Nothing moved this month")).toBeInTheDocument();
    // No currency was touched, so there is no column to head.
    expect(screen.queryByRole("columnheader", { name: "USD" })).not.toBeInTheDocument();
    expect(screen.queryByText("Opening inventory")).not.toBeInTheDocument();
  });
});

describe("the reconciliation banner", () => {
  it("says so when goods and money agree", async () => {
    renderScreen(report());

    expect(await screen.findByText("Goods and money agree")).toBeInTheDocument();
  });

  it("lists each discrepancy and still shows the figures", async () => {
    renderScreen(
      report({
        reconciles: false,
        discrepancies: [
          {
            subject: "closing inventory value in USD",
            expected: "$1,760.00",
            found: "$1,860.00",
          },
        ],
      }),
    );

    expect(
      await screen.findByText("Goods and money disagree"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/closing inventory value in USD/),
    ).toBeInTheDocument();
    // The mismatch is surfaced beside the month, never instead of it: revenue
    // still shows, in the grid and in the financing split.
    expect(screen.getAllByText("$600.00")).toHaveLength(2);
  });
});

describe("customer returns", () => {
  it("shows the refunded amount in the sales block and links it to the ledger", async () => {
    const base = report();
    renderScreen({
      ...base,
      figures: { ...base.figures, salesReturns: [usd(-15000)] },
    });

    const link = await screen.findByRole("link", { name: "Customer returns" });
    expect(link).toHaveAttribute(
      "href",
      "/reports/financial-ledger?txnType=sales_return_refund&from=2026-01-01&to=2026-01-31",
    );
    expect(screen.getByText("-$150.00")).toBeInTheDocument();
  });

  it("shows debt written off by returns as its own line", async () => {
    const base = report();
    renderScreen({
      ...base,
      debt: { ...base.debt, relieved: { minor: 500000, currency: "UZS" } },
    });

    expect(
      await screen.findByText("Debt written off by customer returns"),
    ).toBeInTheDocument();
    expect(screen.getByText(/500[\s ]000/)).toBeInTheDocument();
  });
});

describe("the period", () => {
  it("names the store's timezone, and does not start in December", async () => {
    renderScreen(report());

    const period = await screen.findByText(/Asia\/Tashkent/);
    expect(period).toBeInTheDocument();
    expect(period.textContent).not.toContain("Dec");
  });
});

function somFigures(overrides: Partial<SomFigures> = {}): SomFigures {
  return {
    openingInventory: som(2_280_000),
    purchases: som(-912_000),
    costOfGoods: som(-456_000),
    revenue: som(750_000),
    salesReturns: som(0),
    writeOffs: som(0),
    supplierReturnCredits: som(0),
    countAdjustments: som(0),
    closingInventory: som(2_112_000),
    margin: som(294_000),
    marginPercent: "39.2",
    rateGain: som(0),
    instalmentIncome: som(0),
    profit: som(294_000),
    openingRate: "12000",
    closingRate: "12500",
    beforeTheFirstQuote: false,
    ...overrides,
  };
}

describe("the month read in som", () => {
  it("says there is nothing to convert at until a rate is quoted", async () => {
    renderScreen(report());

    expect(await screen.findByText(/no rate has been quoted yet/i)).toBeInTheDocument();
  });

  it("prints the converted figures and the rates they were read at", async () => {
    renderScreen(report({ som: somFigures() }));

    expect(await screen.findByText(/the month in so'm/i)).toBeInTheDocument();
    expect(
      screen.getByText(/12000 at the start of the period, 12500 at the end/i),
    ).toBeInTheDocument();
    expect(screen.getByText("39.2%")).toBeInTheDocument();
  });

  it("prints the profit an owner would count, not only the converted margin", async () => {
    renderScreen(
      report({
        som: somFigures({
          rateGain: som(645_000),
          instalmentIncome: som(300_000),
          profit: som(1_239_000),
        }),
      }),
    );

    expect(await screen.findByText("Rate gain")).toBeInTheDocument();
    expect(screen.getByText(/645[\s ]000/)).toBeInTheDocument();
    // The two are never one line: one is set by a percentage the shop
    // agreed, the other by how the counter rounded a rate.
    expect(screen.getByText("Instalment income")).toBeInTheDocument();
    expect(screen.getByText(/300[\s ]000/)).toBeInTheDocument();
    expect(screen.getByText("Profit on goods")).toBeInTheDocument();
    expect(screen.getByText(/1[\s ]239[\s ]000/)).toBeInTheDocument();
  });

  it("says so when the period predates the first rate on file", async () => {
    renderScreen(report({ som: somFigures({ beforeTheFirstQuote: true }) }));

    expect(
      await screen.findByText(/earlier than the first rate the store recorded/i),
    ).toBeInTheDocument();
  });
});

describe("the debt block", () => {
  it("reads in so'm, whole units, however large", async () => {
    renderScreen(report());

    expect(await screen.findByText(/7[\s ]000[\s ]000/)).toBeInTheDocument();
  });
});

describe("the debt block drill-downs", () => {
  it("links store-credit sales booked to the invoices behind it", async () => {
    renderScreen(report());

    const link = await screen.findByRole("link", {
      name: "Store-credit sales booked",
    });
    expect(link).toHaveAttribute(
      "href",
      "/invoices?paymentType=store_credit&status=confirmed" +
        "&confirmedFrom=2026-01-01&confirmedTo=2026-01-31",
    );
  });

  it("links cash collected to the payments ledger", async () => {
    renderScreen(report());

    const link = await screen.findByRole("link", { name: "Cash collected" });
    expect(link).toHaveAttribute(
      "href",
      "/reports/financial-ledger?txnType=payment_received&from=2026-01-01&to=2026-01-31",
    );
  });
});
