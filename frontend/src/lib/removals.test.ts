import { describe, expect, it } from "vitest";

import { canConfirmRemoval, isSerialLine, removalTotals } from "@/lib/removals";
import type { RemovalLine, SupplierReturn, WriteOff } from "@/lib/types";

function line(overrides: Partial<RemovalLine> = {}): RemovalLine {
  return {
    id: crypto.randomUUID(),
    productId: "product-1",
    deviceUnitId: "device-1",
    imei: "490154203237518",
    quantity: 1,
    currency: "USD",
    trackingType: "serial",
    ...overrides,
  };
}

function supplierReturn(overrides: Partial<SupplierReturn> = {}): SupplierReturn {
  return {
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
    ...overrides,
  };
}

function writeOff(overrides: Partial<WriteOff> = {}): WriteOff {
  return {
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
    ...overrides,
  };
}

describe("isSerialLine", () => {
  it("separates a named handset from a count of accessories", () => {
    expect(isSerialLine(line())).toBe(true);
    expect(
      isSerialLine(
        line({ trackingType: "quantity", deviceUnitId: null, imei: null }),
      ),
    ).toBe(false);
  });
});

describe("canConfirmRemoval", () => {
  it("refuses an empty document, which is what the server refuses too", () => {
    expect(canConfirmRemoval(supplierReturn())).toBe(false);
    expect(canConfirmRemoval(writeOff())).toBe(false);
  });

  it("allows one with a line on it", () => {
    expect(
      canConfirmRemoval(supplierReturn({ lines: [line()], lineCount: 1 })),
    ).toBe(true);
    expect(canConfirmRemoval(writeOff({ lines: [line()], lineCount: 1 }))).toBe(
      true,
    );
  });
});

describe("removalTotals", () => {
  it("counts handsets and loose items separately, never adding them up", () => {
    const document = writeOff({
      lines: [
        line(),
        line({ imei: "352099001761481" }),
        line({
          trackingType: "quantity",
          deviceUnitId: null,
          imei: null,
          quantity: 3,
        }),
      ],
      lineCount: 3,
    });

    expect(removalTotals(document)).toEqual({ units: 2, quantity: 3 });
  });
});
