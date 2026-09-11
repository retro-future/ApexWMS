import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TenderPanel } from "@/app/(app)/invoices/TenderPanel";
import { Permission } from "@/lib/permissions";
import type { Currency, Payment, SalesInvoice } from "@/lib/types";
import { makeMe, renderWithProviders } from "@/test/render";

const { apiGet } = vi.hoisted(() => ({ apiGet: vi.fn() }));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiGet,
}));

const SELLER = makeMe([Permission.Payment.Record], "tenant.seller");

function payment(id: string, minor: number, currency: Currency): Payment {
  return {
    id,
    salesInvoiceId: "invoice-1",
    occurredAt: "2026-08-19T09:30:00Z",
    amount: { minor, currency },
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
    customerId: null,
    note: null,
    createdBy: "user-1",
    createdAt: "2026-08-19T09:00:00Z",
    confirmedBy: "user-1",
    confirmedAt: "2026-08-19T09:00:00Z",
    cancelledBy: null,
    cancelledAt: null,
    cancellationReason: null,
    lines: [],
    subtotals: [{ currency: "USD", minor: 60000 }],
    paymentType: "paid_in_full",
    creditCompanyId: null,
    contractRef: null,
    debt: null,
    tendered: [{ currency: "UZS", minor: 7_620_000 }],
    paid: { minor: 0, currency: "UZS" },
    relieved: { minor: 0, currency: "UZS" },
    remaining: { minor: 0, currency: "UZS" },
    payments: [payment("a", 7_620_000, "UZS")],
    saleRate: null,
    belowCostAlerts: [],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  apiGet.mockResolvedValue([]);
});

describe("TenderPanel", () => {
  it("shows the som taken beside the dollar sale, with neither converted", async () => {
    renderWithProviders(<TenderPanel invoice={sale()} />, { me: SELLER });

    expect(await screen.findByText("$600.00")).toBeInTheDocument();
    expect(screen.getAllByText(/7\s620\s000\s?so'm/).length).toBeGreaterThan(0);
    // The dialog states two figures and never their sum: there is no rate
    // in the system for a combined total to come from (§4.5 rule 1).
    expect(screen.queryByText(/7\s680\s000/)).not.toBeInTheDocument();
  });

  it("keeps a dollar tender and a som tender apart", async () => {
    const mixed = sale({
      tendered: [
        { currency: "USD", minor: 30000 },
        { currency: "UZS", minor: 3_810_000 },
      ],
      payments: [payment("a", 30000, "USD"), payment("b", 3_810_000, "UZS")],
    });

    renderWithProviders(<TenderPanel invoice={mixed} />, { me: SELLER });

    expect(await screen.findByText("$600.00")).toBeInTheDocument();
    expect(screen.getAllByText("$300.00").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/3\s810\s000\s?so'm/).length).toBeGreaterThan(0);
  });

  it("offers to record a tender to whoever may record payments", async () => {
    renderWithProviders(<TenderPanel invoice={sale()} />, { me: SELLER });

    expect(
      await screen.findByRole("button", { name: /record what was taken/i }),
    ).toBeInTheDocument();
  });

  it("stops offering a row once both currencies are recorded", async () => {
    const both = sale({
      payments: [payment("a", 30000, "USD"), payment("b", 3_810_000, "UZS")],
    });

    renderWithProviders(<TenderPanel invoice={both} />, { me: SELLER });

    expect(await screen.findByText(/reverse the row below/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /record what was taken/i }),
    ).not.toBeInTheDocument();
  });

  it("offers a row again once one is reversed", async () => {
    const corrected = sale({
      payments: [
        payment("a", 30000, "USD"),
        payment("b", 3_810_000, "UZS"),
        {
          ...payment("c", -3_810_000, "UZS"),
          reversesPaymentId: "b",
          isReversal: true,
        },
      ],
    });

    renderWithProviders(<TenderPanel invoice={corrected} />, { me: SELLER });

    expect(
      await screen.findByRole("button", { name: /record what was taken/i }),
    ).toBeInTheDocument();
  });

  it("says so when the amount typed is more than the sale charges", async () => {
    const somSale = sale({
      subtotals: [{ currency: "UZS", minor: 7_620_000 }],
      tendered: [],
      payments: [],
    });
    renderWithProviders(<TenderPanel invoice={somSale} />, { me: SELLER });

    await userEvent.click(
      await screen.findByRole("button", { name: /record what was taken/i }),
    );
    await userEvent.type(await screen.findByLabelText(/amount/i), "9000000");

    expect(
      await screen.findByText(/more than the sale charges/i),
    ).toBeInTheDocument();
  });

  it("offers nothing to record on a cancelled sale", async () => {
    renderWithProviders(<TenderPanel invoice={sale({ status: "cancelled" })} />, {
      me: SELLER,
    });

    expect(await screen.findByText("$600.00")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /record what was taken/i }),
    ).not.toBeInTheDocument();
  });
});
