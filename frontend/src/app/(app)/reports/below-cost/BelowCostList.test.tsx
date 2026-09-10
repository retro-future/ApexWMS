import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BelowCostList } from "@/app/(app)/reports/below-cost/BelowCostList";
import { Permission } from "@/lib/permissions";
import { makeMe, renderWithProviders } from "@/test/render";
import type { BelowCostRow } from "@/lib/types";

const { apiGetPaged } = vi.hoisted(() => ({ apiGetPaged: vi.fn() }));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiGetPaged,
}));

const row: BelowCostRow = {
  productId: "product-1",
  sku: "CBL-USB-C",
  productName: "USB-C cable 1m",
  locationId: "location-1",
  locationName: "Chilonzor shop",
  quantity: 12,
  catalogPrice: { minor: 1000, currency: "USD" },
  averageUnitCost: { minor: 1050, currency: "USD" },
  shortfall: { minor: 50, currency: "USD" },
};

function render() {
  apiGetPaged.mockReset();
  apiGetPaged.mockResolvedValue({ items: [row], totalItems: 1, pagesCount: 1 });
  return renderWithProviders(<BelowCostList />, {
    me: makeMe([Permission.Reporting.View]),
  });
}

describe("the below-cost report", () => {
  it("shows the accessory, its location and the shortfall", async () => {
    render();

    expect(await screen.findByText("CBL-USB-C")).toBeInTheDocument();
    expect(screen.getByText("Chilonzor shop")).toBeInTheDocument();
    expect(screen.getByText("$0.50")).toBeInTheDocument();
    expect(screen.getByText("$10.00")).toBeInTheDocument();
  });
});
