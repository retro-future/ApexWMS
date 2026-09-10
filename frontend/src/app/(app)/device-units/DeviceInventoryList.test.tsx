import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DeviceInventoryList } from "@/app/(app)/device-units/DeviceInventoryList";
import { Permission } from "@/lib/permissions";
import { makeMe, renderWithProviders } from "@/test/render";
import type { DeviceInventoryRow } from "@/lib/types";

const { apiGetPaged } = vi.hoisted(() => ({ apiGetPaged: vi.fn() }));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiGetPaged,
}));

const base: DeviceInventoryRow = {
  deviceUnitId: "unit-1",
  imei: "490154203237518",
  imei2: null,
  serialNumber: null,
  productId: "product-1",
  sku: "IP15P-256",
  productName: "iPhone 15 Pro",
  brand: "Apple",
  condition: "used",
  status: "in_stock",
  wasCustomerReturned: true,
  locationId: "location-1",
  locationName: "Chilonzor shop",
  since: "2026-01-01T00:00:00Z",
  daysInStock: 40,
  askingPrice: { minor: 50000, currency: "USD" },
  resolvedPrice: { minor: 50000, currency: "USD" },
  sourceDocumentType: "goods_receipt",
  sourceDocumentId: "receipt-1",
  acquisitionCost: { minor: 38000, currency: "USD" },
  impliedMargin: { minor: 12000, currency: "USD" },
};

function render(
  rows: DeviceInventoryRow[],
  permissions = [Permission.Reporting.View, Permission.Cost.View],
) {
  apiGetPaged.mockReset();
  apiGetPaged.mockImplementation((path: string) =>
    Promise.resolve(
      path.startsWith("/reports/device-units")
        ? { items: rows, totalItems: rows.length, pagesCount: 1 }
        : { items: [], totalItems: 0, pagesCount: 1 },
    ),
  );
  return renderWithProviders(<DeviceInventoryList />, { me: makeMe(permissions) });
}

describe("the device inventory list", () => {
  it("shows the handset, its status and the returned marker", async () => {
    render([base]);

    expect(await screen.findByText("iPhone 15 Pro")).toBeInTheDocument();
    expect(screen.getByText("490154203237518")).toBeInTheDocument();
    expect(screen.getByText("$500.00")).toBeInTheDocument();
    expect(screen.getByText("$120.00")).toBeInTheDocument();
    expect(screen.getAllByText("Returned by customer").length).toBeGreaterThan(0);
  });

  it("passes the status filter to the query", async () => {
    render([base]);
    await screen.findByText("iPhone 15 Pro");

    await userEvent.click(screen.getByRole("combobox", { name: "Status" }));
    await userEvent.click(
      await screen.findByRole("option", { name: "Returned by customer" }),
    );

    await waitFor(() => {
      expect(apiGetPaged).toHaveBeenLastCalledWith(
        expect.stringContaining("status=customer_returned"),
      );
    });
  });

  it("hides cost and margin when the payload omits them", async () => {
    const trimmed: DeviceInventoryRow = {
      ...base,
      acquisitionCost: undefined,
      impliedMargin: undefined,
    };
    render([trimmed], [Permission.Reporting.View]);

    await screen.findByText("iPhone 15 Pro");
    expect(screen.queryByText("$380.00")).not.toBeInTheDocument();
    expect(screen.queryByText("$120.00")).not.toBeInTheDocument();
  });
});
