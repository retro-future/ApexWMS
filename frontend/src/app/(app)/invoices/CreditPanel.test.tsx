import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CreditPanel } from "@/app/(app)/invoices/CreditPanel";
import { Permission } from "@/lib/permissions";
import type { Payment, SalesInvoice } from "@/lib/types";
import { makeMe, renderWithProviders } from "@/test/render";

const { apiGet } = vi.hoisted(() => ({ apiGet: vi.fn() }));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiGet,
}));

const MANAGER = makeMe(
  [Permission.Payment.Record, Permission.Payment.Reverse],
  "tenant.manager",
);

function payment(id: string, amountMinor: number): Payment {
  return {
    id,
    salesInvoiceId: "invoice-1",
    occurredAt: "2026-08-19T09:30:00Z",
    amount: String(amountMinor),
    amountMinor,
    method: "cash",
    userId: "user-1",
    note: null,
    reversesPaymentId: null,
    isReversal: false,
  };
}

function sale(overrides: Partial<SalesInvoice> = {}): SalesInvoice {
  return {
    id: "invoice-1",
    number: "INV-2026-0001",
    status: "confirmed",
    locationId: "location-1",
    customerId: "customer-1",
    note: null,
    createdBy: "user-1",
    createdAt: "2026-08-19T09:00:00Z",
    confirmedBy: "user-1",
    confirmedAt: "2026-08-19T09:15:00Z",
    cancelledBy: null,
    cancelledAt: null,
    cancellationReason: null,
    lines: [],
    subtotals: [],
    paymentType: "store_credit",
    creditCompanyId: null,
    contractRef: null,
    debt: "7200000",
    debtMinor: 7200000,
    paidMinor: 200000,
    remainingMinor: 7000000,
    payments: [payment("a", 200000)],
    belowCostAlerts: [],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  apiGet.mockResolvedValue([]);
});

describe("CreditPanel", () => {
  it("offers to record a payment while som is still owed", () => {
    renderWithProviders(<CreditPanel invoice={sale()} />, { me: MANAGER });

    expect(screen.getByRole("button", { name: "Record payment" })).toBeInTheDocument();
  });

  it("stops offering it once the debt is paid off", () => {
    const settled = sale({
      paidMinor: 7200000,
      remainingMinor: 0,
      payments: [payment("a", 200000), payment("b", 7000000)],
    });

    renderWithProviders(<CreditPanel invoice={settled} />, { me: MANAGER });

    expect(screen.queryByRole("button", { name: "Record payment" })).not.toBeInTheDocument();
    expect(screen.getByText("This sale is paid off.")).toBeInTheDocument();
  });

  it("still lets a manager reverse a payment on a settled sale", () => {
    // Reversing reopens the debt, which is the point: FR-11.8 exists to
    // correct a payment that was typed wrong.
    const settled = sale({ paidMinor: 7200000, remainingMinor: 0 });

    renderWithProviders(<CreditPanel invoice={settled} />, { me: MANAGER });

    expect(screen.getByRole("button", { name: "Reverse" })).toBeInTheDocument();
  });

  it("names the refund owed on a cancelled sale (FR-11.11)", () => {
    const cancelled = sale({ status: "cancelled", remainingMinor: 0 });

    renderWithProviders(<CreditPanel invoice={cancelled} />, { me: MANAGER });

    expect(
      screen.getByText(
        "This sale was cancelled, but 200 000 so'm is still with the store. Refund it by hand.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Record payment" })).not.toBeInTheDocument();
  });
});
