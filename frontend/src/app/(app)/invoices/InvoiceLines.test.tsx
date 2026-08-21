import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import InvoicePage from "@/app/(app)/invoices/[id]/page";
import { Permission } from "@/lib/permissions";
import type { SalesInvoice } from "@/lib/types";
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

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "invoice-1" }),
}));

const invoice: SalesInvoice = {
  id: "invoice-1",
  number: "INV-2026-0001",
  status: "draft",
  locationId: "location-1",
  customerId: null,
  note: null,
  createdBy: "user-1",
  createdAt: "2026-08-19T09:00:00Z",
  confirmedBy: null,
  confirmedAt: null,
  cancelledBy: null,
  cancelledAt: null,
  cancellationReason: null,
  lines: [
    {
      id: "line-1",
      productId: "product-1",
      deviceUnitId: "unit-1",
      quantity: 1,
      trackingType: "serial",
      currency: "USD",
      resolvedPrice: null,
      resolvedPriceMinor: null,
      chargedPrice: null,
      chargedPriceMinor: null,
      lineTotal: null,
      lineTotalMinor: null,
      overridePrice: null,
      overridePriceMinor: null,
      priceApprovedBy: null,
      priceNote: null,
      isDeviation: false,
    },
  ],
  subtotals: [],
};

/** The same invoice, selling a case rather than a handset. */
const accessoryInvoice: SalesInvoice = {
  ...invoice,
  lines: [
    {
      ...invoice.lines[0]!,
      deviceUnitId: null,
      trackingType: "quantity",
      quantity: 1,
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  apiGetPaged.mockResolvedValue({
    items: [],
    pageIndex: 1,
    pageSize: 200,
    pagesCount: 0,
    totalItems: 0,
  });
  apiGet.mockImplementation((path: string) => {
    if (path === "/invoices/invoice-1") return Promise.resolve(invoice);
    if (path === "/device-units/unit-1") {
      // The quote a draft's own payload does not carry (FR-4.5b1).
      return Promise.resolve({ id: "unit-1", currency: "USD", resolvedPriceMinor: 52000 });
    }
    return Promise.resolve([]);
  });
});

function render(permissions: string[]) {
  return renderWithProviders(<InvoicePage />, { me: makeMe(permissions) });
}

describe("the invoice detail page", () => {
  it("quotes a draft line from the handset, since the invoice carries no price", async () => {
    render([Permission.Sales.View, Permission.Sales.Manage, Permission.Catalog.View]);

    // Three times: what resolves, what would be charged, and the total.
    await waitFor(() => expect(screen.getAllByText("$520.00").length).toBe(3));
  });

  it("offers no override to a Seller (FR-4.5)", async () => {
    render([Permission.Sales.View, Permission.Sales.Manage, Permission.Catalog.View]);

    await screen.findByText("INV-2026-0001");
    expect(screen.queryByRole("button", { name: "Override price" })).not.toBeInTheDocument();
    // They can still take the line off — that is Sales.Manage, not pricing.
    expect(screen.getByRole("button", { name: "Remove line" })).toBeInTheDocument();
  });

  it("offers it to a Manager, and sends price and note together", async () => {
    // Sending a note without a price would clear the override outright, so
    // the modal must never split them.
    apiSend.mockResolvedValue(invoice);
    const user = userEvent.setup();
    render([
      Permission.Sales.View,
      Permission.Sales.Manage,
      Permission.Pricing.Override,
      Permission.Catalog.View,
    ]);

    await user.click(await screen.findByRole("button", { name: "Override price" }));
    await user.type(await screen.findByLabelText("Price to charge"), "300");
    await user.type(screen.getByLabelText("Note"), "haggled hard");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(apiSend).toHaveBeenCalledWith("PATCH", "/invoices/invoice-1/lines/line-1", {
        price: "300",
        note: "haggled hard",
      }),
    );
  });

  it("changes an accessory's quantity without naming the line in the body", async () => {
    // The id belongs in the URL; the endpoint declares only price, note and
    // quantity, and a serial line has no quantity to change at all.
    apiSend.mockResolvedValue(accessoryInvoice);
    apiGet.mockImplementation((path: string) =>
      path === "/invoices/invoice-1"
        ? Promise.resolve(accessoryInvoice)
        : Promise.resolve([]),
    );
    apiGetPaged.mockResolvedValue({
      items: [{ id: "product-1", defaultSalePriceMinor: 1200, currency: "USD" }],
      pageIndex: 1,
      pageSize: 200,
      pagesCount: 1,
      totalItems: 1,
    });
    const user = userEvent.setup();
    render([Permission.Sales.View, Permission.Sales.Manage, Permission.Catalog.View]);

    const quantity = await screen.findByLabelText("Quantity");
    await user.clear(quantity);
    await user.type(quantity, "3");

    await waitFor(() =>
      expect(apiSend).toHaveBeenLastCalledWith(
        "PATCH",
        "/invoices/invoice-1/lines/line-1",
        { quantity: 3 },
      ),
    );
  });

  it("has no PDF button while the invoice is a draft", async () => {
    // A draft holds no prices to print, and the server refuses it.
    render([Permission.Sales.View, Permission.Sales.Manage]);

    await screen.findByText("INV-2026-0001");
    expect(screen.queryByRole("link", { name: "Open PDF" })).not.toBeInTheDocument();
  });
});
