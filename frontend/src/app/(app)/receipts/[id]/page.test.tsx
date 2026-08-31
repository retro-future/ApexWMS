import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ReceiptPage from "@/app/(app)/receipts/[id]/page";
import { Permission } from "@/lib/permissions";
import type { GoodsReceipt } from "@/lib/types";
import { makeMe, renderWithProviders } from "@/test/render";

const { apiGet, apiGetPaged, apiSend } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiGetPaged: vi.fn(),
  apiSend: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiGet,
  apiGetPaged,
  apiSend,
}));

const notifySuccess = vi.fn();
vi.mock("@/lib/notify", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/notify")>()),
  notifySuccess: (message: string) => notifySuccess(message),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "receipt-1" }),
}));

function receipt(status: GoodsReceipt["status"]): GoodsReceipt {
  return {
    id: "receipt-1",
    number: "GR-2026-0001",
    status,
    acquisitionSource: "supplier",
    supplierId: "supplier-1",
    customerId: null,
    purchaseOrderId: null,
    locationId: "location-1",
    note: null,
    createdBy: "user-1",
    createdAt: "2026-08-14T09:00:00Z",
    confirmedAt: null,
    cancelledAt: null,
    lines: [
      {
        id: "line-1",
        productId: "product-1",
        quantity: 5,
        trackingType: "quantity",
        currency: "USD",
        scannedCount: 0,
        units: [],
      },
    ],
    subtotals: [],
    belowCostAlerts: [],
  };
}

const MANAGER = [Permission.Receiving.Manage, Permission.Cost.View];

beforeEach(() => {
  vi.clearAllMocks();
  apiGetPaged.mockResolvedValue({
    items: [],
    pageIndex: 1,
    pageSize: 200,
    pagesCount: 0,
    totalItems: 0,
  });
  apiGet.mockResolvedValue(receipt("draft"));
});

describe("confirming a goods receipt below cost", () => {
  it("shows a non-blocking yellow warning for each accessory that now sells below cost", async () => {
    apiSend.mockResolvedValue({
      ...receipt("confirmed"),
      belowCostAlerts: [
        {
          productId: "product-1",
          sku: "USB-C-CABLE",
          catalogPrice: "5.00",
          catalogPriceMinor: 500,
          averageUnitCost: "5.40",
          averageUnitCostMinor: 540,
        },
      ],
    });
    const user = userEvent.setup();

    renderWithProviders(<ReceiptPage />, { me: makeMe(MANAGER) });

    await screen.findByText("GR-2026-0001");
    await user.click(screen.getByRole("button", { name: "Confirm" }));

    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Confirm" }));

    const alert = await screen.findByText(
      "This receipt raised cost above catalog price",
    );
    const block = alert.closest("[role='alert']") ?? alert.parentElement!;
    expect(within(block as HTMLElement).getByText(/USB-C-CABLE/)).toHaveTextContent(
      "USB-C-CABLE: sells at 5.00, now costs 5.40",
    );
    expect(
      within(block as HTMLElement).getByRole("link", { name: /USB-C-CABLE/ }),
    ).toHaveAttribute("href", "/products/product-1");

    // The confirm still succeeded — the warning is additive, not a blocker.
    expect(apiSend).toHaveBeenCalledWith("POST", "/receipts/receipt-1/confirm", {});
    await waitFor(() => expect(notifySuccess).toHaveBeenCalledWith("Confirmed"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows no warning when nothing came back below cost", async () => {
    apiSend.mockResolvedValue(receipt("confirmed"));
    const user = userEvent.setup();

    renderWithProviders(<ReceiptPage />, { me: makeMe(MANAGER) });

    await screen.findByText("GR-2026-0001");
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Confirm" }));

    await waitFor(() => expect(notifySuccess).toHaveBeenCalled());
    expect(
      screen.queryByText("This receipt raised cost above catalog price"),
    ).not.toBeInTheDocument();
  });
});
