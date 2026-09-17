import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ScanConsole } from "@/app/(app)/receipts/ScanConsole";
import { ApiError } from "@/lib/api";
import { Permission } from "@/lib/permissions";
import { makeMe, renderWithProviders } from "@/test/render";
import type { GoodsReceipt, ScanResult } from "@/lib/types";

const { apiSend, apiGet, apiGetPaged, scannerProps } = vi.hoisted(() => ({
  apiSend: vi.fn(),
  apiGet: vi.fn(),
  apiGetPaged: vi.fn(),
  scannerProps: { onScan: undefined as ((codes: { rawValue: string }[]) => void) | undefined },
}));

vi.mock("@/lib/api", async (importOriginal) => ({
  // ApiError is a real class the console's error handling depends on.
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiSend,
  apiGet,
  apiGetPaged,
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

const receipt: GoodsReceipt = {
  id: "receipt-1",
  number: "GR-2026-0001",
  status: "draft",
  acquisitionSource: "supplier",
  supplierId: "supplier-1",
  customerId: null,
  purchaseOrderId: null,
  locationId: "location-1",
  note: null,
  createdBy: "user-1",
  createdAt: "2026-08-14T09:00:00Z",
  confirmedAt: null,
  cancelledAt: null,
  lines: [
    {
      id: "line-1",
      productId: "product-1",
      quantity: 10,
      trackingType: "serial",
      currency: "USD",
      scannedCount: 0,
      units: [],
    },
  ],
  subtotals: [],
  belowCostAlerts: [],
};

function scanResult(imei: string): ScanResult {
  return {
    lineId: "line-1",
    scannedCount: 1,
    expectedCount: 10,
    unit: {
      id: "unit-1",
      imei,
      imei2: null,
      serialNumber: null,
      condition: "new",
      currency: "USD",
      askingPrice: null,
      needsAskingPrice: false,
    },
  };
}

/** The wedge scanner types into whatever has focus, then sends Enter. */
async function scan(user: ReturnType<typeof userEvent.setup>, code: string) {
  const input = screen.getByLabelText("Scan or type an IMEI, then press Enter");
  await user.type(input, `${code}{Enter}`);
  return input as HTMLInputElement;
}

const tradeIn: GoodsReceipt = {
  ...receipt,
  acquisitionSource: "trade_in",
  supplierId: null,
  customerId: "customer-1",
};

beforeEach(() => {
  vi.clearAllMocks();
  apiGet.mockResolvedValue({
    sale: null,
    buyback: {
      id: "rate-1",
      kind: "buyback",
      somPerUsd: "11500",
      effectiveOn: "2026-08-14",
      setAt: "2026-08-14T06:00:00Z",
      userId: "user-1",
      isStale: false,
    },
    today: "2026-08-14",
  });
  apiGetPaged.mockResolvedValue({
    items: [],
    pageIndex: 1,
    pageSize: 200,
    pagesCount: 0,
    totalItems: 0,
  });
});

describe("ScanConsole", () => {
  it("sends one scan per beep and clears the input for the next handset", async () => {
    apiSend.mockResolvedValue(scanResult(IMEI));
    const onScanned = vi.fn();
    const user = userEvent.setup();

    renderWithProviders(
      <ScanConsole receipt={receipt} referenceCosts={new Map()} onScanned={onScanned} />,
      { me: makeMe([Permission.Receiving.Manage, Permission.Catalog.View]) },
    );

    const input = await scan(user, IMEI);

    await waitFor(() => expect(apiSend).toHaveBeenCalledTimes(1));
    expect(apiSend).toHaveBeenCalledWith("POST", "/receipts/receipt-1/scan", {
      imei: IMEI,
      lineId: "line-1",
      condition: "new",
    });
    await waitFor(() => expect(input).toHaveValue(""));
    // The next scan lands here or it lands nowhere.
    expect(input).toHaveFocus();
    expect(onScanned).toHaveBeenCalledWith(scanResult(IMEI));
  });

  it("shows the running count the server returned", async () => {
    apiSend.mockResolvedValue(scanResult(IMEI));
    const user = userEvent.setup();

    renderWithProviders(
      <ScanConsole receipt={receipt} referenceCosts={new Map()} onScanned={vi.fn()} />,
      { me: makeMe([Permission.Receiving.Manage]) },
    );

    await scan(user, IMEI);

    expect(
      await screen.findByText(`${IMEI} accepted — 1 of 10`),
    ).toBeInTheDocument();
  });

  it("keeps a rejection on screen, verbatim, with the caret still in the input", async () => {
    // What the server says about a duplicate names the existing unit — the
    // console must not paraphrase that away (FR-3.5).
    const message = "IMEI 490154203237518 is already in stock at Chilonzor shop";
    apiSend.mockRejectedValue(new ApiError(409, message));
    const user = userEvent.setup();

    renderWithProviders(
      <ScanConsole receipt={receipt} referenceCosts={new Map()} onScanned={vi.fn()} />,
      { me: makeMe([Permission.Receiving.Manage]) },
    );

    const input = await scan(user, IMEI);

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(input).toHaveFocus();
    // The rejected code stays visible, so the operator can see what was read.
    expect(input).toHaveValue(IMEI);
  });

  it("picks the line still short of its count, so the first beep names one", async () => {
    // A scan onto a receipt with several serialized lines is refused unless
    // it names a line, and the operator has a phone in their hand.
    const full = {
      ...receipt.lines[0],
      id: "line-full",
      quantity: 1,
      scannedCount: 1,
      units: [scanResult("352099001761481").unit],
    };
    const short = { ...receipt.lines[0], id: "line-short" };
    apiSend.mockResolvedValue(scanResult(IMEI));
    const user = userEvent.setup();

    renderWithProviders(
      <ScanConsole
        receipt={{ ...receipt, lines: [full, short] }}
        referenceCosts={new Map()}
        onScanned={vi.fn()}
      />,
      { me: makeMe([Permission.Receiving.Manage]) },
    );

    await scan(user, IMEI);

    await waitFor(() =>
      expect(apiSend).toHaveBeenCalledWith(
        "POST",
        "/receipts/receipt-1/scan",
        expect.objectContaining({ lineId: "line-short" }),
      ),
    );
  });

  it("hides the line picker once only one line still needs scans, even with several lines on the receipt", () => {
    const full = {
      ...receipt.lines[0],
      id: "line-full",
      quantity: 1,
      scannedCount: 1,
      units: [scanResult("352099001761481").unit],
    };
    const short = { ...receipt.lines[0], id: "line-short" };

    renderWithProviders(
      <ScanConsole
        receipt={{ ...receipt, lines: [full, short] }}
        referenceCosts={new Map()}
        onScanned={vi.fn()}
      />,
      { me: makeMe([Permission.Receiving.Manage]) },
    );

    expect(screen.queryByLabelText("Line")).not.toBeInTheDocument();
  });

  it("auto-advances to the next incomplete line once the active one fills, without the operator picking one", async () => {
    const lineA = {
      ...receipt.lines[0],
      id: "line-a",
      productId: "product-a",
      quantity: 1,
      scannedCount: 0,
    };
    const lineB = {
      ...receipt.lines[0],
      id: "line-b",
      productId: "product-b",
      quantity: 1,
      scannedCount: 0,
    };
    apiSend.mockResolvedValue(scanResult(IMEI));
    const user = userEvent.setup();

    const { rerender } = renderWithProviders(
      <ScanConsole
        receipt={{ ...receipt, lines: [lineA, lineB] }}
        referenceCosts={new Map()}
        onScanned={vi.fn()}
      />,
      { me: makeMe([Permission.Receiving.Manage]) },
    );

    await scan(user, IMEI);
    await waitFor(() =>
      expect(apiSend).toHaveBeenLastCalledWith(
        "POST",
        "/receipts/receipt-1/scan",
        expect.objectContaining({ lineId: "line-a" }),
      ),
    );

    // The real page patches the cached receipt with the new count after a
    // successful scan, handing this component a fresh `receipt` object —
    // simulate that hand-off directly rather than re-plumbing React Query.
    rerender(
      <ScanConsole
        receipt={{ ...receipt, lines: [{ ...lineA, scannedCount: 1 }, lineB] }}
        referenceCosts={new Map()}
        onScanned={vi.fn()}
      />,
    );

    await scan(user, "352099001761481");
    await waitFor(() =>
      expect(apiSend).toHaveBeenLastCalledWith(
        "POST",
        "/receipts/receipt-1/scan",
        expect.objectContaining({ lineId: "line-b" }),
      ),
    );
  });

  it("replaces the scan form with a completion message once every line is fully scanned", () => {
    const full = { ...receipt.lines[0], scannedCount: 10 };

    renderWithProviders(
      <ScanConsole
        receipt={{ ...receipt, lines: [full] }}
        referenceCosts={new Map()}
        onScanned={vi.fn()}
      />,
      { me: makeMe([Permission.Receiving.Manage]) },
    );

    expect(
      screen.getByText("Every line is fully scanned — there is nothing left to scan."),
    ).toBeInTheDocument();
    expect(
      screen.queryByLabelText("Scan or type an IMEI, then press Enter"),
    ).not.toBeInTheDocument();
  });

  it("offers no money fields without the pricing permission (FR-3.4b)", () => {
    renderWithProviders(
      <ScanConsole receipt={receipt} referenceCosts={new Map()} onScanned={vi.fn()} />,
      { me: makeMe([Permission.Receiving.Manage]) },
    );

    expect(screen.queryByLabelText("Cost")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Asking price")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Cash paid")).not.toBeInTheDocument();
  });

  it("asks what was paid out on a supplier receipt too, without requiring it", () => {
    renderWithProviders(
      <ScanConsole receipt={receipt} referenceCosts={new Map()} onScanned={vi.fn()} />,
      { me: makeMe([Permission.Receiving.Manage, Permission.Pricing.Set]) },
    );

    const field = screen.getByLabelText("Cash paid");
    expect(field).toBeInTheDocument();
    expect(field).not.toBeRequired();
  });

  it("requires it on a trade-in and defaults it to the buying rate", async () => {
    const user = userEvent.setup();

    renderWithProviders(
      <ScanConsole receipt={tradeIn} referenceCosts={new Map()} onScanned={vi.fn()} />,
      { me: makeMe([Permission.Receiving.Manage, Permission.Pricing.Set]) },
    );

    expect(screen.getByLabelText(/cash paid/i)).toBeRequired();

    await user.type(screen.getByLabelText("Cost"), "330.00");

    // $330 at 11 500, defaulted into the field as well as shown as a hint.
    expect(await screen.findByText(/3\s795\s000/)).toBeInTheDocument();
    expect(screen.getByLabelText(/cash paid/i)).toHaveValue("3795000");

    // Typing a different figure opts out of the default.
    await user.clear(screen.getByLabelText(/cash paid/i));
    await user.type(screen.getByLabelText(/cash paid/i), "4000000");
    expect(screen.getByLabelText(/cash paid/i)).toHaveValue("4000000");
  });

  it("sends cost and price when the scanner does hold the pricing permission", async () => {
    apiSend.mockResolvedValue(scanResult(IMEI));
    const user = userEvent.setup();

    renderWithProviders(
      <ScanConsole receipt={receipt} referenceCosts={new Map()} onScanned={vi.fn()} />,
      { me: makeMe([Permission.Receiving.Manage, Permission.Pricing.Set]) },
    );

    await user.type(screen.getByLabelText("Cost"), "700.00");
    await scan(user, IMEI);

    await waitFor(() =>
      expect(apiSend).toHaveBeenCalledWith("POST", "/receipts/receipt-1/scan", {
        imei: IMEI,
        lineId: "line-1",
        condition: "new",
        acquisitionCost: "700.00",
      }),
    );
  });

  it("submits a camera-decoded code through the same scan path", async () => {
    apiSend.mockResolvedValue(scanResult(IMEI));
    const user = userEvent.setup();

    renderWithProviders(
      <ScanConsole receipt={receipt} referenceCosts={new Map()} onScanned={vi.fn()} />,
      { me: makeMe([Permission.Receiving.Manage]) },
    );

    await user.click(screen.getByLabelText("Scan with camera"));
    await waitFor(() => expect(screen.getByTestId("scanner")).toBeInTheDocument());
    act(() => scannerProps.onScan?.([{ rawValue: IMEI }]));

    await waitFor(() =>
      expect(apiSend).toHaveBeenCalledWith("POST", "/receipts/receipt-1/scan", {
        imei: IMEI,
        lineId: "line-1",
        condition: "new",
      }),
    );
  });
});
