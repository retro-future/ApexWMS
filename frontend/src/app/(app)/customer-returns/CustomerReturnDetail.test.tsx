import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CustomerReturnPage from "@/app/(app)/customer-returns/[id]/page";
import { Permission } from "@/lib/permissions";
import type { CustomerReturn, DocumentStatus } from "@/lib/types";
import { makeMe, renderWithProviders } from "@/test/render";

const { apiGet, apiGetPaged } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiGetPaged: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiGet,
  apiGetPaged,
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "return-1" }),
}));

function customerReturn(
  status: DocumentStatus,
  overrides: Partial<CustomerReturn> = {},
): CustomerReturn {
  return {
    id: "return-1",
    number: "CR-2026-0001",
    status,
    salesInvoiceId: "invoice-1",
    customerId: "customer-1",
    locationId: "location-1",
    reason: "defective",
    debtReliefMinor: null,
    note: null,
    createdBy: "user-1",
    createdAt: "2026-08-19T09:00:00Z",
    confirmedAt: status === "draft" ? null : "2026-08-19T10:00:00Z",
    cancelledAt: status === "cancelled" ? "2026-08-19T11:00:00Z" : null,
    cancellationReason: null,
    lines: [
      {
        id: "line-1",
        salesInvoiceLineId: "invoice-line-1",
        productId: "product-1",
        deviceUnitId: "unit-1",
        imei: "490154203237518",
        quantity: 1,
        soldQuantity: 1,
        currency: "USD",
        trackingType: "serial",
        chargedPriceMinor: 90000,
        refundPriceMinor: 90000,
        refundPrice: "900.00",
        lineTotalMinor: 90000,
        isReduced: false,
        refundApprovedBy: null,
        refundNote: null,
      },
    ],
    subtotals: [{ currency: "USD", amount: "900.00", amountMinor: 90000 }],
    lineCount: 1,
    ...overrides,
  };
}

const MANAGER = [
  Permission.CustomerReturn.View,
  Permission.CustomerReturn.Manage,
  Permission.Pricing.Override,
];

beforeEach(() => {
  vi.clearAllMocks();
  apiGetPaged.mockResolvedValue({
    items: [],
    pageIndex: 1,
    pageSize: 200,
    pagesCount: 0,
    totalItems: 0,
  });
});

function render(document: CustomerReturn, permissions: string[] = MANAGER) {
  // The page reads the return and, for the outstanding balance, its sale.
  apiGet.mockImplementation((path: string) =>
    Promise.resolve(
      path.includes("customer-returns") ? document : { paymentType: "paid_in_full" },
    ),
  );
  return renderWithProviders(<CustomerReturnPage />, {
    me: makeMe(permissions),
  });
}

describe("the refund is visible beside what was charged", () => {
  it("shows both figures on a line refunded in full", async () => {
    render(customerReturn("draft"));

    await screen.findByText("CR-2026-0001");
    // Charged and refund are the same amount, so it appears twice.
    expect(await screen.findAllByText("$900.00")).not.toHaveLength(0);
  });

  it("shows what the store kept when the refund was reduced", async () => {
    render(
      customerReturn("draft", {
        lines: [
          {
            ...customerReturn("draft").lines[0],
            refundPriceMinor: 81000,
            refundPrice: "810.00",
            lineTotalMinor: 81000,
            isReduced: true,
            refundApprovedBy: "user-1",
            refundNote: "opened box",
          },
        ],
        subtotals: [{ currency: "USD", amount: "810.00", amountMinor: 81000 }],
      }),
    );

    await screen.findByText("CR-2026-0001");
    // The refund shows on the line and again in the document subtotal.
    expect(await screen.findAllByText("$810.00")).not.toHaveLength(0);
    // 900.00 charged less 810.00 refunded, in the "kept" column and total.
    expect(await screen.findAllByText("$90.00")).not.toHaveLength(0);
  });
});

describe("gating on permissions rather than roles", () => {
  it("offers confirm to a manager while it is a draft", async () => {
    render(customerReturn("draft"));

    await screen.findByText("CR-2026-0001");
    expect(screen.getByRole("button", { name: "Confirm" })).toBeInTheDocument();
  });

  it("hides confirm from someone who may only view", async () => {
    render(customerReturn("draft"), [Permission.CustomerReturn.View]);

    await screen.findByText("CR-2026-0001");
    expect(
      screen.queryByRole("button", { name: "Confirm" }),
    ).not.toBeInTheDocument();
  });

  it("offers cancel only once the return is confirmed", async () => {
    render(customerReturn("confirmed"), [
      ...MANAGER,
      Permission.Document.Cancel,
    ]);

    await screen.findByText("CR-2026-0001");
    expect(screen.getByRole("button", { name: "Cancel document" })).toBeInTheDocument();
  });
});

describe("relieved debt", () => {
  it("says so on a return that wrote some off", async () => {
    render(customerReturn("confirmed", { debtReliefMinor: 7_000_000 }));

    await screen.findByText("CR-2026-0001");
    expect(
      await screen.findByText(/7 000 000 so'm of this sale's debt/),
    ).toBeInTheDocument();
  });

  it("says nothing on a cash sale's return", async () => {
    render(customerReturn("confirmed"));

    await screen.findByText("CR-2026-0001");
    expect(screen.queryByText(/debt was written off/)).not.toBeInTheDocument();
  });
});
