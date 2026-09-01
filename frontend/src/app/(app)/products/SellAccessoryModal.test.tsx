import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SellAccessoryModal } from "@/app/(app)/products/SellAccessoryModal";
import { Permission } from "@/lib/permissions";
import type { Product } from "@/lib/types";
import { makeMe, renderWithProviders } from "@/test/render";

const { apiSend, apiGetPaged } = vi.hoisted(() => ({
  apiSend: vi.fn(),
  apiGetPaged: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiSend,
  apiGetPaged,
}));

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh: vi.fn() }),
}));

const product = {
  id: "case-1",
  name: "Clear case",
  sku: "CASE-CLR",
  trackingType: "quantity",
  isActive: true,
  defaultSalePriceMinor: 50000,
} as unknown as Product;

beforeEach(() => {
  vi.clearAllMocks();
  apiGetPaged.mockImplementation((path: string) =>
    Promise.resolve({
      items: path.startsWith("/locations")
        ? [{ id: "loc-1", name: "Main Store" }]
        : [],
      pageIndex: 1,
      pageSize: 200,
      pagesCount: 1,
      totalItems: 1,
    }),
  );
});

describe("SellAccessoryModal", () => {
  it("opens an invoice, adds the accessory line, and lands on the invoice", async () => {
    apiSend.mockImplementation((method: string, path: string) => {
      if (path === "/invoices") return Promise.resolve({ id: "invoice-9" });
      return Promise.resolve({});
    });
    const user = userEvent.setup();
    renderWithProviders(
      <SellAccessoryModal product={product} onClose={vi.fn()} />,
      { me: makeMe([Permission.Sales.Manage]) },
    );

    await user.click(await screen.findByRole("combobox", { name: "Location" }));
    await user.click(await screen.findByRole("option", { name: "Main Store" }));
    await user.click(screen.getByRole("button", { name: "Sell this accessory" }));

    await waitFor(() =>
      expect(apiSend).toHaveBeenCalledWith("POST", "/invoices/invoice-9/lines", {
        productId: "case-1",
        quantity: 1,
      }),
    );
    expect(push).toHaveBeenCalledWith("/invoices/invoice-9");
  });
});
