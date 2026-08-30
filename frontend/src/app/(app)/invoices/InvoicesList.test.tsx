import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { InvoicesList } from "@/app/(app)/invoices/InvoicesList";
import { Permission } from "@/lib/permissions";
import { makeMe, renderWithProviders } from "@/test/render";

/**
 * The month-end "store-credit sales booked" figure links here, scoped to the
 * sales confirmed that month. The list has to read `paymentType` and the
 * confirmed-date window out of the URL, or the drill-down shows every sale.
 */

const { apiGetPaged } = vi.hoisted(() => ({ apiGetPaged: vi.fn() }));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiGetPaged,
}));

const search = vi.hoisted(() => ({ params: new URLSearchParams() }));

vi.mock("next/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("next/navigation")>()),
  useSearchParams: () => search.params,
}));

function render() {
  apiGetPaged.mockReset();
  apiGetPaged.mockResolvedValue({ items: [], totalItems: 0, pagesCount: 0 });
  return renderWithProviders(<InvoicesList />, {
    me: makeMe([Permission.Sales.Manage]),
  });
}

function invoicesUrl(): string {
  const call = apiGetPaged.mock.calls
    .map((args) => args[0] as string)
    .find((url) => url.startsWith("/invoices?"));
  if (!call) throw new Error("the invoices list was never queried");
  return call;
}

describe("opening the invoices list from a drill-down link", () => {
  it("starts scoped to store-credit sales confirmed in the month", async () => {
    search.params = new URLSearchParams(
      "paymentType=store_credit&confirmedFrom=2026-08-01&confirmedTo=2026-08-31",
    );

    render();

    await vi.waitFor(() => expect(invoicesUrl).not.toThrow());
    const url = invoicesUrl();
    expect(url).toContain("paymentType=store_credit");
    expect(url).toContain("confirmedFrom=2026-08-01");
    expect(url).toContain("confirmedTo=2026-08-31");
  });

  it("shows a payment-type filter that a seller can drive by hand", async () => {
    search.params = new URLSearchParams();

    render();

    expect(
      await screen.findByPlaceholderText("Any payment type"),
    ).toBeInTheDocument();
  });
});
