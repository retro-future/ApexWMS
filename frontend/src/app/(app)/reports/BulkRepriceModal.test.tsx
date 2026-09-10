import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BulkRepriceModal } from "@/app/(app)/reports/BulkRepriceModal";
import { Permission } from "@/lib/permissions";
import { makeMe, renderWithProviders } from "@/test/render";
import type { DeviceUnit } from "@/lib/types";

const { apiGet, apiSend } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiSend: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiGet,
  apiSend,
}));

function unit(id: string, imei: string): DeviceUnit {
  return {
    id,
    imei,
    imei2: null,
    serialNumber: null,
    productId: "product-1",
    sku: "IPH13-128",
    productName: "iPhone 13 128GB",
    status: "in_stock",
    condition: "used",
    locationId: "location-1",
    currency: "USD",
    askingPrice: null,
    resolvedPrice: null,
    createdAt: "2026-01-04T09:00:00Z",
  };
}

const units = [unit("unit-1", "490154203237518"), unit("unit-2", "356938035643809")];

describe("BulkRepriceModal", () => {
  beforeEach(() => {
    apiGet.mockReset();
    apiSend.mockReset();
    apiGet.mockImplementation((path: string) =>
      Promise.resolve(units.find((one) => path.endsWith(one.id))),
    );
    apiSend.mockResolvedValue(2);
  });

  it("sends only the handsets a price was stated for", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <BulkRepriceModal
        deviceUnitIds={["unit-1", "unit-2"]}
        onClose={() => {}}
        onDone={() => {}}
      />,
      { me: makeMe([Permission.Pricing.Set]) },
    );

    await user.type(
      await screen.findByLabelText("New price 490154203237518"),
      "360.00",
    );
    await user.type(screen.getByLabelText("Reason"), "Ramadan clearance");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(apiSend).toHaveBeenCalledWith("POST", "/device-units/price", {
        prices: [{ deviceUnitId: "unit-1", askingPrice: "360.00" }],
        reason: "Ramadan clearance",
      }),
    );
  });

  it("refuses a price the currency cannot express", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <BulkRepriceModal
        deviceUnitIds={["unit-1"]}
        onClose={() => {}}
        onDone={() => {}}
      />,
      { me: makeMe([Permission.Pricing.Set]) },
    );

    await user.type(await screen.findByLabelText("New price 490154203237518"), "360.999");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText(/two decimals/i)).toBeInTheDocument();
    expect(apiSend).not.toHaveBeenCalled();
  });
});
