import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SellConsole } from "@/app/(app)/invoices/SellConsole";
import { ApiError } from "@/lib/api";
import { Permission } from "@/lib/permissions";
import type { InvoiceScanResult, SalesInvoice } from "@/lib/types";
import { makeMe, renderWithProviders } from "@/test/render";

const { apiSend, decodeFromConstraints } = vi.hoisted(() => ({
  apiSend: vi.fn(),
  decodeFromConstraints: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => ({
  // ApiError is a real class the console's error handling depends on.
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiSend,
}));

vi.mock("@zxing/browser", () => ({
  BrowserMultiFormatReader: vi.fn().mockImplementation(function BrowserMultiFormatReaderMock() {
    return { decodeFromConstraints };
  }),
}));

const IMEI = "490154203237518";

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
  lines: [],
  subtotals: [],
  paymentType: "paid_in_full",
  creditCompanyId: null,
  contractRef: null,
  debt: null,
  debtMinor: null,
  paidMinor: 0,
  remainingMinor: 0,
  payments: [],
  belowCostAlerts: [],
};

const result: InvoiceScanResult = {
  line: {
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
  lineCount: 1,
  resolvedPrice: "520.00",
  resolvedPriceMinor: 52000,
  productId: "product-1",
  deviceUnitId: "unit-1",
};

/** The wedge scanner types into whatever has focus, then sends Enter. */
async function scan(user: ReturnType<typeof userEvent.setup>, code: string) {
  const input = screen.getByLabelText(
    "Scan or type an IMEI or barcode, then press Enter",
  );
  await user.type(input, `${code}{Enter}`);
  return input as HTMLInputElement;
}

function render(onScanned = vi.fn()) {
  return renderWithProviders(
    <SellConsole invoice={invoice} onScanned={onScanned} />,
    { me: makeMe([Permission.Sales.Manage]) },
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("SellConsole", () => {
  it("sends the raw code and nothing else — the server decides what it was", async () => {
    // FR-7.1: the operator's scanner does not know whether it read an IMEI
    // off a handset or a barcode off a box, so neither does the client.
    apiSend.mockResolvedValue(result);
    const onScanned = vi.fn();
    const user = userEvent.setup();
    render(onScanned);

    const input = await scan(user, IMEI);

    await waitFor(() => expect(apiSend).toHaveBeenCalledTimes(1));
    expect(apiSend).toHaveBeenCalledWith("POST", "/invoices/invoice-1/scan", {
      code: IMEI,
    });
    await waitFor(() => expect(input).toHaveValue(""));
    // The next scan lands here or it lands nowhere.
    expect(input).toHaveFocus();
    expect(onScanned).toHaveBeenCalledWith(result);
  });

  it("reads back the quote the server returned, not a stored price", async () => {
    apiSend.mockResolvedValue(result);
    const user = userEvent.setup();
    render();

    await scan(user, IMEI);

    expect(
      await screen.findByText("Added at $520.00 · 1 line(s) on this invoice"),
    ).toBeInTheDocument();
  });

  it("keeps a refusal on screen verbatim, with the code still readable", async () => {
    // FR-4.2b's message names who can fix it, because the Seller reading it
    // cannot. Paraphrasing that away is the whole failure mode.
    const message =
      "490154203237518 is used and carries no asking price — an Owner or Manager must price it";
    apiSend.mockRejectedValue(new ApiError(409, message));
    const user = userEvent.setup();
    render();

    const input = await scan(user, IMEI);

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(input).toHaveValue(IMEI);
    expect(input).toHaveFocus();
  });

  it("replaces the refusal once the next scan is accepted", async () => {
    apiSend.mockRejectedValueOnce(new ApiError(409, "already sold"));
    const user = userEvent.setup();
    render();

    await scan(user, IMEI);
    expect(await screen.findByRole("alert")).toBeInTheDocument();

    apiSend.mockResolvedValue(result);
    await scan(user, "{selectall}other-code");

    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  });

  it("sends nothing for an empty scan", async () => {
    const user = userEvent.setup();
    render();

    await scan(user, "   ");

    expect(apiSend).not.toHaveBeenCalled();
  });

  it("submits a camera-decoded code through the same scan path", async () => {
    apiSend.mockResolvedValue(result);
    let callback: (result: { getText: () => string }) => void = () => {};
    decodeFromConstraints.mockImplementation(
      (_constraints: unknown, _preview: unknown, cb: typeof callback) => {
        callback = cb;
        return Promise.resolve({ stop: vi.fn() });
      },
    );
    const user = userEvent.setup();
    render();

    await user.click(screen.getByLabelText("Scan with camera"));
    await waitFor(() => expect(decodeFromConstraints).toHaveBeenCalled());
    act(() => callback({ getText: () => IMEI }));

    await waitFor(() =>
      expect(apiSend).toHaveBeenCalledWith("POST", "/invoices/invoice-1/scan", {
        code: IMEI,
      }),
    );
  });
});
