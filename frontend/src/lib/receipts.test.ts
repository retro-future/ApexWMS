import { describe, expect, it } from "vitest";

import {
  confirmBlockers,
  isSerial,
  referenceCosts,
  scanProgress,
  shortLines,
  unitsNeedingPrice,
} from "@/lib/receipts";
import type {
  DeviceCondition,
  GoodsReceipt,
  GoodsReceiptLine,
  PurchaseOrder,
  ReceivedUnit,
} from "@/lib/types";

function unit(
  imei: string,
  condition: DeviceCondition,
  askingPriceMinor: number | null,
): ReceivedUnit {
  return {
    id: imei,
    imei,
    imei2: null,
    serialNumber: null,
    condition,
    currency: "USD",
    askingPrice:
      askingPriceMinor === null
        ? null
        : { minor: askingPriceMinor, currency: "USD" },
    // The server derives this; a used handset with no price is what FR-3.10
    // refuses the confirm over.
    needsAskingPrice: condition !== "new" && askingPriceMinor === null,
  };
}

function line(
  id: string,
  quantity: number,
  units: ReceivedUnit[],
  trackingType: "serial" | "quantity" = "serial",
): GoodsReceiptLine {
  return {
    id,
    productId: `product-${id}`,
    quantity,
    trackingType,
    currency: "USD",
    scannedCount: units.length,
    units,
  };
}

function receipt(lines: GoodsReceiptLine[]): GoodsReceipt {
  return {
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
    lines,
    subtotals: [],
    belowCostAlerts: [],
  };
}

describe("scanProgress", () => {
  it("counts what has been scanned against what was declared", () => {
    expect(scanProgress(line("a", 10, [unit("1", "new", null)]))).toEqual({
      scanned: 1,
      expected: 10,
      isComplete: false,
    });
  });

  it("is complete once the declared quantity is reached", () => {
    const units = [unit("1", "new", null), unit("2", "new", null)];
    expect(scanProgress(line("a", 2, units)).isComplete).toBe(true);
  });
});

describe("shortLines (FR-3.8)", () => {
  it("names serialized lines still missing IMEIs", () => {
    const short = line("a", 3, [unit("1", "new", null)]);
    const done = line("b", 1, [unit("2", "new", null)]);

    expect(shortLines(receipt([short, done]))).toEqual([short]);
  });

  it("ignores quantity lines, which are counted and not scanned", () => {
    const cases = line("c", 200, [], "quantity");
    expect(shortLines(receipt([cases]))).toEqual([]);
  });
});

describe("unitsNeedingPrice (FR-3.10)", () => {
  it("lists used handsets nobody has priced", () => {
    const used = unit("869924030176755", "used", null);
    const priced = unit("358240051111110", "used", 42000);
    const fresh = unit("490154203237518", "new", null);

    const needing = unitsNeedingPrice(receipt([line("a", 3, [used, priced, fresh])]));

    // A NEW handset may inherit the catalog price, so it is not a blocker.
    expect(needing).toEqual([used]);
  });
});

describe("confirmBlockers", () => {
  it("is ready when every line is full and every used unit is priced", () => {
    const full = line("a", 1, [unit("490154203237518", "new", null)]);

    expect(confirmBlockers(receipt([full])).isReady).toBe(true);
  });

  it("is not ready while a used handset carries no price", () => {
    const withUsed = line("a", 1, [unit("869924030176755", "used", null)]);

    const blockers = confirmBlockers(receipt([withUsed]));

    expect(blockers.isReady).toBe(false);
    expect(blockers.shortLines).toEqual([]);
    expect(blockers.unpricedUnits).toHaveLength(1);
  });

  it("reports both kinds of blocker at once, so one pass fixes them", () => {
    const short = line("a", 5, [unit("869924030176755", "used", null)]);

    const blockers = confirmBlockers(receipt([short]));

    expect(blockers.shortLines).toHaveLength(1);
    expect(blockers.unpricedUnits).toHaveLength(1);
  });
});

describe("isSerial", () => {
  it("separates handsets from boxes of accessories (§4.1)", () => {
    expect(isSerial(line("a", 1, []))).toBe(true);
    expect(isSerial(line("b", 200, [], "quantity"))).toBe(false);
  });
});

function poLine(productId: string, unitCostMinor: number | null): PurchaseOrder["lines"][number] {
  return {
    id: `po-line-${productId}`,
    productId,
    quantity: 1,
    trackingType: "serial",
    currency: "USD",
    unitCost:
      unitCostMinor === null ? null : { minor: unitCostMinor, currency: "USD" },
    totalCost: null,
    receivedQuantity: 0,
  };
}

function purchaseOrder(lines: PurchaseOrder["lines"]): PurchaseOrder {
  return {
    id: "po-1",
    number: "PO-2026-0001",
    status: "confirmed",
    supplierId: "supplier-1",
    note: null,
    createdBy: "user-1",
    createdAt: "2026-08-01T09:00:00Z",
    confirmedAt: "2026-08-01T09:05:00Z",
    cancelledAt: null,
    lines,
    subtotals: [],
    fulfilment: "pending",
  };
}

describe("referenceCosts", () => {
  it("maps a priced order line's cost by product, for use as a default", () => {
    const order = purchaseOrder([poLine("product-a", 25000)]);

    expect(referenceCosts(order)).toEqual(
      new Map([["product-a", { minor: 25000, currency: "USD" }]]),
    );
  });

  it("skips a line nobody has priced yet", () => {
    const order = purchaseOrder([poLine("product-a", null)]);

    expect(referenceCosts(order)).toEqual(new Map());
  });

  it("is empty without a linked order", () => {
    expect(referenceCosts(null)).toEqual(new Map());
    expect(referenceCosts(undefined)).toEqual(new Map());
  });
});
