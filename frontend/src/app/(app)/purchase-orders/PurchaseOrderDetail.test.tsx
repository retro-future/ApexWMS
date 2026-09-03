import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PurchaseOrderPage from "@/app/(app)/purchase-orders/[id]/page";
import { Permission } from "@/lib/permissions";
import type { DocumentStatus, PurchaseOrder } from "@/lib/types";
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
  useParams: () => ({ id: "order-1" }),
}));

function order(status: DocumentStatus): PurchaseOrder {
  return {
    id: "order-1",
    number: "PO-2026-0001",
    status,
    supplierId: "supplier-1",
    note: null,
    createdBy: "user-1",
    createdAt: "2026-08-19T09:00:00Z",
    confirmedAt: status === "draft" ? null : "2026-08-19T10:00:00Z",
    cancelledAt: status === "cancelled" ? "2026-08-19T11:00:00Z" : null,
    lines: [
      {
        id: "line-1",
        productId: "product-1",
        quantity: 2,
        trackingType: "serial",
        currency: "USD",
        unitCost: "700.00",
        unitCostMinor: 70000,
        totalCost: "1400.00",
        totalCostMinor: 140000,
        receivedQuantity: 0,
      },
    ],
    subtotals: [],
    fulfilment: "pending",
  };
}

const MANAGER = [
  Permission.PurchaseOrder.View,
  Permission.PurchaseOrder.Manage,
  Permission.Cost.View,
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

function render(status: DocumentStatus, permissions: string[] = MANAGER) {
  apiGet.mockResolvedValue(order(status));
  return renderWithProviders(<PurchaseOrderPage />, { me: makeMe(permissions) });
}

const pdfLink = () => screen.queryByRole("link", { name: "Open PDF" });

describe("printing a purchase order", () => {
  it("offers the PDF once the order is confirmed", async () => {
    render("confirmed");

    await screen.findByText("PO-2026-0001");
    expect(pdfLink()).toHaveAttribute(
      "href",
      "/api/backend/purchase-orders/order-1/pdf",
    );
  });

  it("has no button while it is a draft", async () => {
    // The PDF renders only from a confirmed order.
    render("draft");

    await screen.findByText("PO-2026-0001");
    expect(pdfLink()).not.toBeInTheDocument();
  });

  it("still prints a cancelled order, which the page marks as cancelled", async () => {
    render("cancelled");

    await screen.findByText("PO-2026-0001");
    expect(pdfLink()).toBeInTheDocument();
  });

  it("offers nothing to someone who may not see costs", async () => {
    // The page is a list of unit costs, and the server requires Cost.View
    // on top of the order's own read permission (FR-1.7).
    render("confirmed", [Permission.PurchaseOrder.View]);

    await screen.findByText("PO-2026-0001");
    expect(pdfLink()).not.toBeInTheDocument();
  });
});
