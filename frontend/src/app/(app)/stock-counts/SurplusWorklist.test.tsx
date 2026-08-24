import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SurplusWorklist } from "@/app/(app)/stock-counts/SurplusWorklist";
import { Permission } from "@/lib/permissions";
import { makeMe, renderWithProviders } from "@/test/render";
import type { Product, StockCount, StockCountUnit } from "@/lib/types";

const { apiSend, apiGetPaged } = vi.hoisted(() => ({
  apiSend: vi.fn(),
  apiGetPaged: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiSend,
  apiGetPaged,
}));

const IMEI = "490154203237518";

const product: Product = {
  id: "product-1",
  sku: "IPH13-128",
  name: "iPhone 13 128GB",
  brand: "Apple",
  model: "13",
  trackingType: "serial",
  currency: "USD",
  barcode: null,
  defaultSalePrice: "900.00",
  defaultSalePriceMinor: 90000,
  isActive: true,
};

const count: StockCount = {
  id: "count-1",
  number: "SC-2026-0001",
  status: "draft",
  locationId: "location-1",
  note: null,
  createdBy: "user-1",
  createdAt: "2026-08-14T09:00:00Z",
  closedAt: "2026-08-14T17:00:00Z",
  confirmedAt: null,
  cancelledAt: null,
  cancellationReason: null,
  units: [],
  lines: [],
  matchedCount: 0,
  missingCount: 0,
  unexpectedCount: 1,
};

/** Known model, nobody stated a cost. Only the money is missing. */
const unpriced: StockCountUnit = {
  id: "unit-1",
  imei: IMEI,
  deviceUnitId: null,
  productId: "product-1",
  expected: false,
  scanned: true,
  outcome: "unexpected",
  isSurprise: true,
  acquisitionCost: null,
  acquisitionCostMinor: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  apiGetPaged.mockResolvedValue({
    items: [product],
    pageIndex: 1,
    pageSize: 200,
    pagesCount: 1,
    totalItems: 1,
  });
});

describe("SurplusWorklist", () => {
  it("renders nothing when no surplus needs a value", () => {
    renderWithProviders(
      <SurplusWorklist count={count} units={[]} onFixed={vi.fn()} />,
      { me: makeMe([Permission.Cost.View, Permission.Pricing.Set]) },
    );

    expect(screen.queryByText("Surplus needing a value")).not.toBeInTheDocument();
  });

  it("states a cost by re-scanning the IMEI with its product", async () => {
    // A repeat beep on a count changes nothing about what was found, and may
    // carry the product and cost the first one lacked.
    apiSend.mockResolvedValue({
      unit: { ...unpriced, acquisitionCostMinor: 30000 },
      line: null,
      matchedCount: 0,
      missingCount: 0,
      unexpectedCount: 1,
    });
    const onFixed = vi.fn();
    const user = userEvent.setup();

    renderWithProviders(
      <SurplusWorklist count={count} units={[unpriced]} onFixed={onFixed} />,
      { me: makeMe([Permission.Cost.View, Permission.Pricing.Set, Permission.Catalog.View]) },
    );

    // The row's currency comes from the catalog list, so wait for it: a cost
    // cannot be checked before the model it is denominated in is known.
    await screen.findByText("iPhone 13 128GB (IPH13-128)");
    await user.type(screen.getByLabelText(`Cost for ${IMEI}`), "300.00");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(apiSend).toHaveBeenCalledWith("POST", "/stock-counts/count-1/scan", {
        code: IMEI,
        productId: "product-1",
        acquisitionCost: "300.00",
      }),
    );
    expect(onFixed).toHaveBeenCalled();
  });

  it("will not save until a cost is stated", async () => {
    renderWithProviders(
      <SurplusWorklist count={count} units={[unpriced]} onFixed={vi.fn()} />,
      { me: makeMe([Permission.Cost.View, Permission.Pricing.Set, Permission.Catalog.View]) },
    );

    expect(await screen.findByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("refuses a cost with decimals in a currency that has no minor unit", async () => {
    const user = userEvent.setup();
    apiGetPaged.mockResolvedValue({
      items: [{ ...product, currency: "UZS" as const }],
      pageIndex: 1,
      pageSize: 200,
      pagesCount: 1,
      totalItems: 1,
    });

    renderWithProviders(
      <SurplusWorklist count={count} units={[unpriced]} onFixed={vi.fn()} />,
      { me: makeMe([Permission.Cost.View, Permission.Pricing.Set, Permission.Catalog.View]) },
    );

    await screen.findByText("iPhone 13 128GB (IPH13-128)");
    await user.type(screen.getByLabelText(`Cost for ${IMEI}`), "4200000.50");

    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("shows a Storekeeper the count and no way to act on it", () => {
    // Without Cost.View the cost field is absent from every row, so the list
    // cannot be computed honestly — say how many and who can fix them.
    renderWithProviders(
      <SurplusWorklist count={count} units={[unpriced]} onFixed={vi.fn()} />,
      { me: makeMe([Permission.StockCount.Run]) },
    );

    expect(
      screen.getByText(
        "1 handsets turned up that the store does not hold. An Owner or Manager has to state what they cost before this count can be applied.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
  });

  it("shows the list read-only to someone who may see cost but not set it", async () => {
    renderWithProviders(
      <SurplusWorklist count={count} units={[unpriced]} onFixed={vi.fn()} />,
      { me: makeMe([Permission.Cost.View]) },
    );

    expect(
      await screen.findByText("An Owner or Manager has to state these costs."),
    ).toBeInTheDocument();
    expect(screen.getByText(IMEI)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
  });
});
