import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmSaleModal } from "@/app/(app)/invoices/ConfirmSaleModal";
import { Permission } from "@/lib/permissions";
import type { CurrentRates, SalesInvoice, TenantSettings } from "@/lib/types";
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

const SETTINGS: TenantSettings = {
  timezone: "Asia/Tashkent",
  businessName: null,
  address: null,
  hasLogo: false,
  // Off, the way every existing store has it. The tender no longer depends
  // on it (W9 B1); the flag now only gates the shift screens.
  runsTill: false,
};

function rates(somPerUsd: string | null): CurrentRates {
  if (somPerUsd === null) return { sale: null, buyback: null, today: "2026-08-19" };
  return {
    sale: {
      id: "rate-1",
      kind: "sale",
      somPerUsd,
      effectiveOn: "2026-08-19",
      setAt: "2026-08-19T06:00:00Z",
      userId: "user-1",
      isStale: false,
    },
    buyback: null,
    today: "2026-08-19",
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
    saleRate: null,
    belowCostAlerts: [],
  };
}

function render(somPerUsd: string | null) {
  apiGet.mockImplementation((path: string) =>
    Promise.resolve(path.startsWith("/exchange-rates") ? rates(somPerUsd) : SETTINGS),
  );
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

describe("what the customer handed over", () => {
  it("is asked for even when the store keeps no drawer", async () => {
    render(null);

    expect(await screen.findByLabelText(/taken/i)).toBeInTheDocument();
  });

  it("shows what the dollar total works out to at the day's rate", async () => {
    render("12000");

    // $600 at 12 000, as a hint under the field. It is never written into
    // the field: what was taken is a fact, not a figure the screen guessed.
    expect(await screen.findByText(/7 200 000/)).toBeInTheDocument();
    expect((await screen.findByLabelText(/taken/i)).getAttribute("value")).toBe("");
  });

  it("says nothing about a rate the store has not quoted", async () => {
    render(null);

    await screen.findByLabelText(/taken/i);
    expect(screen.queryByText(/at 12 000/)).not.toBeInTheDocument();
  });
});
