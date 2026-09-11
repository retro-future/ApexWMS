import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SellConsole } from "@/app/(app)/invoices/SellConsole";
import { ApiError } from "@/lib/api";
import { Permission } from "@/lib/permissions";
import type { InvoiceScanResult, SalesInvoice } from "@/lib/types";
import { makeMe, renderWithProviders } from "@/test/render";

const { apiSend, scannerProps } = vi.hoisted(() => ({
  apiSend: vi.fn(),
  scannerProps: { onScan: undefined as ((codes: { rawValue: string }[]) => void) | undefined },
}));

vi.mock("@/lib/api", async (importOriginal) => ({
  // ApiError is a real class the console's error handling depends on.
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiSend,
}));

vi.mock("@yudiel/react-qr-scanner", () => ({
  Scanner: (props: { onScan: (codes: { rawValue: string }[]) => void }) => {
    scannerProps.onScan = props.onScan;
    return <div data-testid="scanner" />;
  },
  boundingBox: vi.fn(),
  prepareZXingModule: vi.fn(),
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
  paid: { minor: 0, currency: "UZS" },
  relieved: { minor: 0, currency: "UZS" },
  remaining: { minor: 0, currency: "UZS" },
  tendered: [],
  payments: [],
  saleRate: null,
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
    chargedPrice: null,
    lineTotal: null,
    overridePrice: null,
    priceApprovedBy: null,
    priceNote: null,
    isDeviation: false,
  },
  lineCount: 1,
  resolvedPrice: { minor: 52000, currency: "USD" },
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
    const user = userEvent.setup();
    render();

    await user.click(screen.getByLabelText("Scan with camera"));
    await waitFor(() => expect(screen.getByTestId("scanner")).toBeInTheDocument());
    act(() => scannerProps.onScan?.([{ rawValue: IMEI }]));

    await waitFor(() =>
      expect(apiSend).toHaveBeenCalledWith("POST", "/invoices/invoice-1/scan", {
        code: IMEI,
      }),
    );
  });
});
