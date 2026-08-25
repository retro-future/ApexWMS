import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SupplierReturnPage from "@/app/(app)/supplier-returns/[id]/page";
import { Permission } from "@/lib/permissions";
import type { DocumentStatus, SupplierReturn } from "@/lib/types";
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

function supplierReturn(status: DocumentStatus): SupplierReturn {
  return {
    id: "return-1",
    number: "SR-2026-0001",
    status,
    supplierId: "supplier-1",
    locationId: "location-1",
    reason: "defective",
    note: null,
    createdBy: "user-1",
    createdAt: "2026-08-19T09:00:00Z",
    confirmedAt: status === "draft" ? null : "2026-08-19T10:00:00Z",
    cancelledAt: status === "cancelled" ? "2026-08-19T11:00:00Z" : null,
    cancellationReason: null,
    lines: [
      {
        id: "line-1",
        productId: "product-1",
        deviceUnitId: "unit-1",
        imei: "490154203237518",
        quantity: 1,
        currency: "USD",
        trackingType: "serial",
      },
    ],
    lineCount: 1,
  };
}

const MANAGER = [
  Permission.SupplierReturn.View,
  Permission.SupplierReturn.Manage,
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
  apiGet.mockResolvedValue(supplierReturn(status));
  return renderWithProviders(<SupplierReturnPage />, {
    me: makeMe(permissions),
  });
}

const pdfLink = () => screen.queryByRole("link", { name: "Open PDF" });

describe("printing a return note", () => {
  it("offers the PDF once the goods have gone back", async () => {
    render("confirmed");

    await screen.findByText("SR-2026-0001");
    expect(pdfLink()).toHaveAttribute(
      "href",
      "/api/backend/supplier-returns/return-1/pdf",
    );
  });

  it("has no button while it is a draft", async () => {
    // Nothing has left the shelf yet, and the server refuses it.
    render("draft");

    await screen.findByText("SR-2026-0001");
    expect(pdfLink()).not.toBeInTheDocument();
  });

  it("still prints a cancelled return", async () => {
    render("cancelled");

    await screen.findByText("SR-2026-0001");
    expect(pdfLink()).toBeInTheDocument();
  });

  it("needs no cost permission, because the note carries no money", async () => {
    render("confirmed", [Permission.SupplierReturn.View]);

    await screen.findByText("SR-2026-0001");
    expect(pdfLink()).toBeInTheDocument();
  });
});
