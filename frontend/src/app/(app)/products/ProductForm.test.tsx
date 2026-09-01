import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProductForm } from "@/app/(app)/products/ProductForm";
import { Permission } from "@/lib/permissions";
import { makeMe, renderWithProviders } from "@/test/render";

const { apiSend } = vi.hoisted(() => ({ apiSend: vi.fn() }));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiSend,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useParams: () => ({}),
}));

const manager = makeMe([Permission.Catalog.Manage, Permission.Pricing.Set]);

describe("ProductForm create", () => {
  beforeEach(() => {
    apiSend.mockReset();
    apiSend.mockResolvedValue({ id: "product-1" });
  });

  it("omits the SKU when the field is left blank", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProductForm />, { me: manager });

    await user.type(screen.getByLabelText("Name"), "iPhone 15 Pro");
    await user.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(apiSend).toHaveBeenCalled());
    const [, path, payload] = apiSend.mock.calls[0] as [
      string,
      string,
      Record<string, unknown>,
    ];
    expect(path).toBe("/products");
    expect(payload.sku).toBeUndefined();
  });

  it("asks the backend to generate a barcode for an accessory", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProductForm />, { me: manager });

    await user.type(screen.getByLabelText("Name"), "Clear case");
    await user.click(screen.getByRole("combobox", { name: "Tracking" }));
    await user.click(screen.getByRole("option", { name: "Quantity" }));
    await user.click(
      screen.getByLabelText("Generate an in-store barcode automatically"),
    );
    await user.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(apiSend).toHaveBeenCalled());
    const payload = apiSend.mock.calls[0][2] as Record<string, unknown>;
    expect(payload.generateBarcode).toBe(true);
    expect(payload.barcode).toBeUndefined();
  });
});
