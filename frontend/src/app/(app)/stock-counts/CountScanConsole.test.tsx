import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CountScanConsole } from "@/app/(app)/stock-counts/CountScanConsole";
import { ApiError } from "@/lib/api";
import { Permission } from "@/lib/permissions";
import { makeMe, renderWithProviders } from "@/test/render";
import type { CountScanResult, StockCount } from "@/lib/types";

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

const count: StockCount = {
  id: "count-1",
  number: "SC-2026-0001",
  status: "draft",
  locationId: "location-1",
  note: null,
  createdBy: "user-1",
  createdAt: "2026-08-14T09:00:00Z",
  closedAt: null,
  confirmedAt: null,
  cancelledAt: null,
  cancellationReason: null,
  units: [],
  lines: [],
  matchedCount: 4,
  missingCount: 1,
  unexpectedCount: 0,
};

function scanResult(): CountScanResult {
  return {
    unit: {
      id: "unit-1",
      imei: IMEI,
      deviceUnitId: "device-1",
      productId: "product-1",
      expected: true,
      scanned: true,
      outcome: "matched",
      isSurprise: false,
    },
    line: null,
    matchedCount: 5,
    missingCount: 0,
    unexpectedCount: 0,
  };
}

/** The wedge scanner types into whatever has focus, then sends Enter. */
async function scan(user: ReturnType<typeof userEvent.setup>, code: string) {
  const input = screen.getByLabelText("Scan or type a code, then press Enter");
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

describe("CountScanConsole", () => {
  it("sends the bare code and clears the input for the next handset", async () => {
    apiSend.mockResolvedValue(scanResult());
    const onScanned = vi.fn();
    const user = userEvent.setup();

    renderWithProviders(
      <CountScanConsole count={count} onScanned={onScanned} />,
      { me: makeMe([Permission.StockCount.Run]) },
    );

    const input = await scan(user, IMEI);

    await waitFor(() => expect(apiSend).toHaveBeenCalledTimes(1));
    expect(apiSend).toHaveBeenCalledWith("POST", "/stock-counts/count-1/scan", {
      code: IMEI,
    });
    await waitFor(() => expect(input).toHaveValue(""));
    // The next scan lands here or it lands nowhere.
    expect(input).toHaveFocus();
    expect(onScanned).toHaveBeenCalledWith(scanResult());
  });

  it("shows the three running totals the server returned", async () => {
    apiSend.mockResolvedValue(scanResult());
    const user = userEvent.setup();

    renderWithProviders(<CountScanConsole count={count} onScanned={vi.fn()} />, {
      me: makeMe([Permission.StockCount.Run]),
    });

    await scan(user, IMEI);

    expect(
      await screen.findByText(
        `${IMEI} counted — 5 matched, 0 missing, 0 unexpected`,
      ),
    ).toBeInTheDocument();
  });

  it("keeps a rejection on screen, verbatim, with the caret still in the input", async () => {
    const message =
      "FANVIL-X3S is a serialized model, and SC-2026-0001 moves one named handset";
    apiSend.mockRejectedValue(new ApiError(409, message));
    const user = userEvent.setup();

    renderWithProviders(<CountScanConsole count={count} onScanned={vi.fn()} />, {
      me: makeMe([Permission.StockCount.Run]),
    });

    const input = await scan(user, IMEI);

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(input).toHaveFocus();
    // The rejected code stays visible, so the operator can see what was read.
    expect(input).toHaveValue(IMEI);
  });

  it("offers no condition picker — a surprise handset is USED by construction", () => {
    renderWithProviders(<CountScanConsole count={count} onScanned={vi.fn()} />, {
      me: makeMe([Permission.StockCount.Run, Permission.Pricing.Set]),
    });

    expect(screen.queryByLabelText("Condition")).not.toBeInTheDocument();
  });

  it("offers no cost field without the pricing permission", () => {
    renderWithProviders(<CountScanConsole count={count} onScanned={vi.fn()} />, {
      me: makeMe([Permission.StockCount.Run]),
    });

    expect(screen.queryByLabelText("Cost")).not.toBeInTheDocument();
  });

  it("omits the cost key entirely rather than sending it null", async () => {
    // The route escalates on the field being present in the body, so a null
    // would be refused exactly as a figure would.
    apiSend.mockResolvedValue(scanResult());
    const user = userEvent.setup();

    renderWithProviders(<CountScanConsole count={count} onScanned={vi.fn()} />, {
      me: makeMe([Permission.StockCount.Run, Permission.Pricing.Set]),
    });

    await scan(user, IMEI);

    await waitFor(() =>
      expect(apiSend).toHaveBeenCalledWith("POST", "/stock-counts/count-1/scan", {
        code: IMEI,
      }),
    );
  });
});
