import { describe, expect, it } from "vitest";

import {
  chargedMinor,
  confirmBlockers,
  quoteSubtotals,
  type QuoteMap,
} from "@/lib/invoices";
import type { Currency, SalesInvoice, SalesInvoiceLine, TrackingType } from "@/lib/types";

function line(
  id: string,
  overrides: Partial<SalesInvoiceLine> = {},
  tracking: TrackingType = "serial",
  currency: Currency = "USD",
): SalesInvoiceLine {
  return {
    id,
    productId: `product-${id}`,
    deviceUnitId: tracking === "serial" ? `unit-${id}` : null,
    quantity: 1,
    trackingType: tracking,
    currency,
    // A draft's money fields are all null; only an override is set.
    resolvedPrice: null,
    resolvedPriceMinor: null,
    chargedPrice: null,
    chargedPriceMinor: null,
    lineTotal: null,
    lineTotalMinor: null,
    overridePrice: null,
    overridePriceMinor: null,
    priceApprovedBy: null,
    priceNote: null,
    isDeviation: false,
    ...overrides,
  };
}

function invoice(lines: SalesInvoiceLine[]): SalesInvoice {
  return {
    id: "invoice-1",
    number: "INV-2026-0001",
    status: "draft",
    locationId: "location-1",
    customerId: null,
    note: null,
    createdBy: "user-1",
    createdAt: "2026-08-19T09:00:00Z",
    confirmedBy: null,
    confirmedAt: null,
    cancelledBy: null,
    cancelledAt: null,
    cancellationReason: null,
    lines,
    subtotals: [],
    paymentType: "paid_in_full",
    creditCompanyId: null,
    contractRef: null,
    debt: null,
    debtMinor: null,
    paidMinor: 0,
    remainingMinor: 0,
    payments: [],
  };
}

function quotes(entries: [string, number | null][]): QuoteMap {
  return new Map(
    entries.map(([id, resolvedMinor]) => [
      id,
      { resolvedMinor, chargedMinor: resolvedMinor, currency: "USD" as Currency, isOverride: false },
    ]),
  );
}

describe("chargedMinor", () => {
  it("takes what resolves when nothing was overridden", () => {
    expect(chargedMinor(line("a"), 52000)).toBe(52000);
  });

  it("prefers an explicit override, which survives re-resolution (FR-4.5b1)", () => {
    // The unit was marked down to $480 while the draft sat open; the
    // manager's $300 is still what the customer is charged.
    expect(chargedMinor(line("a", { overridePriceMinor: 30000 }), 48000)).toBe(30000);
  });

  it("keeps a zero-priced giveaway rather than falling back (FR-4.5e)", () => {
    expect(chargedMinor(line("a", { overridePriceMinor: 0 }), 52000)).toBe(0);
  });

  it("is null where nothing resolves and nothing was overridden", () => {
    expect(chargedMinor(line("a"), null)).toBeNull();
  });
});

describe("quoteSubtotals", () => {
  it("multiplies by the quantity an accessory line carries", () => {
    const accessory = line("a", { quantity: 3 }, "quantity");
    expect(quoteSubtotals(invoice([accessory]), quotes([["a", 1200]]))).toEqual([
      { currency: "USD", amountMinor: 3600 },
    ]);
  });

  it("keeps the currencies apart and never sums them (§4.5 rule 4)", () => {
    const dollars = line("a");
    const som = { ...line("b"), currency: "UZS" as Currency };
    const map: QuoteMap = new Map([
      ["a", { resolvedMinor: 52000, chargedMinor: 52000, currency: "USD" as Currency, isOverride: false }],
      ["b", { resolvedMinor: 900000, chargedMinor: 900000, currency: "UZS" as Currency, isOverride: false }],
    ]);

    expect(quoteSubtotals(invoice([dollars, som]), map)).toEqual([
      { currency: "USD", amountMinor: 52000 },
      { currency: "UZS", amountMinor: 900000 },
    ]);
  });

  it("leaves a line that resolves to nothing out of the total, not at zero", () => {
    expect(quoteSubtotals(invoice([line("a"), line("b")]), quotes([["a", 52000], ["b", null]]))).toEqual([
      { currency: "USD", amountMinor: 52000 },
    ]);
  });
});

describe("confirmBlockers", () => {
  it("refuses an invoice with nothing on it", () => {
    const blockers = confirmBlockers(invoice([]), new Map());
    expect(blockers.isEmpty).toBe(true);
    expect(blockers.isReady).toBe(false);
  });

  it("names a line whose price stopped resolving (FR-4.5b2)", () => {
    // The handset was flipped to USED while the draft sat open, so the
    // catalog price no longer reaches it.
    const blockers = confirmBlockers(invoice([line("a"), line("b")]), quotes([["a", 52000], ["b", null]]));

    expect(blockers.unresolvedLines.map((one) => one.id)).toEqual(["b"]);
    expect(blockers.isReady).toBe(false);
  });

  it("does not blame a line whose override covers the missing price", () => {
    const overridden = line("a", { overridePriceMinor: 30000 });
    expect(confirmBlockers(invoice([overridden]), quotes([["a", null]])).isReady).toBe(true);
  });

  it("is not a blocker while a line's handset is still loading", () => {
    // No quote yet is "unknown", not "unpriced".
    expect(confirmBlockers(invoice([line("a")]), new Map()).isReady).toBe(true);
  });

  it("is ready when every line resolves", () => {
    expect(confirmBlockers(invoice([line("a")]), quotes([["a", 52000]])).isReady).toBe(true);
  });
});
