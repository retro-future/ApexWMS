import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ScanConsole } from "@/components/scan/ScanConsole";
import { ApiError } from "@/lib/api";
import { Permission } from "@/lib/permissions";
import { makeMe, renderWithProviders } from "@/test/render";
import type { SupplierReturn, WriteOff } from "@/lib/types";

const { apiSend, apiGetPaged } = vi.hoisted(() => ({
  apiSend: vi.fn(),
  apiGetPaged: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => ({
  // ApiError is a real class the console's error handling depends on.
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiSend,
  apiGetPaged,
}));

vi.mock("@zxing/browser", () => ({
  BrowserMultiFormatReader: vi.fn().mockImplementation(function Reader() {
    return { decodeFromConstraints: vi.fn() };
  }),
}));

const IMEI = "490154203237518";

const supplierReturn: SupplierReturn = {
  id: "return-1",
  number: "SR-2026-0001",
  status: "draft",
  supplierId: "supplier-1",
  locationId: "location-1",
  reason: "defective",
  note: null,
  createdBy: "user-1",
  createdAt: "2026-08-14T09:00:00Z",
  confirmedAt: null,
  cancelledAt: null,
  cancellationReason: null,
  lines: [],
  lineCount: 0,
};

const writeOff: WriteOff = {
  id: "write-off-1",
  number: "WO-2026-0001",
  status: "draft",
  locationId: "location-1",
  reason: "theft",
  note: null,
  createdBy: "user-1",
  createdAt: "2026-08-14T09:00:00Z",
  confirmedAt: null,
  cancelledAt: null,
  cancellationReason: null,
  lines: [],
  lineCount: 0,
};

function scanned(document: SupplierReturn): SupplierReturn {
  return {
    ...document,
    lineCount: 1,
    lines: [
      {
        id: "line-1",
        productId: "product-1",
        deviceUnitId: "device-1",
        imei: IMEI,
        quantity: 1,
        currency: "USD",
        trackingType: "serial",
      },
    ],
  };
}

/** The wedge scanner types into whatever has focus, then sends Enter. */
async function scan(user: ReturnType<typeof userEvent.setup>, code: string) {
  const input = screen.getByLabelText("Scan or type an IMEI, then press Enter");
  await user.type(input, `${code}{Enter}`);
  return input as HTMLInputElement;
}

beforeEach(() => {
  vi.clearAllMocks();
  apiGetPaged.mockResolvedValue({
    items: [],
    pageIndex: 1,
    pageSize: 200,
    pagesCount: 0,
    totalItems: 0,
  });
});

describe("ScanConsole", () => {
  it("sends the bare code and clears the input for the next handset", async () => {
    apiSend.mockResolvedValue(scanned(supplierReturn));
    const onScanned = vi.fn();
    const user = userEvent.setup();

    renderWithProviders(
      <ScanConsole
        namespace="supplierReturns.scan"
        resource="supplier-returns"
        document={supplierReturn}
        onScanned={onScanned}
      />,
      { me: makeMe([Permission.SupplierReturn.Manage]) },
    );

    const input = await scan(user, IMEI);

    await waitFor(() => expect(apiSend).toHaveBeenCalledTimes(1));
    expect(apiSend).toHaveBeenCalledWith(
      "POST",
      "/supplier-returns/return-1/scan",
      { code: IMEI },
    );
    await waitFor(() => expect(input).toHaveValue(""));
    // The next scan lands here or it lands nowhere.
    expect(input).toHaveFocus();
    expect(onScanned).toHaveBeenCalledWith(scanned(supplierReturn));
  });

  it("routes to the write-off endpoint when that is the document", async () => {
    apiSend.mockResolvedValue({ ...writeOff, lineCount: 1 });
    const user = userEvent.setup();

    renderWithProviders(
      <ScanConsole
        namespace="supplierReturns.scan"
        resource="write-offs"
        document={writeOff}
        onScanned={vi.fn()}
      />,
      { me: makeMe([Permission.WriteOff.Manage]) },
    );

    await scan(user, IMEI);

    await waitFor(() =>
      expect(apiSend).toHaveBeenCalledWith(
        "POST",
        "/write-offs/write-off-1/scan",
        { code: IMEI },
      ),
    );
  });

  it("shows the running count the server returned", async () => {
    apiSend.mockResolvedValue(scanned(supplierReturn));
    const user = userEvent.setup();

    renderWithProviders(
      <ScanConsole
        namespace="supplierReturns.scan"
        resource="supplier-returns"
        document={supplierReturn}
        onScanned={vi.fn()}
      />,
      { me: makeMe([Permission.SupplierReturn.Manage]) },
    );

    await scan(user, IMEI);

    expect(
      await screen.findByText(`${IMEI} added — 1 on this return`),
    ).toBeInTheDocument();
  });

  it("keeps a rejection on screen, verbatim, with the caret still in the input", async () => {
    // FR-5.2's refusal names the handset's actual status, and the console
    // must not paraphrase that away.
    const message =
      "IMEI 490154203237518 is sold and is not on the shelf, so SR-2026-0001 cannot move it (FR-5.2)";
    apiSend.mockRejectedValue(new ApiError(409, message));
    const user = userEvent.setup();

    renderWithProviders(
      <ScanConsole
        namespace="supplierReturns.scan"
        resource="supplier-returns"
        document={supplierReturn}
        onScanned={vi.fn()}
      />,
      { me: makeMe([Permission.SupplierReturn.Manage]) },
    );

    const input = await scan(user, IMEI);

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(input).toHaveFocus();
    // The rejected code stays visible, so the operator can see what was read.
    expect(input).toHaveValue(IMEI);
  });

  it("ignores an empty submission rather than calling the server", async () => {
    const user = userEvent.setup();

    renderWithProviders(
      <ScanConsole
        namespace="supplierReturns.scan"
        resource="supplier-returns"
        document={supplierReturn}
        onScanned={vi.fn()}
      />,
      { me: makeMe([Permission.SupplierReturn.Manage]) },
    );

    await user.click(screen.getByRole("button", { name: "Scan" }));

    expect(apiSend).not.toHaveBeenCalled();
  });
});
