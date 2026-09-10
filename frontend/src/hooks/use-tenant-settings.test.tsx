import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmSaleModal } from "@/app/(app)/invoices/ConfirmSaleModal";
import { Permission } from "@/lib/permissions";
import type { SalesInvoice, TenantSettings } from "@/lib/types";
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

const SELLER = makeMe([Permission.CreditSale.Create], "tenant.seller");

function settings(runsTill: boolean): TenantSettings {
  return {
    timezone: "Asia/Tashkent",
    businessName: null,
    address: null,
    hasLogo: false,
    runsTill,
  };
}

function sale(): SalesInvoice {
  return {
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
    lines: [],
    subtotals: [],
    paymentType: "paid_in_full",
    creditCompanyId: null,
    contractRef: null,
    debt: null,
    tendered: [],
    paid: { minor: 0, currency: "UZS" },
    relieved: { minor: 0, currency: "UZS" },
    remaining: { minor: 0, currency: "UZS" },
    payments: [],
    belowCostAlerts: [],
  };
}

function render(runsTill: boolean) {
  apiGet.mockResolvedValue(settings(runsTill));
  apiGetPaged.mockResolvedValue({ items: [], totalItems: 0 });
  renderWithProviders(
    <ConfirmSaleModal
      invoice={sale()}
      quote={[{ currency: "USD", minor: 60000 }]}
      busy={false}
      error={null}
      onClose={vi.fn()}
      onSubmit={vi.fn()}
    />,
    { me: SELLER },
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("the till flag decides what a sale asks for", () => {
  it("offers no tender field to a store that keeps no drawer", async () => {
    render(false);

    // The confirm itself still works; there is simply nothing to state.
    expect(await screen.findByText("Confirm this sale?")).toBeInTheDocument();
    expect(screen.queryByLabelText(/taken/i)).not.toBeInTheDocument();
  });

  it("asks what was taken once the drawer is kept", async () => {
    render(true);

    expect(await screen.findByLabelText(/taken/i)).toBeInTheDocument();
  });
});
