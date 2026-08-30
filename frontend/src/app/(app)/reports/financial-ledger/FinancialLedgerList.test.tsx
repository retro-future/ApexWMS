import { describe, expect, it, vi } from "vitest";

import { FinancialLedgerList } from "@/app/(app)/reports/financial-ledger/FinancialLedgerList";
import { Permission } from "@/lib/permissions";
import { makeMe, renderWithProviders } from "@/test/render";

/**
 * The month-end figures link here pre-filtered. The page has to read that
 * filter out of the URL on mount, or the drill-down lands on the whole
 * ledger and the number the owner clicked is lost in it.
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
  return renderWithProviders(<FinancialLedgerList />, {
    me: makeMe([Permission.FinancialLedger.View]),
  });
}

describe("opening the ledger from a drill-down link", () => {
  it("starts filtered to the category and month named in the URL", async () => {
    search.params = new URLSearchParams(
      "txnType=supplier_return_credit&from=2026-08-01&to=2026-08-31",
    );

    render();

    await vi.waitFor(() => expect(apiGetPaged).toHaveBeenCalled());
    const url = apiGetPaged.mock.calls[0][0] as string;
    expect(url).toContain("txnType=supplier_return_credit");
    expect(url).toContain("fromDate=2026-08-01");
    expect(url).toContain("toDate=2026-08-31");
  });

  it("loads the whole ledger when the URL carries no filter", async () => {
    search.params = new URLSearchParams();

    render();

    await vi.waitFor(() => expect(apiGetPaged).toHaveBeenCalled());
    const url = apiGetPaged.mock.calls[0][0] as string;
    expect(url).not.toContain("txnType=");
    expect(url).not.toContain("fromDate=");
  });
});
