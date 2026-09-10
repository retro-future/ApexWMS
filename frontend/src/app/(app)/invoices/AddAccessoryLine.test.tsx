import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AddAccessoryLine } from "@/app/(app)/invoices/AddAccessoryLine";
import { Permission } from "@/lib/permissions";
import type { InvoiceScanResult, SalesInvoice } from "@/lib/types";
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

const invoice = { id: "invoice-1", status: "draft", lines: [] } as unknown as SalesInvoice;

const result: InvoiceScanResult = {
  line: {
    id: "line-1",
    productId: "case-1",
    deviceUnitId: null,
    quantity: 3,
    trackingType: "quantity",
    currency: "UZS",
    resolvedPrice: null,
    chargedPrice: null,
    lineTotal: null,
    overridePrice: null,
    priceApprovedBy: null,
    priceNote: null,
    isDeviation: false,
  },
  lineCount: 1,
  resolvedPrice: { minor: 2500000, currency: "UZS" },
  productId: "case-1",
  deviceUnitId: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  apiGetPaged.mockResolvedValue({
    items: [
      { id: "case-1", name: "Clear case", sku: "CASE-CLR", trackingType: "quantity" },
      { id: "phone-1", name: "iPhone 15", sku: "IP15", trackingType: "serial" },
    ],
    pageIndex: 1,
    pageSize: 50,
    pagesCount: 1,
    totalItems: 2,
  });
});

function render(onAdded = vi.fn()) {
  return renderWithProviders(
    <AddAccessoryLine invoice={invoice} onAdded={onAdded} />,
    { me: makeMe([Permission.Sales.Manage]) },
  );
}

async function pickCase(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("combobox", { name: "Accessory" }));
  expect(
    await screen.findByRole("option", { name: /Clear case/ }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: /iPhone 15/ })).not.toBeInTheDocument();
  await user.click(screen.getByRole("option", { name: /Clear case/ }));
}

describe("AddAccessoryLine", () => {
  it("adds the picked accessory and quantity, and hides phones from the list", async () => {
    apiSend.mockResolvedValue(result);
    const onAdded = vi.fn();
    const user = userEvent.setup();
    render(onAdded);

    await pickCase(user);
    const quantity = screen.getByLabelText("Quantity to add");
    await user.clear(quantity);
    await user.type(quantity, "3");
    await user.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() =>
      expect(apiSend).toHaveBeenCalledWith("POST", "/invoices/invoice-1/lines", {
        productId: "case-1",
        quantity: 3,
      }),
    );
    expect(onAdded).toHaveBeenCalledWith(result);
  });

  it("shows the server's refusal verbatim", async () => {
    const { ApiError } = await import("@/lib/api");
    apiSend.mockRejectedValue(
      new ApiError(409, "Clear case has no catalog price — an Owner or Manager must price it"),
    );
    const user = userEvent.setup();
    render();

    await pickCase(user);
    await user.click(screen.getByRole("button", { name: "Add" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("no catalog price");
  });
});
