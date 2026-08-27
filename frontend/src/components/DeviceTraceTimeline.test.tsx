import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DeviceTraceTimeline } from "@/components/DeviceTraceTimeline";
import { Permission } from "@/lib/permissions";
import { makeMe, renderWithProviders } from "@/test/render";
import type { DeviceTrace, DeviceUnit, TraceEvent } from "@/lib/types";

const { apiGet } = vi.hoisted(() => ({ apiGet: vi.fn() }));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiGet,
}));

const unit: DeviceUnit = {
  id: "unit-1",
  imei: "490154203237518",
  imei2: null,
  serialNumber: null,
  productId: "product-1",
  sku: "IPH13-128",
  productName: "iPhone 13 128GB",
  status: "sold",
  condition: "used",
  locationId: "location-1",
  currency: "USD",
  askingPrice: "360.00",
  resolvedPrice: "360.00",
  resolvedPriceMinor: 36000,
  createdAt: "2026-01-04T09:00:00Z",
};

function event(overrides: Partial<TraceEvent>): TraceEvent {
  return {
    kind: "priced",
    occurredAt: "2026-01-04T09:00:00Z",
    userId: "user-1",
    userName: "Dilnoza",
    note: null,
    documentType: null,
    documentId: null,
    documentNumber: null,
    locationId: null,
    locationName: null,
    oldPrice: null,
    oldPriceMinor: null,
    newPrice: null,
    newPriceMinor: null,
    origin: null,
    sale: null,
    ...overrides,
  };
}

/** The M8 demo: bought, priced, cut, sold below asking, with the approver. */
const trace: DeviceTrace = {
  unit,
  events: [
    event({
      kind: "received",
      documentType: "goods_receipt",
      documentId: "receipt-1",
      documentNumber: "GR-2026-0001",
      locationName: "Chorsu store",
      origin: {
        acquisitionSource: "trade_in",
        supplierId: null,
        supplierName: null,
        customerId: "customer-1",
        customerName: "Aziz Karimov",
      },
    }),
    event({ newPrice: "420.00", newPriceMinor: 42000 }),
    event({
      occurredAt: "2026-02-01T09:00:00Z",
      oldPrice: "420.00",
      oldPriceMinor: 42000,
      newPrice: "390.00",
      newPriceMinor: 39000,
    }),
    event({
      kind: "sold",
      occurredAt: "2026-03-01T09:00:00Z",
      documentType: "sales_invoice",
      documentId: "invoice-1",
      documentNumber: "INV-2026-0007",
      sale: {
        invoiceId: "invoice-1",
        invoiceNumber: "INV-2026-0007",
        customerId: "customer-2",
        customerName: "Nodira Yusupova",
        resolvedPrice: "390.00",
        resolvedPriceMinor: 39000,
        chargedPrice: "350.00",
        chargedPriceMinor: 35000,
        priceApprovedBy: "user-2",
        priceApprovedByName: "Rustam Manager",
        priceNote: "Regular customer",
      },
    }),
  ],
};

describe("DeviceTraceTimeline", () => {
  beforeEach(() => {
    apiGet.mockReset();
    apiGet.mockResolvedValue(trace);
  });

  it("renders the handset's whole life, prices and approver included", async () => {
    renderWithProviders(<DeviceTraceTimeline deviceUnitId="unit-1" />, {
      me: makeMe([Permission.Catalog.View]),
    });

    expect(await screen.findByText("Traded in from Aziz Karimov")).toBeInTheDocument();
    expect(screen.getByText("Priced at $420.00")).toBeInTheDocument();
    expect(screen.getByText("$420.00 → $390.00")).toBeInTheDocument();
    expect(screen.getByText("$350.00")).toBeInTheDocument();
    expect(screen.getByText("Price overridden")).toBeInTheDocument();
    expect(screen.getByText("System price was $390.00")).toBeInTheDocument();
    expect(screen.getByText("Rustam Manager")).toBeInTheDocument();
  });

  it("links each event to the document it came from", async () => {
    renderWithProviders(<DeviceTraceTimeline deviceUnitId="unit-1" />, {
      me: makeMe([Permission.Catalog.View]),
    });

    expect(await screen.findByRole("link", { name: "GR-2026-0001" })).toHaveAttribute(
      "href",
      "/receipts/receipt-1",
    );
    expect(screen.getAllByRole("link", { name: "INV-2026-0007" })[0]).toHaveAttribute(
      "href",
      "/invoices/invoice-1",
    );
  });
});
