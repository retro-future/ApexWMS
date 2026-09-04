import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SalesSummaryReport } from "@/app/(app)/reports/sales-summary/SalesSummaryReport";
import { Permission } from "@/lib/permissions";
import { makeMe, renderWithProviders } from "@/test/render";
import type { CurrencySubtotal, SalesFigures, SalesSummary } from "@/lib/types";

const { apiGet } = vi.hoisted(() => ({ apiGet: vi.fn() }));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiGet,
}));

const usd = (amountMinor: number): CurrencySubtotal => ({
  currency: "USD",
  amount: String(amountMinor / 100),
  amountMinor,
});

const figures = (over: Partial<SalesFigures> = {}): SalesFigures => ({
  unitsSold: 5,
  revenue: [usd(250000)],
  costOfGoods: [usd(-100000)],
  returns: [usd(-30000)],
  margin: [usd(120000)],
  ...over,
});

function renderReport(summary: SalesSummary) {
  apiGet.mockReset();
  apiGet.mockResolvedValue(summary);
  return renderWithProviders(<SalesSummaryReport />, {
    me: makeMe([Permission.Reporting.View]),
  });
}

describe("the sales summary customer-returns figure", () => {
  it("shows the refunded total next to revenue", async () => {
    renderReport({
      fromDate: null,
      toDate: null,
      locations: [
        { locationId: "location-1", locationName: "Chilonzor shop", figures: figures() },
      ],
      total: figures(),
    });

    // Labelled in the summary card and again as a table column.
    expect(await screen.findAllByText("Customer returns")).toHaveLength(2);
    // The refund total: once in the card, once in the location row.
    expect(screen.getAllByText("-$300.00")).toHaveLength(2);
  });

  it("keeps a zero-return month readable", async () => {
    const none = figures({ returns: [], margin: [usd(150000)] });
    renderReport({
      fromDate: null,
      toDate: null,
      locations: [
        { locationId: "location-1", locationName: "Chilonzor shop", figures: none },
      ],
      total: none,
    });

    expect(await screen.findAllByText("Customer returns")).toHaveLength(2);
    expect(screen.queryByText("-$300.00")).not.toBeInTheDocument();
  });
});
