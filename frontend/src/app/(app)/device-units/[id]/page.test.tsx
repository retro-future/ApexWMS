import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DeviceUnitPage from "@/app/(app)/device-units/[id]/page";
import { Permission } from "@/lib/permissions";
import type { DeviceUnit } from "@/lib/types";
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
  useParams: () => ({ id: "unit-1" }),
}));

const MANAGER = makeMe(
  [Permission.Cost.View, Permission.Pricing.Set],
  "tenant.manager",
);

function unit(overrides: Partial<DeviceUnit> = {}): DeviceUnit {
  return {
    id: "unit-1",
    imei: "495635906513085",
    imei2: null,
    serialNumber: null,
    productId: "product-1",
    sku: "APPLE-IPHONE-12-64",
    productName: "Apple iPhone 12 64GB",
    status: "in_stock",
    condition: "used",
    locationId: "location-1",
    currency: "USD",
    askingPrice: { minor: 30000, currency: "USD" },
    resolvedPrice: { minor: 30000, currency: "USD" },
    createdAt: "2026-09-01T09:00:00Z",
    acquisitionCost: { minor: 25000, currency: "USD" },
    cashPaid: "3 650 000 so'm",
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  apiGet.mockResolvedValue(unit());
  apiGetPaged.mockResolvedValue({ items: [], totalItems: 0 });
});

describe("DeviceUnitPage", () => {
  it("renders every money figure formatted, never as a raw object", async () => {
    renderWithProviders(<DeviceUnitPage />, { me: MANAGER });

    // Regression: these were built with `${unit.askingPrice} ${unit.currency}`,
    // which TypeScript accepts and which renders "[object Object] USD" once
    // the field carries its own currency.
    expect(await screen.findAllByText("$300.00")).toHaveLength(2);
    expect(screen.getByText("$250.00")).toBeInTheDocument();
    expect(screen.queryByText(/\[object Object\]/)).not.toBeInTheDocument();
  });

  it("shows the som handed over as the inert note it is", async () => {
    renderWithProviders(<DeviceUnitPage />, { me: MANAGER });

    expect(await screen.findByText(/3\s650\s000\s?so'm/)).toBeInTheDocument();
  });

  it("says a used handset is unpriced rather than showing a stray figure", async () => {
    apiGet.mockResolvedValue(unit({ askingPrice: null, resolvedPrice: null }));

    renderWithProviders(<DeviceUnitPage />, { me: MANAGER });

    expect(await screen.findByText("Apple iPhone 12 64GB")).toBeInTheDocument();
    expect(screen.queryByText(/\[object Object\]/)).not.toBeInTheDocument();
  });
});
